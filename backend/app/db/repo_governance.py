import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import text

from app.auth.context import AuthenticatedUser
from app.db.db import engine


def _normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", (question or "").strip().lower())


def active_restrictions(actor: Optional[AuthenticatedUser]) -> list[dict[str, Any]]:
    if actor is None:
        return []
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, user_external_user_id, user_email, restriction_type, status,
                       reason, starts_at, expires_at, metadata_json, created_at
                FROM user_governance_restrictions
                WHERE status = 'active'
                  AND (expires_at IS NULL OR expires_at > now())
                  AND (
                    user_external_user_id = :user_id
                    OR lower(COALESCE(user_email, '')) = lower(:email)
                  )
                ORDER BY created_at DESC, id DESC
                """
            ),
            {"user_id": actor.user_id, "email": actor.email or ""},
        ).mappings().all()
    return [_jsonable(dict(row)) for row in rows]


def is_restricted(actor: Optional[AuthenticatedUser], restriction_types: set[str]) -> Optional[dict[str, Any]]:
    for restriction in active_restrictions(actor):
        if str(restriction.get("restriction_type")) in restriction_types:
            return restriction
    return None


def create_restriction(
    *,
    user_external_user_id: Optional[str],
    user_email: Optional[str],
    restriction_type: str,
    reason: str,
    actor: Optional[AuthenticatedUser],
    duration_hours: Optional[int] = None,
    metadata_json: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=duration_hours) if duration_hours else None
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO user_governance_restrictions (
                    user_external_user_id, user_email, restriction_type, reason,
                    expires_at, created_by_external_user_id, created_by_email, metadata_json
                )
                VALUES (
                    :user_id, :email, :restriction_type, :reason, :expires_at,
                    :actor_id, :actor_email, CAST(:metadata_json AS jsonb)
                )
                RETURNING id, user_external_user_id, user_email, restriction_type, status,
                          reason, starts_at, expires_at, metadata_json, created_at
                """
            ),
            {
                "user_id": user_external_user_id,
                "email": user_email,
                "restriction_type": restriction_type,
                "reason": reason,
                "expires_at": expires_at,
                "actor_id": actor.user_id if actor else None,
                "actor_email": actor.email if actor else None,
                "metadata_json": json.dumps(metadata_json or {}),
            },
        ).mappings().one()
        conn.execute(
            text(
                """
                INSERT INTO user_governance_events (
                    user_external_user_id, user_email, action, reason, restriction_id,
                    actor_external_user_id, actor_email, event_json
                )
                VALUES (
                    :user_id, :email, 'restriction.created', :reason, :restriction_id,
                    :actor_id, :actor_email, CAST(:event_json AS jsonb)
                )
                """
            ),
            {
                "user_id": user_external_user_id,
                "email": user_email,
                "reason": reason,
                "restriction_id": row["id"],
                "actor_id": actor.user_id if actor else None,
                "actor_email": actor.email if actor else None,
                "event_json": json.dumps({"restriction_type": restriction_type}),
            },
        )
    return _jsonable(dict(row))


def lift_restriction(restriction_id: int, *, reason: str, actor: Optional[AuthenticatedUser]) -> dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                UPDATE user_governance_restrictions
                SET status = 'lifted',
                    lifted_reason = :reason,
                    lifted_by_external_user_id = :actor_id,
                    lifted_by_email = :actor_email,
                    lifted_at = now()
                WHERE id = :restriction_id
                RETURNING id, user_external_user_id, user_email, restriction_type, status,
                          reason, starts_at, expires_at, metadata_json, created_at
                """
            ),
            {"restriction_id": restriction_id, "reason": reason, "actor_id": actor.user_id if actor else None, "actor_email": actor.email if actor else None},
        ).mappings().first()
        if not row:
            raise ValueError(f"Restriction {restriction_id} not found")
        conn.execute(
            text(
                """
                INSERT INTO user_governance_events (
                    user_external_user_id, user_email, action, reason, restriction_id,
                    actor_external_user_id, actor_email, event_json
                )
                VALUES (
                    :user_id, :email, 'restriction.lifted', :reason, :restriction_id,
                    :actor_id, :actor_email, '{}'::jsonb
                )
                """
            ),
            {
                "user_id": row["user_external_user_id"],
                "email": row["user_email"],
                "reason": reason,
                "restriction_id": restriction_id,
                "actor_id": actor.user_id if actor else None,
                "actor_email": actor.email if actor else None,
            },
        )
    return _jsonable(dict(row))


def create_risk_signal(
    *,
    requester_external_user_id: Optional[str],
    requester_email: Optional[str],
    signal_type: str,
    severity: str,
    question: Optional[str],
    access_request_id: Optional[int],
    evidence_json: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO access_request_risk_signals (
                    requester_external_user_id, requester_email, signal_type, severity,
                    question, access_request_id, evidence_json
                )
                VALUES (
                    :user_id, :email, :signal_type, :severity, :question,
                    :access_request_id, CAST(:evidence_json AS jsonb)
                )
                RETURNING id, requester_external_user_id, requester_email, signal_type,
                          severity, question, access_request_id, evidence_json, status, created_at
                """
            ),
            {
                "user_id": requester_external_user_id,
                "email": requester_email,
                "signal_type": signal_type,
                "severity": severity,
                "question": question,
                "access_request_id": access_request_id,
                "evidence_json": json.dumps(evidence_json or {}),
            },
        ).mappings().one()
    return _jsonable(dict(row))


def evaluate_access_request_risk(*, actor: Optional[AuthenticatedUser], question: str, suggested_approver_email: Optional[str] = None) -> list[dict[str, Any]]:
    if actor is None:
        return []
    normalized = _normalize_question(question)
    with engine.connect() as conn:
        repeat_count = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM access_requests
                    WHERE requester_external_user_id = :user_id
                      AND lower(regexp_replace(question, '\\s+', ' ', 'g')) = :normalized
                      AND created_at > now() - interval '7 days'
                    """
                ),
                {"user_id": actor.user_id, "normalized": normalized},
            ).scalar_one()
        )
        approver_count = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(DISTINCT lower(COALESCE(metadata_json->>'suggested_approver_email', '')))
                    FROM access_requests
                    WHERE requester_external_user_id = :user_id
                      AND lower(regexp_replace(question, '\\s+', ' ', 'g')) = :normalized
                      AND created_at > now() - interval '14 days'
                    """
                ),
                {"user_id": actor.user_id, "normalized": normalized},
            ).scalar_one()
        )
    signals: list[dict[str, Any]] = []
    if repeat_count >= 2:
        signals.append(
            create_risk_signal(
                requester_external_user_id=actor.user_id,
                requester_email=actor.email,
                signal_type="repeated_similar_request",
                severity="warning",
                question=question,
                access_request_id=None,
                evidence_json={"repeat_count_7d": repeat_count},
            )
        )
    if suggested_approver_email and approver_count >= 2:
        signals.append(
            create_risk_signal(
                requester_external_user_id=actor.user_id,
                requester_email=actor.email,
                signal_type="approver_swapping",
                severity="warning",
                question=question,
                access_request_id=None,
                evidence_json={"distinct_suggested_approvers_14d": approver_count},
            )
        )
    return signals


def list_risk_signals(limit: int = 100) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, requester_external_user_id, requester_email, signal_type,
                       severity, question, access_request_id, evidence_json, status, created_at
                FROM access_request_risk_signals
                ORDER BY created_at DESC, id DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
    return [_jsonable(dict(row)) for row in rows]


def list_restrictions(limit: int = 100) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, user_external_user_id, user_email, restriction_type, status,
                       reason, starts_at, expires_at, metadata_json, created_at
                FROM user_governance_restrictions
                ORDER BY created_at DESC, id DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
    return [_jsonable(dict(row)) for row in rows]


def _jsonable(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
