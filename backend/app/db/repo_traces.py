import json
from typing import Any, Optional

from sqlalchemy import text

from app.db.db import engine


def _jsonable(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {key: _jsonable(value) for key, value in dict(row).items()}


def insert_trace(
    *,
    request_id: str,
    question: str,
    requested_mode: Optional[str],
    resolved_mode: str,
    retrieval_path: str,
    candidate_counts: dict,
    fallback_reason: Optional[str],
    answer_path: Optional[str],
    latency_ms: dict,
    score_diagnostics: list,
    trace_json: dict,
    active_profiles: dict,
) -> int:
    sql = """
        INSERT INTO retrieval_traces
            (request_id, question, requested_mode, resolved_mode, retrieval_path,
             candidate_counts, fallback_reason, answer_path, latency_ms,
             score_diagnostics, trace_json, active_profiles)
        VALUES
            (:rid, :q, :rm, :rsm, :rp,
             CAST(:cc AS jsonb), :fr, :ap, CAST(:lm AS jsonb),
             CAST(:sd AS jsonb), CAST(:tj AS jsonb), CAST(:aprof AS jsonb))
        RETURNING id
    """
    with engine.begin() as conn:
        stmt = text(sql).bindparams(
            rid=request_id,
            q=question,
            rm=requested_mode,
            rsm=resolved_mode,
            rp=retrieval_path,
            cc=json.dumps(candidate_counts),
            fr=fallback_reason,
            ap=answer_path,
            lm=json.dumps(latency_ms),
            sd=json.dumps(score_diagnostics),
            tj=json.dumps(trace_json),
            aprof=json.dumps(active_profiles),
        )
        row = conn.execute(stmt).first()
        return row[0]


def get_trace(request_id: str) -> Optional[dict[str, Any]]:
    sql = "SELECT * FROM retrieval_traces WHERE request_id = :rid ORDER BY created_at DESC LIMIT 1"
    with engine.connect() as conn:
        stmt = text(sql).bindparams(rid=request_id)
        row = conn.execute(stmt).mappings().first()
        return _row_to_dict(row) if row else None


def list_traces(limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    sql = """
        SELECT id, request_id, question, requested_mode, resolved_mode, retrieval_path,
               candidate_counts, fallback_reason, answer_path, latency_ms, active_profiles, created_at
        FROM retrieval_traces
        ORDER BY created_at DESC
        LIMIT :lim OFFSET :off
    """
    with engine.connect() as conn:
        stmt = text(sql).bindparams(lim=limit, off=offset)
        rows = conn.execute(stmt).mappings().all()
        return [_row_to_dict(r) for r in rows]


def get_trace_by_id(trace_id: int) -> Optional[dict[str, Any]]:
    sql = "SELECT * FROM retrieval_traces WHERE id = :tid"
    with engine.connect() as conn:
        stmt = text(sql).bindparams(tid=trace_id)
        row = conn.execute(stmt).mappings().first()
        return _row_to_dict(row) if row else None


def update_trace(
    *,
    request_id: str,
    answer_path: Optional[str] = None,
    fallback_reason: Optional[str] = None,
    latency_ms: Optional[dict] = None,
    trace_json: Optional[dict] = None,
    score_diagnostics: Optional[list] = None,
) -> bool:
    assignments: list[str] = []
    params: dict[str, Any] = {"rid": request_id}
    if answer_path is not None:
        assignments.append("answer_path = :ap")
        params["ap"] = answer_path
    if fallback_reason is not None:
        assignments.append("fallback_reason = :fr")
        params["fr"] = fallback_reason
    if latency_ms is not None:
        assignments.append("latency_ms = CAST(:lm AS jsonb)")
        params["lm"] = json.dumps(latency_ms)
    if trace_json is not None:
        assignments.append("trace_json = CAST(:tj AS jsonb)")
        params["tj"] = json.dumps(trace_json)
    if score_diagnostics is not None:
        assignments.append("score_diagnostics = CAST(:sd AS jsonb)")
        params["sd"] = json.dumps(score_diagnostics)
    if not assignments:
        return False

    sql = f"""
        UPDATE retrieval_traces
        SET {", ".join(assignments)}
        WHERE request_id = :rid
    """
    with engine.begin() as conn:
        result = conn.execute(text(sql), params)
        return bool(result.rowcount)
