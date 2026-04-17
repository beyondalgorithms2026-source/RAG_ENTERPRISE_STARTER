from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text

from app.auth.context import get_current_user
from app.db.db import engine


@dataclass
class PriorityRequestRow:
    id: int
    job_id: int
    source_id: Optional[int]
    requester_external_user_id: Optional[str]
    requester_email: Optional[str]
    requester_display_name: Optional[str]
    requested_priority: int
    reason: str
    status: str
    review_reason: Optional[str]
    reviewed_by_external_user_id: Optional[str]
    reviewed_by_email: Optional[str]
    created_at: Optional[str]
    reviewed_at: Optional[str]
    expires_at: Optional[str]


def _row_to_request(row) -> PriorityRequestRow:
    return PriorityRequestRow(*row)


def create_priority_request(
    *,
    job_id: int,
    source_id: Optional[int],
    requested_priority: int,
    reason: str,
    expires_in_hours: int = 24,
) -> int:
    actor = get_current_user()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
    sql = text(
        """
        INSERT INTO ingestion_priority_requests (
            job_id, source_id,
            requester_external_user_id, requester_email, requester_display_name,
            requested_priority, reason, status, expires_at
        )
        VALUES (
            :job_id, :source_id,
            :requester_external_user_id, :requester_email, :requester_display_name,
            :requested_priority, :reason, 'submitted', :expires_at
        )
        RETURNING id
        """
    )
    with engine.begin() as conn:
        return conn.execute(
            sql,
            {
                "job_id": job_id,
                "source_id": source_id,
                "requester_external_user_id": actor.user_id if actor else None,
                "requester_email": actor.email if actor else None,
                "requester_display_name": actor.name if actor else None,
                "requested_priority": requested_priority,
                "reason": reason.strip(),
                "expires_at": expires_at,
            },
        ).scalar_one()


def _base_select_sql() -> str:
    return """
        SELECT id, job_id, source_id,
               requester_external_user_id, requester_email, requester_display_name,
               requested_priority, reason, status, review_reason,
               reviewed_by_external_user_id, reviewed_by_email,
               created_at, reviewed_at, expires_at
        FROM ingestion_priority_requests
    """


def get_priority_request(request_id: int) -> Optional[PriorityRequestRow]:
    sql = text(f"{_base_select_sql()} WHERE id = :request_id")
    with engine.connect() as conn:
        row = conn.execute(sql, {"request_id": request_id}).first()
    if not row:
        return None
    return _row_to_request(row)


def get_latest_priority_request_for_job(job_id: int) -> Optional[PriorityRequestRow]:
    sql = text(f"{_base_select_sql()} WHERE job_id = :job_id ORDER BY created_at DESC, id DESC LIMIT 1")
    with engine.connect() as conn:
        row = conn.execute(sql, {"job_id": job_id}).first()
    if not row:
        return None
    return _row_to_request(row)


def list_priority_requests(*, status: Optional[str] = None, limit: int = 100, offset: int = 0) -> list[PriorityRequestRow]:
    sql = _base_select_sql()
    params = {"limit": limit, "offset": offset}
    if status:
        sql += " WHERE status = :status"
        params["status"] = status
    sql += " ORDER BY created_at DESC, id DESC LIMIT :limit OFFSET :offset"
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()
    return [_row_to_request(row) for row in rows]


def expire_stale_priority_requests() -> int:
    sql = text(
        """
        UPDATE ingestion_priority_requests
        SET status = 'expired'
        WHERE status IN ('submitted', 'under_review')
          AND expires_at IS NOT NULL
          AND expires_at < now()
        """
    )
    with engine.begin() as conn:
        result = conn.execute(sql)
    return result.rowcount


def update_priority_request_status(
    request_id: int,
    *,
    status: str,
    review_reason: Optional[str] = None,
) -> bool:
    actor = get_current_user()
    sql = text(
        """
        UPDATE ingestion_priority_requests
        SET status = :status,
            review_reason = :review_reason,
            reviewed_by_external_user_id = :reviewed_by_external_user_id,
            reviewed_by_email = :reviewed_by_email,
            reviewed_at = CASE WHEN :status IN ('approved', 'denied', 'expired') THEN now() ELSE reviewed_at END
        WHERE id = :request_id
        """
    )
    with engine.begin() as conn:
        result = conn.execute(
            sql,
            {
                "request_id": request_id,
                "status": status,
                "review_reason": review_reason,
                "reviewed_by_external_user_id": actor.user_id if actor else None,
                "reviewed_by_email": actor.email if actor else None,
            },
        )
    return result.rowcount > 0
