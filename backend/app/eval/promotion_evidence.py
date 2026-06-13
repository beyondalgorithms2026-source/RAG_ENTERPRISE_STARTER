"""AR4: eval-pack runs as promotion evidence.

Closes the audit's "single biggest missed integration": the promotion path
never invoked evaluation. This module runs AR3 packs under a candidate's
profile bundle, persists the run, and computes live-vs-candidate metric
deltas for promotion records.

Candidate profile application reuses the sandbox-compare temporary-profile
context managers, which monkeypatch module-level resolvers. That is
concurrency-unsafe (audit finding, AR8 scope): a concurrent live request
during a candidate eval could see candidate profiles.
"""
import hashlib
import json
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Optional

from app.auth.context import AuthenticatedUser
from app.core.config import settings
from app.db.repo_eval_runs import insert_eval_run, latest_live_baseline_run
from app.db.repo_tuning_configs import get_candidate_draft, get_live_configuration
from app.eval.pack_eval import DEFAULT_THRESHOLDS, run_pack_eval
from app.eval.pack_builder import PACKS_DIR
from app.tuning.sandbox_compare import (
    _profile_models_with_retrieval_override,
    _temporary_reranker_profile,
    _temporary_retrieval_profile,
)

DELTA_METRICS = ("recall_at_5", "recall_at_10", "mrr", "ndcg_at_10")
ENFORCEMENT_MODES = ("require", "warn")


def resolve_enforcement_mode() -> str:
    explicit = str(settings.TUNING_EVAL_ENFORCEMENT or "").strip().lower()
    if explicit in ENFORCEMENT_MODES:
        return explicit
    return "warn" if settings.APP_ENV == "local" else "require"


def config_fingerprint(resolved_config: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(resolved_config, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def resolve_pack_paths(pack_names: Optional[list[str]]) -> Optional[list[Path]]:
    """Pack names only — never caller-supplied paths — resolved inside PACKS_DIR."""
    if not pack_names:
        return None
    paths: list[Path] = []
    for name in pack_names:
        token = str(name).strip()
        if not token or "/" in token or "\\" in token or ".." in token:
            raise ValueError(f"Invalid pack name: {name!r}")
        path = PACKS_DIR / f"{token}.json" if not token.endswith(".json") else PACKS_DIR / token
        if not path.exists():
            raise ValueError(f"Pack not found: {token}")
        paths.append(path)
    return paths


def metric_deltas(candidate_aggregates: dict[str, Any], baseline_aggregates: dict[str, Any]) -> dict[str, Optional[float]]:
    deltas: dict[str, Optional[float]] = {}
    for metric in DELTA_METRICS:
        candidate = candidate_aggregates.get(metric)
        baseline = baseline_aggregates.get(metric)
        deltas[metric] = round(float(candidate) - float(baseline), 4) if candidate is not None and baseline is not None else None
    return deltas


def run_candidate_eval(
    *,
    draft_id: Optional[int] = None,
    pack_names: Optional[list[str]] = None,
    sample_size: Optional[int] = 150,
    k: int = 10,
    thresholds: Optional[dict[str, float]] = None,
    actor: Optional[AuthenticatedUser] = None,
) -> dict[str, Any]:
    """Run AR3 packs under the draft's profile bundle (or the live config when
    draft_id is None) and persist the result as promotion evidence."""
    pack_paths = resolve_pack_paths(pack_names)
    if draft_id is None:
        selected_profiles = dict((get_live_configuration() or {}).get("selected_profiles") or {})
        resolved = dict((get_live_configuration() or {}).get("resolved_config") or {})
        label = "live"
        contexts: list[Any] = []
    else:
        draft = get_candidate_draft(draft_id)
        if not draft:
            raise ValueError(f"Draft {draft_id} not found")
        selected_profiles = dict(draft.get("selected_profiles") or {})
        live_selected = dict((get_live_configuration() or {}).get("selected_profiles") or {})
        if selected_profiles.get("embedding") and live_selected.get("embedding") and selected_profiles["embedding"] != live_selected["embedding"]:
            # Evaluating a different embedding model against the current index
            # would score a vector space that does not exist yet.
            raise ValueError(
                "blocked_embedding_scope: candidate selects a different embedding profile; "
                "eval against the current index would be meaningless. Run the embedding "
                "experiment workflow first."
            )
        override = dict((draft.get("lineage") or {}).get("retrieval_override_config") or {})
        models = _profile_models_with_retrieval_override(selected_profiles, override)
        resolved = models["resolved"]
        label = "candidate"
        contexts = [
            _temporary_retrieval_profile(models["retrieval"]),
            _temporary_reranker_profile(models["reranker"]),
        ]

    with ExitStack() as stack:
        for context in contexts:
            stack.enter_context(context)
        report = run_pack_eval(
            pack_paths=pack_paths,
            modes=("hybrid",),
            k=k,
            thresholds=thresholds,
            label=label,
            gate_mode_sample=sample_size,
        )

    # Persist without per-case payloads; aggregates and gate are the evidence.
    slim_report = dict(report)
    slim_report["packs"] = [{key: value for key, value in pack.items() if key != "cases"} for pack in report["packs"]]
    run = insert_eval_run(
        run_label=label,
        draft_id=draft_id,
        config_fingerprint=config_fingerprint(resolved),
        gate_status=report["gate"]["status"],
        gate_aggregates=report["gate_aggregates"],
        thresholds=report["gate"]["thresholds"],
        selected_profiles=selected_profiles,
        report=slim_report,
        sample_size=sample_size,
        duration_s=report.get("duration_s"),
        actor=actor,
    )
    baseline = latest_live_baseline_run()
    if baseline and draft_id is not None:
        run["baseline_eval_run_id"] = baseline["id"]
        run["deltas_vs_live_baseline"] = metric_deltas(run["gate_aggregates"], baseline["gate_aggregates"])
    return run


def build_promotion_evidence(
    *,
    eval_run: Optional[dict[str, Any]],
    enforcement_mode: str,
    warnings: list[str],
) -> dict[str, Any]:
    """The evidence object stored on the promotion event (loud in warn mode)."""
    evidence: dict[str, Any] = {"enforcement_mode": enforcement_mode, "warnings": warnings}
    if eval_run:
        baseline = latest_live_baseline_run()
        evidence.update(
            {
                "eval_run_id": eval_run["id"],
                "gate_status": eval_run["gate_status"],
                "gate_aggregates": eval_run["gate_aggregates"],
                "thresholds": eval_run["thresholds"],
                "baseline_eval_run_id": baseline["id"] if baseline else None,
                "baseline_gate_aggregates": baseline["gate_aggregates"] if baseline else None,
                "deltas_vs_live_baseline": metric_deltas(eval_run["gate_aggregates"], baseline["gate_aggregates"]) if baseline else None,
            }
        )
    else:
        evidence["eval_run_id"] = None
        evidence["gate_status"] = None
    return evidence
