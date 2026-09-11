import json
from dataclasses import dataclass
from typing import Any

from app.auth.context import AuthenticatedUser
from app.db.db import engine
from sqlalchemy import text


@dataclass
class ToolInvocationRow:
    id: int
    tool_name: str
    status: str
    actor_external_user_id: str | None
    actor_email: str | None
    actor_roles_json: list[str]
    corpus_name: str | None
    request_payload_json: dict[str, Any]
    result_payload_json: dict[str, Any]
    denial_reason: str | None
    approval_request_id: int | None
    created_at: str | None
    completed_at: str | None


@dataclass
class ApprovalRequestRow:
    id: int
    approval_type: str
    status: str
    reason: str
    requester_external_user_id: str | None
    requester_email: str | None
    requester_display_name: str | None
    requested_payload_json: dict[str, Any]
    response_payload_json: dict[str, Any]
    reviewed_by_external_user_id: str | None
    reviewed_by_email: str | None
    review_reason: str | None
    created_at: str | None
    reviewed_at: str | None


@dataclass
class QueryFeedbackRow:
    id: int
    question: str
    feedback_type: str
    rating: str | None
    reason: str
    suggested_source: str | None
    request_id: str | None
    answer_path: str | None
    actor_external_user_id: str | None
    actor_email: str | None
    metadata_json: dict[str, Any]
    created_at: str | None


@dataclass
class NegativeFeedbackEventRow:
    id: int
    question: str
    answer_text: str
    negative_reason: str
    note: str
    request_id: str | None
    answer_path: str | None
    used_chunks_count: int
    actor_external_user_id: str | None
    actor_email: str | None
    citations_json: list[dict[str, Any]]
    cited_source_ids_json: list[int]
    cited_chunk_ids_json: list[int]
    active_profile_snapshot_json: dict[str, Any]
    metadata_json: dict[str, Any]
    created_at: str | None


def _actor_payload(actor: AuthenticatedUser | None) -> dict[str, Any]:
    return {
        "actor_external_user_id": actor.user_id if actor else None,
        "actor_email": actor.email if actor else None,
        "actor_roles_json": json.dumps(list(actor.roles) if actor else []),
    }


def _row_to_tool(row) -> ToolInvocationRow:
    return ToolInvocationRow(
        id=int(row[0]),
        tool_name=str(row[1]),
        status=str(row[2]),
        actor_external_user_id=row[3],
        actor_email=row[4],
        actor_roles_json=row[5] or [],
        corpus_name=row[6],
        request_payload_json=row[7] or {},
        result_payload_json=row[8] or {},
        denial_reason=row[9],
        approval_request_id=int(row[10]) if row[10] is not None else None,
        created_at=str(row[11]) if row[11] is not None else None,
        completed_at=str(row[12]) if row[12] is not None else None,
    )


def create_tool_invocation(
    *,
    tool_name: str,
    status: str,
    actor: AuthenticatedUser | None,
    corpus_name: str | None,
    request_payload_json: dict[str, Any],
    result_payload_json: dict[str, Any] | None = None,
    denial_reason: str | None = None,
    approval_request_id: int | None = None,
) -> int:
    sql = text(
        """
        INSERT INTO tool_invocations (
            tool_name, status, actor_external_user_id, actor_email, actor_roles_json,
            corpus_name, request_payload_json, result_payload_json, denial_reason,
            approval_request_id, completed_at
        )
        VALUES (
            :tool_name, :status, :actor_external_user_id, :actor_email,
            CAST(:actor_roles_json AS jsonb), :corpus_name,
            CAST(:request_payload_json AS jsonb), CAST(:result_payload_json AS jsonb),
            :denial_reason, :approval_request_id,
            CASE WHEN :status IN ('completed', 'denied') THEN now() ELSE NULL END
        )
        RETURNING id
        """
    )
    params = _actor_payload(actor)
    params.update(
        {
            "tool_name": tool_name,
            "status": status,
            "corpus_name": corpus_name,
            "request_payload_json": json.dumps(request_payload_json),
            "result_payload_json": json.dumps(result_payload_json or {}),
            "denial_reason": denial_reason,
            "approval_request_id": approval_request_id,
        }
    )
    with engine.begin() as conn:
        return int(conn.execute(sql, params).scalar_one())


def list_tool_invocations(limit: int = 100) -> list[ToolInvocationRow]:
    sql = text(
        """
        SELECT id, tool_name, status, actor_external_user_id, actor_email, actor_roles_json,
               corpus_name, request_payload_json, result_payload_json, denial_reason,
               approval_request_id, created_at, completed_at
        FROM tool_invocations
        ORDER BY created_at DESC, id DESC
        LIMIT :limit
        """
    )
    with engine.connect() as conn:
        return [_row_to_tool(row) for row in conn.execute(sql, {"limit": limit}).fetchall()]


def _row_to_approval(row) -> ApprovalRequestRow:
    return ApprovalRequestRow(
        id=int(row[0]),
        approval_type=str(row[1]),
        status=str(row[2]),
        reason=str(row[3] or ""),
        requester_external_user_id=row[4],
        requester_email=row[5],
        requester_display_name=row[6],
        requested_payload_json=row[7] or {},
        response_payload_json=row[8] or {},
        reviewed_by_external_user_id=row[9],
        reviewed_by_email=row[10],
        review_reason=row[11],
        created_at=str(row[12]) if row[12] is not None else None,
        reviewed_at=str(row[13]) if row[13] is not None else None,
    )


def create_approval_request(
    *,
    approval_type: str,
    reason: str,
    actor: AuthenticatedUser | None,
    requested_payload_json: dict[str, Any],
    response_payload_json: dict[str, Any] | None = None,
) -> int:
    sql = text(
        """
        INSERT INTO approval_requests (
            approval_type, reason, requester_external_user_id, requester_email,
            requester_display_name, requested_payload_json, response_payload_json
        )
        VALUES (
            :approval_type, :reason, :requester_external_user_id, :requester_email,
            :requester_display_name, CAST(:requested_payload_json AS jsonb),
            CAST(:response_payload_json AS jsonb)
        )
        RETURNING id
        """
    )
    with engine.begin() as conn:
        return int(
            conn.execute(
                sql,
                {
                    "approval_type": approval_type,
                    "reason": reason,
                    "requester_external_user_id": actor.user_id if actor else None,
                    "requester_email": actor.email if actor else None,
                    "requester_display_name": actor.name if actor else None,
                    "requested_payload_json": json.dumps(requested_payload_json),
                    "response_payload_json": json.dumps(response_payload_json or {}),
                },
            ).scalar_one()
        )


def get_approval_request(approval_id: int) -> ApprovalRequestRow | None:
    sql = text(
        """
        SELECT id, approval_type, status, reason, requester_external_user_id, requester_email,
               requester_display_name, requested_payload_json, response_payload_json,
               reviewed_by_external_user_id, reviewed_by_email, review_reason, created_at, reviewed_at
        FROM approval_requests
        WHERE id = :approval_id
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"approval_id": approval_id}).first()
    return _row_to_approval(row) if row else None


def list_approval_requests(
    *, requester_external_user_id: str | None = None, limit: int = 100
) -> list[ApprovalRequestRow]:
    conditions = []
    params: dict[str, Any] = {"limit": limit}
    if requester_external_user_id:
        conditions.append("requester_external_user_id = :requester_external_user_id")
        params["requester_external_user_id"] = requester_external_user_id
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = text(
        f"""
        SELECT id, approval_type, status, reason, requester_external_user_id, requester_email,
               requester_display_name, requested_payload_json, response_payload_json,
               reviewed_by_external_user_id, reviewed_by_email, review_reason, created_at, reviewed_at
        FROM approval_requests
        {where_clause}
        ORDER BY created_at DESC, id DESC
        LIMIT :limit
        """
    )
    with engine.connect() as conn:
        return [_row_to_approval(row) for row in conn.execute(sql, params).fetchall()]


def review_approval_request(
    *,
    approval_id: int,
    status: str,
    review_reason: str,
    reviewer: AuthenticatedUser | None,
) -> ApprovalRequestRow | None:
    sql = text(
        """
        UPDATE approval_requests
        SET status = :status,
            review_reason = :review_reason,
            reviewed_by_external_user_id = :reviewed_by_external_user_id,
            reviewed_by_email = :reviewed_by_email,
            reviewed_at = now()
        WHERE id = :approval_id
        RETURNING id, approval_type, status, reason, requester_external_user_id, requester_email,
                  requester_display_name, requested_payload_json, response_payload_json,
                  reviewed_by_external_user_id, reviewed_by_email, review_reason, created_at, reviewed_at
        """
    )
    with engine.begin() as conn:
        row = conn.execute(
            sql,
            {
                "approval_id": approval_id,
                "status": status,
                "review_reason": review_reason,
                "reviewed_by_external_user_id": reviewer.user_id if reviewer else None,
                "reviewed_by_email": reviewer.email if reviewer else None,
            },
        ).first()
    return _row_to_approval(row) if row else None


def _row_to_feedback(row) -> QueryFeedbackRow:
    return QueryFeedbackRow(
        id=int(row[0]),
        question=str(row[1]),
        feedback_type=str(row[2]),
        rating=row[3],
        reason=str(row[4] or ""),
        suggested_source=row[5],
        request_id=row[6],
        answer_path=row[7],
        actor_external_user_id=row[8],
        actor_email=row[9],
        metadata_json=row[10] or {},
        created_at=str(row[11]) if row[11] is not None else None,
    )


def _row_to_negative_feedback(row) -> NegativeFeedbackEventRow:
    return NegativeFeedbackEventRow(
        id=int(row[0]),
        question=str(row[1]),
        answer_text=str(row[2] or ""),
        negative_reason=str(row[3]),
        note=str(row[4] or ""),
        request_id=row[5],
        answer_path=row[6],
        used_chunks_count=int(row[7] or 0),
        actor_external_user_id=row[8],
        actor_email=row[9],
        citations_json=row[10] or [],
        cited_source_ids_json=row[11] or [],
        cited_chunk_ids_json=row[12] or [],
        active_profile_snapshot_json=row[13] or {},
        metadata_json=row[14] or {},
        created_at=str(row[15]) if row[15] is not None else None,
    )


def create_query_feedback(
    *,
    question: str,
    feedback_type: str,
    rating: str | None,
    reason: str,
    suggested_source: str | None,
    request_id: str | None,
    answer_path: str | None,
    actor: AuthenticatedUser | None,
    metadata_json: dict[str, Any] | None = None,
) -> int:
    sql = text(
        """
        INSERT INTO query_feedback (
            question, feedback_type, rating, reason, suggested_source, request_id,
            answer_path, actor_external_user_id, actor_email, metadata_json
        )
        VALUES (
            :question, :feedback_type, :rating, :reason, :suggested_source, :request_id,
            :answer_path, :actor_external_user_id, :actor_email, CAST(:metadata_json AS jsonb)
        )
        RETURNING id
        """
    )
    with engine.begin() as conn:
        return int(
            conn.execute(
                sql,
                {
                    "question": question,
                    "feedback_type": feedback_type,
                    "rating": rating,
                    "reason": reason,
                    "suggested_source": suggested_source,
                    "request_id": request_id,
                    "answer_path": answer_path,
                    "actor_external_user_id": actor.user_id if actor else None,
                    "actor_email": actor.email if actor else None,
                    "metadata_json": json.dumps(metadata_json or {}),
                },
            ).scalar_one()
        )


def create_negative_feedback_event(
    *,
    question: str,
    answer_text: str,
    negative_reason: str,
    note: str,
    request_id: str | None,
    answer_path: str | None,
    used_chunks_count: int,
    actor: AuthenticatedUser | None,
    citations_json: list[dict[str, Any]],
    cited_source_ids_json: list[int],
    cited_chunk_ids_json: list[int],
    active_profile_snapshot_json: dict[str, Any] | None = None,
    metadata_json: dict[str, Any] | None = None,
) -> int:
    sql = text(
        """
        INSERT INTO negative_feedback_events (
            question, answer_text, negative_reason, note, request_id, answer_path,
            used_chunks_count, actor_external_user_id, actor_email, citations_json,
            cited_source_ids_json, cited_chunk_ids_json, active_profile_snapshot_json,
            metadata_json
        )
        VALUES (
            :question, :answer_text, :negative_reason, :note, :request_id, :answer_path,
            :used_chunks_count, :actor_external_user_id, :actor_email,
            CAST(:citations_json AS jsonb), CAST(:cited_source_ids_json AS jsonb),
            CAST(:cited_chunk_ids_json AS jsonb), CAST(:active_profile_snapshot_json AS jsonb),
            CAST(:metadata_json AS jsonb)
        )
        RETURNING id
        """
    )
    with engine.begin() as conn:
        return int(
            conn.execute(
                sql,
                {
                    "question": question,
                    "answer_text": answer_text,
                    "negative_reason": negative_reason,
                    "note": note,
                    "request_id": request_id,
                    "answer_path": answer_path,
                    "used_chunks_count": max(int(used_chunks_count or 0), 0),
                    "actor_external_user_id": actor.user_id if actor else None,
                    "actor_email": actor.email if actor else None,
                    "citations_json": json.dumps(citations_json or []),
                    "cited_source_ids_json": json.dumps(cited_source_ids_json or []),
                    "cited_chunk_ids_json": json.dumps(cited_chunk_ids_json or []),
                    "active_profile_snapshot_json": json.dumps(active_profile_snapshot_json or {}),
                    "metadata_json": json.dumps(metadata_json or {}),
                },
            ).scalar_one()
        )


def list_query_feedback(limit: int = 100) -> list[QueryFeedbackRow]:
    sql = text(
        """
        SELECT id, question, feedback_type, rating, reason, suggested_source, request_id,
               answer_path, actor_external_user_id, actor_email, metadata_json, created_at
        FROM query_feedback
        ORDER BY created_at DESC, id DESC
        LIMIT :limit
        """
    )
    with engine.connect() as conn:
        return [_row_to_feedback(row) for row in conn.execute(sql, {"limit": limit}).fetchall()]


def list_negative_feedback_events(limit: int = 100) -> list[NegativeFeedbackEventRow]:
    sql = text(
        """
        SELECT id, question, answer_text, negative_reason, note, request_id, answer_path,
               used_chunks_count, actor_external_user_id, actor_email, citations_json,
               cited_source_ids_json, cited_chunk_ids_json, active_profile_snapshot_json,
               metadata_json, created_at
        FROM negative_feedback_events
        ORDER BY created_at DESC, id DESC
        LIMIT :limit
        """
    )
    with engine.connect() as conn:
        return [
            _row_to_negative_feedback(row)
            for row in conn.execute(sql, {"limit": limit}).fetchall()
        ]


def negative_feedback_reason_counts(limit: int = 20) -> list[dict[str, Any]]:
    sql = text(
        """
        SELECT negative_reason, COUNT(*)::bigint AS count, MAX(created_at) AS latest_at
        FROM negative_feedback_events
        GROUP BY negative_reason
        ORDER BY count DESC, latest_at DESC
        LIMIT :limit
        """
    )
    with engine.connect() as conn:
        return [
            {
                "negative_reason": row[0],
                "count": int(row[1]),
                "latest_at": str(row[2]) if row[2] else None,
            }
            for row in conn.execute(sql, {"limit": limit}).fetchall()
        ]


def top_failed_queries(limit: int = 10) -> list[dict[str, Any]]:
    sql = text(
        """
        SELECT question, COUNT(*)::bigint AS count, MAX(created_at) AS latest_at
        FROM query_feedback
        WHERE feedback_type IN ('missing_evidence', 'not_helpful')
           OR answer_path = 'not_found'
        GROUP BY question
        ORDER BY count DESC, latest_at DESC
        LIMIT :limit
        """
    )
    with engine.connect() as conn:
        return [
            {
                "question": row[0],
                "count": int(row[1]),
                "latest_at": str(row[2]) if row[2] else None,
            }
            for row in conn.execute(sql, {"limit": limit}).fetchall()
        ]
