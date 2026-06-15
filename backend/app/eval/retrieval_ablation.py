from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.eval.metrics import evaluate_ranking
from app.eval.pack_builder import PACKS_DIR


CASES_PATH = PACKS_DIR / "AR14_retrieval_isolation_cases.json"
REPORT_PATH = PACKS_DIR / "AR14_retrieval_ablation_report.json"
AR3_BASELINE_PATH = PACKS_DIR / "AR3_baseline_report.json"
MIN_GAIN = 0.01


def _ranking_metrics(payload: dict[str, Any], relevant: dict[int, int]) -> dict[str, float | None]:
    return evaluate_ranking([int(item) for item in payload["ranked"]], relevant, ks=(5, 10))


def _delta(candidate: float | None, baseline: float | None) -> float | None:
    if candidate is None or baseline is None:
        return None
    return round(float(candidate) - float(baseline), 4)


def _verdict(feature: str, baseline: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    relevant = {int(key): int(value) for key, value in (baseline.get("relevant") or {}).items()}
    baseline_metrics = _ranking_metrics(baseline, relevant)
    candidate_metrics = _ranking_metrics(variant, relevant)
    deltas = {
        key: _delta(candidate_metrics.get(key), baseline_metrics.get(key))
        for key in ("recall_at_5", "mrr", "ndcg_at_10")
    }
    feature_gain = None
    if feature == "mmr":
        feature_gain = round(float(variant["diversity"]) - float(baseline["diversity"]), 4)
    qualifying_gain = (deltas["ndcg_at_10"] or 0.0) >= MIN_GAIN or (feature_gain or 0.0) >= MIN_GAIN
    passes = (
        (deltas["recall_at_5"] or 0.0) >= 0.0
        and (deltas["mrr"] or 0.0) >= 0.0
        and qualifying_gain
    )
    return {
        "name": variant["name"],
        "metrics": candidate_metrics,
        "deltas": deltas,
        "feature_metric": {"name": "intra_list_diversity", "delta": feature_gain} if feature_gain is not None else None,
        "latency_ms": variant.get("latency_ms"),
        "passes": passes,
    }


def _choose(variants: list[dict[str, Any]]) -> dict[str, Any] | None:
    passing = [item for item in variants if item["passes"]]
    if not passing:
        return None
    return max(
        passing,
        key=lambda item: (
            float(((item.get("feature_metric") or {}).get("delta")) or 0.0),
            float((item["deltas"].get("ndcg_at_10")) or 0.0),
            -float(item.get("latency_ms") or 0.0),
        ),
    )


def build_report(*, global_after: dict[str, Any] | None = None) -> dict[str, Any]:
    from app.core_rag.retrieval_scoring import scoring_snapshot

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    evidence = []
    for feature in cases["features"]:
        relevant = {int(key): int(value) for key, value in (feature["baseline"].get("relevant") or {}).items()}
        baseline_metrics = _ranking_metrics(feature["baseline"], relevant)
        variants = [_verdict(feature["feature"], feature["baseline"], variant) for variant in feature["variants"]]
        chosen = _choose(variants)
        evidence.append(
            {
                "feature": feature["feature"],
                "baseline_metrics": baseline_metrics,
                "variants": variants,
                "verdict": "adopted" if chosen else "retired",
                "chosen": chosen["name"] if chosen else None,
            }
        )

    ar3_before = json.loads(AR3_BASELINE_PATH.read_text(encoding="utf-8"))
    return {
        "kind": "ar14_retrieval_ablation",
        "gate": "no_unfalsifiable_tuning",
        "decision_policy": {
            "core_non_regression": ["recall_at_5", "mrr"],
            "minimum_gain": MIN_GAIN,
            "gain_metrics": ["ndcg_at_10", "feature_specific"],
        },
        "limitations": cases["limitations"],
        "global_control": {
            "before": ar3_before["gate_aggregates"],
            "after": (global_after or {}).get("gate_aggregates"),
            "after_gate": (global_after or {}).get("gate"),
        },
        "evidence": evidence,
        "adopted_scoring": scoring_snapshot(),
        "removed": ["demo_causal_terms_vocabulary"],
    }


def write_report(report: dict[str, Any]) -> Path:
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return REPORT_PATH


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-global", action="store_true")
    parser.add_argument("--cpu", action="store_true")
    args = parser.parse_args()
    if args.cpu:
        import torch

        torch.backends.mps.is_available = lambda: False
    global_after = None
    if args.run_global:
        from app.eval.pack_eval import run_pack_eval

        global_after = run_pack_eval(
            pack_paths=[PACKS_DIR / "pack_general.json"],
            modes=("hybrid",),
            gate_mode="hybrid",
            label="ar14_after",
        )
    path = write_report(build_report(global_after=global_after))
    print(path)


if __name__ == "__main__":
    main()
