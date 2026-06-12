"""Graded eval pack runner with promotion-grade metrics (AR3).

Runs labeled packs (see app/eval/pack_builder.py) through perform_search,
computes recall@k / MRR / nDCG per case, aggregates per mode and per
provenance, evaluates a threshold gate, and emits a report carrying the
active-profile snapshot — the evidence object AR4 attaches to promotions.

Gate semantics: only reviewed/auto_labeled cases gate; cases with
review_status == "unreviewed" (mined, not yet human-checked) are reported
separately and never fail the gate (AR12 quarantine rule).

Run: python -m app.eval.pack_eval [--degraded] [--out PATH]
"""
import argparse
import json
import time
from pathlib import Path
from typing import Any, Optional

from app.core_rag.retrieval import SearchRequest, perform_search
from app.eval.metrics import aggregate_case_metrics, evaluate_ranking
from app.eval.pack_builder import PACKS_DIR

DEFAULT_MODES = ("keyword", "vector", "hybrid")
# Calibrated from the committed AR3 baseline (2026-06-12: recall@5 0.504,
# MRR 0.850 on the live profile) minus a regression margin. Raise as the
# baseline improves; never lower to make a candidate pass.
DEFAULT_THRESHOLDS = {"recall_at_5": 0.45, "mrr": 0.78}

# Deliberately crippled retrieval used as the negative control: candidate
# starvation plus zeroed vector weight must measurably fail the gate.
DEGRADED_RETRIEVAL_OVERRIDES = {
    "hybrid_alpha": 0.0,
    "vector_candidates": 1,
    "keyword_candidates": 1,
    "top_k_initial": 1,
}


def load_pack(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def evaluate_case(case: dict[str, Any], *, mode: str, k: int = 10) -> dict[str, Any]:
    relevant_grades = {int(chunk_id): int(grade) for chunk_id, grade in (case.get("relevant") or {}).items()}
    response = perform_search(SearchRequest(question=case["question"], k=k, mode=mode))
    ranked_ids = [item.chunk_id for item in response.results]
    metrics = evaluate_ranking(ranked_ids, relevant_grades, ks=(5, 10))
    return {
        "case_id": case["id"],
        "mode": mode,
        "provenance": case.get("provenance", "unknown"),
        "review_status": case.get("review_status", "auto_labeled"),
        "resolved_mode": response.mode,
        "ranked_chunk_ids": ranked_ids[:k],
        **metrics,
    }


def evaluate_gate(aggregates: dict[str, Optional[float]], thresholds: dict[str, float]) -> dict[str, Any]:
    failures = []
    for metric, threshold in thresholds.items():
        observed = aggregates.get(metric)
        if observed is None or observed < threshold:
            failures.append({"metric": metric, "threshold": threshold, "observed": observed})
    return {"status": "fail" if failures else "pass", "thresholds": thresholds, "failures": failures}


def _sample_cases(cases: list[dict[str, Any]], sample_size: Optional[int]) -> list[dict[str, Any]]:
    """Deterministic even-stride sample so per-mode breakdowns stay affordable
    when the live config reranks every search (~5s/query on this hardware)."""
    if sample_size is None or sample_size >= len(cases):
        return cases
    stride = max(1, len(cases) // sample_size)
    return cases[::stride][:sample_size]


def run_pack_eval(
    *,
    pack_paths: Optional[list[Path]] = None,
    modes: tuple[str, ...] = DEFAULT_MODES,
    k: int = 10,
    thresholds: Optional[dict[str, float]] = None,
    gate_mode: str = "hybrid",
    label: str = "live",
    non_gate_mode_sample: Optional[int] = None,
) -> dict[str, Any]:
    from app.profiles.resolver import get_active_profile_snapshot, get_effective_retrieval

    thresholds = dict(thresholds or DEFAULT_THRESHOLDS)
    paths = list(pack_paths) if pack_paths else sorted(PACKS_DIR.glob("pack_*.json"))
    started = time.time()
    pack_reports: list[dict[str, Any]] = []
    gating_case_metrics: list[dict[str, Any]] = []

    for path in paths:
        pack = load_pack(path)
        all_cases = pack.get("cases", [])
        case_results: list[dict[str, Any]] = []
        for mode in modes:
            mode_cases = all_cases if mode == gate_mode else _sample_cases(all_cases, non_gate_mode_sample)
            for case in mode_cases:
                case_results.append(evaluate_case(case, mode=mode, k=k))
        gating = [r for r in case_results if r["mode"] == gate_mode and r["review_status"] != "unreviewed"]
        gating_case_metrics.extend(gating)
        per_mode = {
            mode: aggregate_case_metrics([r for r in case_results if r["mode"] == mode])
            for mode in modes
        }
        per_provenance = {
            provenance: aggregate_case_metrics([r for r in case_results if r["provenance"] == provenance])
            for provenance in sorted({r["provenance"] for r in case_results})
        }
        pack_reports.append(
            {
                "pack": pack.get("pack"),
                "corpus": pack.get("corpus"),
                "builder_version": pack.get("builder_version"),
                "case_count": len(all_cases),
                "non_gate_mode_sample": non_gate_mode_sample,
                "gating_case_count": len(gating),
                "unreviewed_case_count": sum(1 for case in all_cases if case.get("review_status") == "unreviewed"),
                "metrics_by_mode": per_mode,
                "metrics_by_provenance": per_provenance,
                "cases": case_results,
            }
        )

    gate_aggregates = aggregate_case_metrics(gating_case_metrics)
    report = {
        "kind": "pack_eval",
        "label": label,
        "generated_at": int(started),
        "duration_s": round(time.time() - started, 1),
        "k": k,
        "modes": list(modes),
        "gate_mode": gate_mode,
        "active_profiles": get_active_profile_snapshot(),
        "effective_retrieval": get_effective_retrieval().model_dump(),
        "gate_aggregates": gate_aggregates,
        "gate": evaluate_gate(gate_aggregates, thresholds),
        "packs": pack_reports,
    }
    return report


def write_report(report: dict[str, Any], path: Path, *, include_cases: bool = False) -> Path:
    payload = dict(report)
    if not include_cases:
        payload["packs"] = [{k: v for k, v in pack.items() if k != "cases"} for pack in report["packs"]]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    return path


def _degraded_retrieval_profile():
    from app.profiles.resolver import get_effective_retrieval

    return get_effective_retrieval().model_copy(update=DEGRADED_RETRIEVAL_OVERRIDES)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packs", nargs="*", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=PACKS_DIR / "pack_eval_report.json")
    parser.add_argument("--degraded", action="store_true", help="Run under the deliberately degraded negative-control profile")
    parser.add_argument("--include-cases", action="store_true")
    parser.add_argument("--non-gate-mode-sample", type=int, default=100)
    parser.add_argument(
        "--cpu",
        action="store_true",
        help="Force CPU inference. Sustained MPS (Metal) runs were observed to "
        "hang in GPU sync during long eval batches; CPU is slower per query but stable.",
    )
    args = parser.parse_args()

    if args.cpu:
        import torch

        torch.backends.mps.is_available = lambda: False  # before any model loads

    if args.degraded:
        import app.core_rag.retrieval as retrieval_module
        import app.profiles.resolver as resolver_module

        degraded = _degraded_retrieval_profile()
        resolver_module.get_effective_retrieval = lambda: degraded
        retrieval_module.get_effective_retrieval = lambda: degraded
        label = "degraded_control"
    else:
        label = "live"

    report = run_pack_eval(pack_paths=args.packs, label=label, non_gate_mode_sample=args.non_gate_mode_sample)
    path = write_report(report, args.out, include_cases=args.include_cases)
    print(json.dumps({"report": str(path), "gate": report["gate"], "gate_aggregates": report["gate_aggregates"]}, indent=1))


if __name__ == "__main__":
    main()
