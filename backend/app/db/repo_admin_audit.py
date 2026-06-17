import json
import hashlib
from typing import Any, Optional

from sqlalchemy import text

from app.auth.context import AuthenticatedUser, get_current_user
from app.db.db import engine


def _jsonable(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value


def _actor_payload(actor: Optional[AuthenticatedUser]) -> dict[str, Any]:
    principal = actor or get_current_user()
    if principal is None:
        return {
            "actor_external_user_id": None,
            "actor_email": None,
            "actor_roles_json": [],
        }
    return {
        "actor_external_user_id": principal.user_id,
        "actor_email": principal.email,
        "actor_roles_json": list(principal.roles),
    }


def _stable_json(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _audit_hash_payload(*, previous_event_hash: Optional[str], values: dict[str, Any]) -> dict[str, Any]:
    return {
        "previous_event_hash": previous_event_hash,
        "event_type": values["event_type"],
        "action": values["action"],
        "outcome": values["outcome"],
        "actor_external_user_id": values["actor_external_user_id"],
        "actor_email": values["actor_email"],
        "actor_roles_json": json.loads(values["actor_roles_json"]),
        "resource_type": values["resource_type"],
        "resource_id": values["resource_id"],
        "resource_name": values["resource_name"],
        "source_id": values["source_id"],
        "corpus_name": values["corpus_name"],
        "profile_type": values["profile_type"],
        "profile_name": values["profile_name"],
        "job_kind": values["job_kind"],
        "job_id": values["job_id"],
        "trace_id": values["trace_id"],
        "request_id": values["request_id"],
        "before_json": json.loads(values["before_json"]),
        "after_json": json.loads(values["after_json"]),
        "event_json": json.loads(values["event_json"]),
    }


def _compute_event_hash(*, previous_event_hash: Optional[str], values: dict[str, Any]) -> str:
    raw = _stable_json(_audit_hash_payload(previous_event_hash=previous_event_hash, values=values))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def insert_admin_audit_event(
    *,
    event_type: str,
    action: str,
    outcome: str = "completed",
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    source_id: Optional[int] = None,
    corpus_name: Optional[str] = None,
    profile_type: Optional[str] = None,
    profile_name: Optional[str] = None,
    job_kind: Optional[str] = None,
    job_id: Optional[int] = None,
    trace_id: Optional[int] = None,
    request_id: Optional[str] = None,
    before_json: Optional[dict[str, Any]] = None,
    after_json: Optional[dict[str, Any]] = None,
    event_json: Optional[dict[str, Any]] = None,
    actor: Optional[AuthenticatedUser] = None,
) -> int:
    actor_payload = _actor_payload(actor)
    sql = text(
        """
        INSERT INTO admin_audit_events (
            event_type, action, outcome,
            actor_external_user_id, actor_email, actor_roles_json,
            resource_type, resource_id, resource_name,
            source_id, corpus_name, profile_type, profile_name,
            job_kind, job_id, trace_id, request_id,
            before_json, after_json, event_json,
            previous_event_hash, event_hash, integrity_metadata_json
        )
        VALUES (
            :event_type, :action, :outcome,
            :actor_external_user_id, :actor_email, CAST(:actor_roles_json AS jsonb),
            :resource_type, :resource_id, :resource_name,
            :source_id, :corpus_name, :profile_type, :profile_name,
            :job_kind, :job_id, :trace_id, :request_id,
            CAST(:before_json AS jsonb), CAST(:after_json AS jsonb), CAST(:event_json AS jsonb),
            :previous_event_hash, :event_hash, CAST(:integrity_metadata_json AS jsonb)
        )
        RETURNING id
        """
    )
    values = {
        "event_type": event_type,
        "action": action,
        "outcome": outcome,
        "actor_external_user_id": actor_payload["actor_external_user_id"],
        "actor_email": actor_payload["actor_email"],
        "actor_roles_json": json.dumps(_jsonable(actor_payload["actor_roles_json"])),
        "resource_type": resource_type,
        "resource_id": resource_id,
        "resource_name": resource_name,
        "source_id": source_id,
        "corpus_name": corpus_name,
        "profile_type": profile_type,
        "profile_name": profile_name,
        "job_kind": job_kind,
        "job_id": job_id,
        "trace_id": trace_id,
        "request_id": request_id,
        "before_json": json.dumps(_jsonable(before_json or {})),
        "after_json": json.dumps(_jsonable(after_json or {})),
        "event_json": json.dumps(_jsonable(event_json or {})),
    }
    with engine.begin() as conn:
        previous_hash = conn.execute(
            text("SELECT event_hash FROM admin_audit_events WHERE event_hash IS NOT NULL ORDER BY id DESC LIMIT 1")
        ).scalar()
        event_hash = _compute_event_hash(previous_event_hash=previous_hash, values=values)
        return conn.execute(
            sql,
            {
                **values,
                "previous_event_hash": previous_hash,
                "event_hash": event_hash,
                "integrity_metadata_json": json.dumps({"algorithm": "sha256", "version": 1}),
            },
        ).scalar_one()


def list_admin_audit_events(
    *,
    limit: int = 50,
    offset: int = 0,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    outcome: Optional[str] = None,
    actor_external_user_id: Optional[str] = None,
    actor_query: Optional[str] = None,
    source_id: Optional[int] = None,
    job_id: Optional[int] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
) -> list[dict[str, Any]]:
    sql = """
        SELECT id, event_type, action, outcome,
               actor_external_user_id, actor_email, actor_roles_json,
               resource_type, resource_id, resource_name,
               source_id, corpus_name, profile_type, profile_name,
               job_kind, job_id, trace_id, request_id,
               before_json, after_json, event_json,
               previous_event_hash, event_hash, integrity_metadata_json, created_at
        FROM admin_audit_events
    """
    filters: list[str] = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if action:
        filters.append("action = :action")
        params["action"] = action
    if resource_type:
        filters.append("resource_type = :resource_type")
        params["resource_type"] = resource_type
    if outcome:
        filters.append("outcome = :outcome")
        params["outcome"] = outcome
    if actor_external_user_id:
        filters.append("actor_external_user_id = :actor_external_user_id")
        params["actor_external_user_id"] = actor_external_user_id
    if actor_query:
        filters.append("(actor_external_user_id ILIKE :actor_query OR actor_email ILIKE :actor_query)")
        params["actor_query"] = f"%{actor_query}%"
    if source_id is not None:
        filters.append("source_id = :source_id")
        params["source_id"] = source_id
    if job_id is not None:
        filters.append("job_id = :job_id")
        params["job_id"] = job_id
    if from_ts:
        filters.append("created_at >= :from_ts")
        params["from_ts"] = from_ts
    if to_ts:
        filters.append("created_at <= :to_ts")
        params["to_ts"] = to_ts
    if filters:
        sql += " WHERE " + " AND ".join(filters)
    sql += " ORDER BY created_at DESC, id DESC LIMIT :limit OFFSET :offset"

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [{key: _jsonable(value) for key, value in dict(row).items()} for row in rows]


def verify_admin_audit_integrity() -> dict[str, Any]:
    sql = text(
        """
        SELECT id, event_type, action, outcome,
               actor_external_user_id, actor_email, actor_roles_json,
               resource_type, resource_id, resource_name,
               source_id, corpus_name, profile_type, profile_name,
               job_kind, job_id, trace_id, request_id,
               before_json, after_json, event_json,
               previous_event_hash, event_hash
        FROM admin_audit_events
        WHERE event_hash IS NOT NULL
        ORDER BY id ASC
        """
    )
    with engine.connect() as conn:
        rows = [dict(row) for row in conn.execute(sql).mappings().all()]
        legacy_count = int(conn.execute(text("SELECT COUNT(*) FROM admin_audit_events WHERE event_hash IS NULL")).scalar() or 0)
    previous_hash = None
    for row in rows:
        values = {
            "event_type": row["event_type"],
            "action": row["action"],
            "outcome": row["outcome"],
            "actor_external_user_id": row["actor_external_user_id"],
            "actor_email": row["actor_email"],
            "actor_roles_json": json.dumps(_jsonable(row["actor_roles_json"] or [])),
            "resource_type": row["resource_type"],
            "resource_id": row["resource_id"],
            "resource_name": row["resource_name"],
            "source_id": row["source_id"],
            "corpus_name": row["corpus_name"],
            "profile_type": row["profile_type"],
            "profile_name": row["profile_name"],
            "job_kind": row["job_kind"],
            "job_id": row["job_id"],
            "trace_id": row["trace_id"],
            "request_id": row["request_id"],
            "before_json": json.dumps(_jsonable(row["before_json"] or {})),
            "after_json": json.dumps(_jsonable(row["after_json"] or {})),
            "event_json": json.dumps(_jsonable(row["event_json"] or {})),
        }
        if row["previous_event_hash"] != previous_hash:
            return {"valid": False, "checked_events": len(rows), "legacy_unhashed_events": legacy_count, "broken_event_id": row["id"], "reason": "previous_hash_mismatch"}
        expected = _compute_event_hash(previous_event_hash=previous_hash, values=values)
        if row["event_hash"] != expected:
            return {"valid": False, "checked_events": len(rows), "legacy_unhashed_events": legacy_count, "broken_event_id": row["id"], "reason": "event_hash_mismatch"}
        previous_hash = row["event_hash"]
    return {"valid": True, "checked_events": len(rows), "legacy_unhashed_events": legacy_count, "latest_event_hash": previous_hash}
