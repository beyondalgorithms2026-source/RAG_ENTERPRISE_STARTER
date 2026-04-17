import json
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
            before_json, after_json, event_json
        )
        VALUES (
            :event_type, :action, :outcome,
            :actor_external_user_id, :actor_email, CAST(:actor_roles_json AS jsonb),
            :resource_type, :resource_id, :resource_name,
            :source_id, :corpus_name, :profile_type, :profile_name,
            :job_kind, :job_id, :trace_id, :request_id,
            CAST(:before_json AS jsonb), CAST(:after_json AS jsonb), CAST(:event_json AS jsonb)
        )
        RETURNING id
        """
    )
    with engine.begin() as conn:
        return conn.execute(
            sql,
            {
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
               before_json, after_json, event_json, created_at
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
