"""Persisted eval-pack runs used as promotion evidence (AR4).

The audit's biggest missed integration: the promotion path never invoked
evaluation. Rows here are the evidence objects promotion/rollback events link.
"""
import json
from typing import Any, Optional

from sqlalchemy import text

from app.auth.context import AuthenticatedUser
from app.db.db import engine

_COLUMNS = """
    id, run_label, draft_id, config_fingerprint, gate_status,
    gate_aggregates_json, thresholds_json, selected_profiles_json,
    report_json, sample_size, duration_s, actor_external_user_id,
    actor_email, created_at
"""


def _payload(row: Any, *, include_report: bool = False) -> dict[str, Any]:
    payload = dict(row)
    payload["created_at"] = str(payload["created_at"])
    payload["gate_aggregates"] = payload.pop("gate_aggregates_json") or {}
    payload["thresholds"] = payload.pop("thresholds_json") or {}
    payload["selected_profiles"] = payload.pop("selected_profiles_json") or {}
    report = payload.pop("report_json") or {}
    if include_report:
        payload["report"] = report
    return payload


def insert_eval_run(
    *,
    run_label: str,
    draft_id: Optional[int],
    config_fingerprint: str,
    gate_status: str,
    gate_aggregates: dict[str, Any],
    thresholds: dict[str, Any],
    selected_profiles: dict[str, str],
    report: dict[str, Any],
    sample_size: Optional[int],
    duration_s: Optional[float],
    actor: Optional[AuthenticatedUser] = None,
) -> dict[str, Any]:
    sql = text(
        f"""
        INSERT INTO tuning_eval_runs (
            run_label, draft_id, config_fingerprint, gate_status,
            gate_aggregates_json, thresholds_json, selected_profiles_json,
            report_json, sample_size, duration_s, actor_external_user_id, actor_email
        )
        VALUES (
            :run_label, :draft_id, :config_fingerprint, :gate_status,
            CAST(:gate_aggregates AS jsonb), CAST(:thresholds AS jsonb),
            CAST(:selected_profiles AS jsonb), CAST(:report AS jsonb),
            :sample_size, :duration_s, :actor_id, :actor_email
        )
        RETURNING {_COLUMNS}
        """
    )
    with engine.begin() as conn:
        row = conn.execute(
            sql,
            {
                "run_label": run_label,
                "draft_id": draft_id,
                "config_fingerprint": config_fingerprint,
                "gate_status": gate_status,
                "gate_aggregates": json.dumps(gate_aggregates),
                "thresholds": json.dumps(thresholds),
                "selected_profiles": json.dumps(selected_profiles),
                "report": json.dumps(report),
                "sample_size": sample_size,
                "duration_s": duration_s,
                "actor_id": actor.user_id if actor else None,
                "actor_email": actor.email if actor else None,
            },
        ).mappings().one()
    return _payload(row)


def get_eval_run(eval_run_id: int, *, include_report: bool = False) -> Optional[dict[str, Any]]:
    with engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT {_COLUMNS} FROM tuning_eval_runs WHERE id = :id"),
            {"id": eval_run_id},
        ).mappings().first()
    return _payload(row, include_report=include_report) if row else None


def list_eval_runs(*, draft_id: Optional[int] = None, limit: int = 50) -> list[dict[str, Any]]:
    clause = "WHERE draft_id = :draft_id" if draft_id is not None else ""
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"SELECT {_COLUMNS} FROM tuning_eval_runs {clause} ORDER BY created_at DESC, id DESC LIMIT :limit"),
            {"draft_id": draft_id, "limit": limit} if draft_id is not None else {"limit": limit},
        ).mappings().all()
    return [_payload(row) for row in rows]


def latest_live_baseline_run() -> Optional[dict[str, Any]]:
    """Most recent eval run of the live configuration (no draft attached)."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                f"""
                SELECT {_COLUMNS} FROM tuning_eval_runs
                WHERE draft_id IS NULL AND run_label = 'live'
                ORDER BY created_at DESC, id DESC LIMIT 1
                """
            )
        ).mappings().first()
    return _payload(row) if row else None
