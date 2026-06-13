"""Feedback-to-eval flywheel (AR12).

The audit found all the ingredients present but disconnected: 423 traces, 176
query events, 101 feedback rows, plus query_failure_clusters and
derived_eval_packs tables — "but there was no path from a thumbs-down cluster or
missing_evidence event to an eval case, and no trend reporting on pack pass
rates."

This closes the loop: a failure cluster's questions become *quarantined*
(review_status="unreviewed") cases in an AR3 pack, prefilled with whatever trace
evidence exists; a human reviews and labels them into gating cases; and pack
pass-rate trends are read back from the AR4 eval-run history. The quarantine is
the guardrail — noisy feedback can never poison the gate, because the AR3 gate
excludes unreviewed cases until a human reviews them.
"""
import json
import time
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import text

from app.auth.context import AuthenticatedUser
from app.db.db import engine
from app.db.repo_query_mining import normalize_question
from app.eval.pack_builder import PACKS_DIR

PROVENANCE = "feedback_derived"


def _pack_path(pack_name: str) -> Path:
    token = str(pack_name or "").strip()
    if not token or "/" in token or "\\" in token or ".." in token:
        raise ValueError(f"Invalid pack name: {pack_name!r}")
    if not token.startswith("pack_"):
        token = f"pack_{token}"
    if not token.endswith(".json"):
        token = f"{token}.json"
    return PACKS_DIR / token


def load_pack(pack_name: str) -> dict[str, Any]:
    path = _pack_path(pack_name)
    if not path.exists():
        raise ValueError(f"Pack '{pack_name}' not found at {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_pack(pack: dict[str, Any], pack_name: str) -> Path:
    path = _pack_path(pack_name)
    path.write_text(json.dumps(pack, indent=1) + "\n", encoding="utf-8")
    return path


def _evidence_for_question(conn, normalized: str) -> tuple[dict[str, int], list[int]]:
    """Prefill a graded relevance map from any recorded trace for this question:
    cited chunks → grade 2 (supporting), as a starting point for human review."""
    row = conn.execute(
        text(
            """
            SELECT rt.trace_json
            FROM query_events qe
            JOIN retrieval_traces rt ON rt.request_id = qe.request_id
            WHERE qe.normalized_question = :nq AND rt.trace_json IS NOT NULL
            ORDER BY qe.id DESC
            LIMIT 1
            """
        ),
        {"nq": normalized},
    ).first()
    if not row or not row[0]:
        return {}, []
    trace = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    cited = trace.get("cited_chunk_ids") or []
    accessed = (trace.get("acl") or {}).get("accessed_doc_ids") or []
    return {str(cid): 2 for cid in cited}, list(accessed)


def propose_cases_from_cluster(cluster_id: int) -> dict[str, Any]:
    """Propose (do not persist) quarantined eval cases from a failure cluster."""
    with engine.connect() as conn:
        cluster = conn.execute(
            text("SELECT id, label, sample_questions_json FROM query_failure_clusters WHERE id = :id"),
            {"id": cluster_id},
        ).mappings().first()
        if not cluster:
            raise ValueError(f"Cluster {cluster_id} not found")
        questions = list(cluster["sample_questions_json"] or [])
        if not questions and cluster["label"]:
            questions = [cluster["label"]]
        cases: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, question in enumerate(questions):
            normalized = normalize_question(question)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            relevant, accessed = _evidence_for_question(conn, normalized)
            cases.append(
                {
                    "id": f"feedback-{cluster_id}-{index + 1}",
                    "question": question,
                    "provenance": PROVENANCE,
                    "review_status": "unreviewed",
                    "relevant": relevant,
                    "needs_label": not relevant,
                    "source_cluster_id": cluster_id,
                    "accessed_doc_ids": accessed,
                }
            )
    return {"cluster_id": cluster_id, "label": cluster["label"], "proposed_cases": cases}


def append_cases_to_pack(pack_name: str, cases: list[dict[str, Any]], *, actor: Optional[AuthenticatedUser] = None) -> dict[str, Any]:
    """Append proposed cases to an AR3 pack as quarantined (unreviewed) cases.
    Deduplicated by normalized question; existing cases are never overwritten."""
    pack = load_pack(pack_name)
    existing = {normalize_question(str(c.get("question"))) for c in pack.get("cases", [])}
    added = []
    for case in cases:
        normalized = normalize_question(str(case.get("question")))
        if not normalized or normalized in existing:
            continue
        existing.add(normalized)
        entry = dict(case)
        entry["review_status"] = "unreviewed"  # quarantine guardrail
        entry["provenance"] = entry.get("provenance") or PROVENANCE
        entry["derived_by"] = actor.email if actor else None
        entry["derived_at"] = int(time.time())
        pack.setdefault("cases", []).append(entry)
        added.append(entry["id"])
    pack["case_counts"] = _recount(pack["cases"])
    _write_pack(pack, pack_name)
    return {"pack": pack_name, "added": added, "added_count": len(added), "total": len(pack["cases"])}


def review_pack_case(
    pack_name: str,
    case_id: str,
    *,
    relevant: dict[str, int],
    review_status: str = "reviewed",
    reviewer: Optional[str] = None,
) -> dict[str, Any]:
    """Label a quarantined case and flip it to reviewed so it gates the next run.
    A reviewed case must carry a non-empty graded relevance map."""
    if review_status == "reviewed" and not relevant:
        raise ValueError("A reviewed case requires a non-empty graded relevance map.")
    pack = load_pack(pack_name)
    case = next((c for c in pack.get("cases", []) if c.get("id") == case_id), None)
    if case is None:
        raise ValueError(f"Case '{case_id}' not found in pack '{pack_name}'.")
    case["relevant"] = {str(k): int(v) for k, v in (relevant or {}).items()}
    case["review_status"] = review_status
    case["needs_label"] = False
    case["reviewed_by"] = reviewer
    case["reviewed_at"] = int(time.time())
    pack["case_counts"] = _recount(pack["cases"])
    _write_pack(pack, pack_name)
    return case


def _recount(cases: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {"total": len(cases)}
    for case in cases:
        counts[case.get("provenance", "unknown")] = counts.get(case.get("provenance", "unknown"), 0) + 1
        status_key = f"review_{case.get('review_status', 'unreviewed')}"
        counts[status_key] = counts.get(status_key, 0) + 1
    return counts


def quarantine_summary(pack_name: str) -> dict[str, Any]:
    pack = load_pack(pack_name)
    cases = pack.get("cases", [])
    by_status: dict[str, int] = {}
    for case in cases:
        status = case.get("review_status", "unreviewed")
        by_status[status] = by_status.get(status, 0) + 1
    feedback_unreviewed = [
        {"id": c["id"], "question": c["question"], "needs_label": bool(c.get("needs_label"))}
        for c in cases
        if c.get("provenance") == PROVENANCE and c.get("review_status") == "unreviewed"
    ]
    return {
        "pack": pack_name,
        "total": len(cases),
        "by_review_status": by_status,
        "quarantined_feedback_cases": feedback_unreviewed,
    }


def pack_passrate_trend(*, limit: int = 50) -> dict[str, Any]:
    """Pack pass-rate over time, read from the AR4 eval-run history. Each point
    is a recorded eval run with its gate status and headline metrics."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, run_label, gate_status, gate_aggregates_json, created_at
                FROM tuning_eval_runs
                ORDER BY created_at ASC, id ASC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
    points = []
    passes = 0
    for index, row in enumerate(rows, start=1):
        if row["gate_status"] == "pass":
            passes += 1
        aggregates = row["gate_aggregates_json"] or {}
        points.append(
            {
                "run_id": row["id"],
                "label": row["run_label"],
                "gate_status": row["gate_status"],
                "recall_at_5": aggregates.get("recall_at_5"),
                "mrr": aggregates.get("mrr"),
                "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else row["created_at"],
                "cumulative_pass_rate": round(passes / index, 4),
            }
        )
    return {"points": points, "run_count": len(points), "overall_pass_rate": round(passes / len(points), 4) if points else None}
