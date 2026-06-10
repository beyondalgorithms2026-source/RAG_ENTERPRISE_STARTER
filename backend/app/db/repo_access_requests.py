import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.auth.context import AuthenticatedUser
from app.db.db import engine
from app.db.repo_sources import get_source_by_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_email(value: Optional[str]) -> Optional[str]:
    cleaned = (value or "").strip().lower()
    return cleaned or None


def _json(value: Optional[Dict[str, Any]]) -> str:
    return json.dumps(value or {})


@dataclass
class SourceAccessContactRow:
    id: int
    source_id: int
    contact_role: str
    contact_external_user_id: Optional[str]
    contact_email: Optional[str]
    contact_display_name: Optional[str]
    contact_metadata_json: Dict[str, Any]
    created_at: Optional[str]
    updated_at: Optional[str]


@dataclass
class AccessRequestRow:
    id: int
    status: str
    question: str
    business_reason: str
    source_hint: Optional[str]
    request_id: Optional[str]
    answer_path: Optional[str]
    requester_external_user_id: Optional[str]
    requester_email: Optional[str]
    requester_display_name: Optional[str]
    requester_manager_external_user_id: Optional[str]
    requester_manager_email: Optional[str]
    requester_manager_display_name: Optional[str]
    approved_duration_hours: Optional[int]
    business_approval_status: Optional[str]
    business_approval_decision: Optional[str]
    business_approval_reason: Optional[str]
    business_approved_at: Optional[str]
    granted_at: Optional[str]
    expires_at: Optional[str]
    granted_by_external_user_id: Optional[str]
    granted_by_email: Optional[str]
    review_reason: Optional[str]
    metadata_json: Dict[str, Any]
    created_at: Optional[str]
    updated_at: Optional[str]


@dataclass
class AccessRequestTargetRow:
    id: int
    access_request_id: int
    source_id: int
    status: str
    mapped_by_external_user_id: Optional[str]
    mapped_by_email: Optional[str]
    created_at: Optional[str]


@dataclass
class AccessRequestRoutingRow:
    id: int
    access_request_id: int
    admin_coordinator_external_user_id: Optional[str]
    admin_coordinator_email: Optional[str]
    business_approver_external_user_id: Optional[str]
    business_approver_email: Optional[str]
    business_approver_display_name: Optional[str]
    acl_manager_external_user_id: Optional[str]
    acl_manager_email: Optional[str]
    acl_manager_display_name: Optional[str]
    requester_manager_external_user_id: Optional[str]
    requester_manager_email: Optional[str]
    requester_manager_display_name: Optional[str]
    routed_at: Optional[str]
    responded_at: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


@dataclass
class ApprovalInboxItemRow:
    id: int
    access_request_id: int
    routing_id: Optional[int]
    assigned_external_user_id: Optional[str]
    assigned_email: Optional[str]
    assigned_display_name: Optional[str]
    status: str
    decision: Optional[str]
    decision_reason: Optional[str]
    request_payload_json: Dict[str, Any]
    resolution_payload_json: Dict[str, Any]
    created_at: Optional[str]
    decided_at: Optional[str]


@dataclass
class NotificationEventRow:
    id: int
    access_request_id: Optional[int]
    event_type: str
    recipient_external_user_id: Optional[str]
    recipient_email: Optional[str]
    recipient_display_name: Optional[str]
    recipient_role: Optional[str]
    title: str
    body: str
    email_subject: Optional[str]
    email_payload_json: Dict[str, Any]
    payload_json: Dict[str, Any]
    status: str
    created_at: Optional[str]
    read_at: Optional[str]


def _row_to_contact(row) -> SourceAccessContactRow:
    return SourceAccessContactRow(
        id=int(row[0]),
        source_id=int(row[1]),
        contact_role=str(row[2]),
        contact_external_user_id=row[3],
        contact_email=row[4],
        contact_display_name=row[5],
        contact_metadata_json=row[6] or {},
        created_at=str(row[7]) if row[7] is not None else None,
        updated_at=str(row[8]) if row[8] is not None else None,
    )


def _row_to_access_request(row) -> AccessRequestRow:
    return AccessRequestRow(
        id=int(row[0]),
        status=str(row[1]),
        question=str(row[2]),
        business_reason=str(row[3] or ""),
        source_hint=row[4],
        request_id=row[5],
        answer_path=row[6],
        requester_external_user_id=row[7],
        requester_email=row[8],
        requester_display_name=row[9],
        requester_manager_external_user_id=row[10],
        requester_manager_email=row[11],
        requester_manager_display_name=row[12],
        approved_duration_hours=int(row[13]) if row[13] is not None else None,
        business_approval_status=row[14],
        business_approval_decision=row[15],
        business_approval_reason=row[16],
        business_approved_at=str(row[17]) if row[17] is not None else None,
        granted_at=str(row[18]) if row[18] is not None else None,
        expires_at=str(row[19]) if row[19] is not None else None,
        granted_by_external_user_id=row[20],
        granted_by_email=row[21],
        review_reason=row[22],
        metadata_json=row[23] or {},
        created_at=str(row[24]) if row[24] is not None else None,
        updated_at=str(row[25]) if row[25] is not None else None,
    )


def _row_to_target(row) -> AccessRequestTargetRow:
    return AccessRequestTargetRow(
        id=int(row[0]),
        access_request_id=int(row[1]),
        source_id=int(row[2]),
        status=str(row[3]),
        mapped_by_external_user_id=row[4],
        mapped_by_email=row[5],
        created_at=str(row[6]) if row[6] is not None else None,
    )


def _row_to_routing(row) -> AccessRequestRoutingRow:
    return AccessRequestRoutingRow(
        id=int(row[0]),
        access_request_id=int(row[1]),
        admin_coordinator_external_user_id=row[2],
        admin_coordinator_email=row[3],
        business_approver_external_user_id=row[4],
        business_approver_email=row[5],
        business_approver_display_name=row[6],
        acl_manager_external_user_id=row[7],
        acl_manager_email=row[8],
        acl_manager_display_name=row[9],
        requester_manager_external_user_id=row[10],
        requester_manager_email=row[11],
        requester_manager_display_name=row[12],
        routed_at=str(row[13]) if row[13] is not None else None,
        responded_at=str(row[14]) if row[14] is not None else None,
        created_at=str(row[15]) if row[15] is not None else None,
        updated_at=str(row[16]) if row[16] is not None else None,
    )


def _row_to_inbox(row) -> ApprovalInboxItemRow:
    return ApprovalInboxItemRow(
        id=int(row[0]),
        access_request_id=int(row[1]),
        routing_id=int(row[2]) if row[2] is not None else None,
        assigned_external_user_id=row[3],
        assigned_email=row[4],
        assigned_display_name=row[5],
        status=str(row[6]),
        decision=row[7],
        decision_reason=row[8],
        request_payload_json=row[9] or {},
        resolution_payload_json=row[10] or {},
        created_at=str(row[11]) if row[11] is not None else None,
        decided_at=str(row[12]) if row[12] is not None else None,
    )


def _row_to_notification(row) -> NotificationEventRow:
    return NotificationEventRow(
        id=int(row[0]),
        access_request_id=int(row[1]) if row[1] is not None else None,
        event_type=str(row[2]),
        recipient_external_user_id=row[3],
        recipient_email=row[4],
        recipient_display_name=row[5],
        recipient_role=row[6],
        title=str(row[7]),
        body=str(row[8]),
        email_subject=row[9],
        email_payload_json=row[10] or {},
        payload_json=row[11] or {},
        status=str(row[12]),
        created_at=str(row[13]) if row[13] is not None else None,
        read_at=str(row[14]) if row[14] is not None else None,
    )


def _manager_fields(actor: Optional[AuthenticatedUser]) -> dict[str, Optional[str]]:
    claims = (actor.raw_claims if actor else {}) or {}
    return {
        "requester_manager_external_user_id": str(
            claims.get("manager_external_user_id") or claims.get("manager_id") or ""
        ).strip()
        or None,
        "requester_manager_email": _normalize_email(
            claims.get("manager_email") or claims.get("managerEmail") or claims.get("manager_mail")
        ),
        "requester_manager_display_name": str(
            claims.get("manager_display_name") or claims.get("manager_name") or ""
        ).strip()
        or None,
    }


def _normalize_requester_manager(payload: Optional[Dict[str, Optional[str]]], actor: Optional[AuthenticatedUser]) -> dict[str, Optional[str]]:
    if not payload:
        return _manager_fields(actor)
    return {
        "requester_manager_external_user_id": (
            payload.get("requester_manager_external_user_id")
            or payload.get("contact_external_user_id")
            or payload.get("external_user_id")
        ),
        "requester_manager_email": _normalize_email(
            payload.get("requester_manager_email")
            or payload.get("contact_email")
            or payload.get("email")
        ),
        "requester_manager_display_name": (
            payload.get("requester_manager_display_name")
            or payload.get("contact_display_name")
            or payload.get("display_name")
            or payload.get("name")
        ),
    }


def list_source_access_contacts(source_id: int) -> List[SourceAccessContactRow]:
    sql = text(
        """
        SELECT id, source_id, contact_role, contact_external_user_id, contact_email, contact_display_name,
               contact_metadata_json, created_at, updated_at
        FROM source_access_contacts
        WHERE source_id = :source_id
        ORDER BY contact_role ASC, created_at ASC
        """
    )
    with engine.connect() as conn:
        return [_row_to_contact(row) for row in conn.execute(sql, {"source_id": source_id}).fetchall()]


def upsert_source_access_contacts(source_id: int, contacts: List[dict[str, Any]]) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM source_access_contacts WHERE source_id = :source_id"), {"source_id": source_id})
        for contact in contacts:
            role = str(contact.get("contact_role") or "").strip().lower()
            email = _normalize_email(contact.get("contact_email"))
            if not role or not email:
                continue
            conn.execute(
                text(
                    """
                    INSERT INTO source_access_contacts (
                        source_id, contact_role, contact_external_user_id, contact_email, contact_display_name, contact_metadata_json
                    )
                    VALUES (
                        :source_id, :contact_role, :contact_external_user_id, :contact_email, :contact_display_name, CAST(:contact_metadata_json AS jsonb)
                    )
                    """
                ),
                {
                    "source_id": source_id,
                    "contact_role": role,
                    "contact_external_user_id": contact.get("contact_external_user_id"),
                    "contact_email": email,
                    "contact_display_name": contact.get("contact_display_name"),
                    "contact_metadata_json": _json(contact.get("contact_metadata_json")),
                },
            )


def resolve_source_contacts(source_id: int) -> dict[str, Optional[dict[str, Any]]]:
    rows = list_source_access_contacts(source_id)
    contacts: dict[str, Optional[dict[str, Any]]] = {"business_approver": None, "acl_manager": None}
    for row in rows:
        if row.contact_role in contacts and contacts[row.contact_role] is None:
            contacts[row.contact_role] = row.__dict__
    if all(contacts.values()):
        return contacts

    source = get_source_by_id(source_id)
    source_metadata = source.source_metadata_json if source else {}
    raw_contacts = source_metadata.get("access_contacts")
    if isinstance(raw_contacts, list):
        for item in raw_contacts:
            if not isinstance(item, dict):
                continue
            role = str(item.get("contact_role") or item.get("role") or "").strip().lower()
            if role in contacts and contacts[role] is None and item.get("contact_email"):
                contacts[role] = {
                    "contact_role": role,
                    "contact_external_user_id": item.get("contact_external_user_id"),
                    "contact_email": _normalize_email(item.get("contact_email")),
                    "contact_display_name": item.get("contact_display_name"),
                    "contact_metadata_json": item.get("contact_metadata_json") or {},
                }
    return contacts


def create_access_request(
    *,
    question: str,
    business_reason: str,
    source_hint: Optional[str],
    request_id: Optional[str],
    answer_path: Optional[str],
    actor: Optional[AuthenticatedUser],
    requester_manager: Optional[Dict[str, Optional[str]]] = None,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> AccessRequestRow:
    manager = _normalize_requester_manager(requester_manager, actor)
    sql = text(
        """
        INSERT INTO access_requests (
            status, question, business_reason, source_hint, request_id, answer_path,
            requester_external_user_id, requester_email, requester_display_name,
            requester_manager_external_user_id, requester_manager_email, requester_manager_display_name,
            metadata_json
        )
        VALUES (
            'submitted', :question, :business_reason, :source_hint, :request_id, :answer_path,
            :requester_external_user_id, :requester_email, :requester_display_name,
            :requester_manager_external_user_id, :requester_manager_email, :requester_manager_display_name,
            CAST(:metadata_json AS jsonb)
        )
        RETURNING id, status, question, business_reason, source_hint, request_id, answer_path,
                  requester_external_user_id, requester_email, requester_display_name,
                  requester_manager_external_user_id, requester_manager_email, requester_manager_display_name,
                  approved_duration_hours, business_approval_status, business_approval_decision,
                  business_approval_reason, business_approved_at, granted_at, expires_at,
                  granted_by_external_user_id, granted_by_email, review_reason, metadata_json, created_at, updated_at
        """
    )
    with engine.begin() as conn:
        row = conn.execute(
            sql,
            {
                "question": question,
                "business_reason": business_reason,
                "source_hint": source_hint,
                "request_id": request_id,
                "answer_path": answer_path,
                "requester_external_user_id": actor.user_id if actor else None,
                "requester_email": actor.email if actor else None,
                "requester_display_name": actor.name if actor else None,
                "requester_manager_external_user_id": manager["requester_manager_external_user_id"],
                "requester_manager_email": manager["requester_manager_email"],
                "requester_manager_display_name": manager["requester_manager_display_name"],
                "metadata_json": _json(metadata_json),
            },
        ).first()
    return _row_to_access_request(row)


def get_access_request(access_request_id: int) -> Optional[AccessRequestRow]:
    sql = text(
        """
        SELECT id, status, question, business_reason, source_hint, request_id, answer_path,
               requester_external_user_id, requester_email, requester_display_name,
               requester_manager_external_user_id, requester_manager_email, requester_manager_display_name,
               approved_duration_hours, business_approval_status, business_approval_decision,
               business_approval_reason, business_approved_at, granted_at, expires_at,
               granted_by_external_user_id, granted_by_email, review_reason, metadata_json, created_at, updated_at
        FROM access_requests
        WHERE id = :access_request_id
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"access_request_id": access_request_id}).first()
    return _row_to_access_request(row) if row else None


def list_access_requests(
    *,
    requester_external_user_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    statuses: Optional[List[str]] = None,
    limit: int = 200,
) -> List[AccessRequestRow]:
    filters = []
    params: Dict[str, Any] = {"limit": limit}
    if requester_external_user_id:
        filters.append("requester_external_user_id = :requester_external_user_id")
        params["requester_external_user_id"] = requester_external_user_id
    elif actor_email:
        filters.append("LOWER(COALESCE(requester_email, '')) = :actor_email")
        params["actor_email"] = actor_email.lower()
    if statuses:
        filters.append("status = ANY(:statuses)")
        params["statuses"] = list(statuses)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    sql = text(
        f"""
        SELECT id, status, question, business_reason, source_hint, request_id, answer_path,
               requester_external_user_id, requester_email, requester_display_name,
               requester_manager_external_user_id, requester_manager_email, requester_manager_display_name,
               approved_duration_hours, business_approval_status, business_approval_decision,
               business_approval_reason, business_approved_at, granted_at, expires_at,
               granted_by_external_user_id, granted_by_email, review_reason, metadata_json, created_at, updated_at
        FROM access_requests
        {where_clause}
        ORDER BY created_at DESC, id DESC
        LIMIT :limit
        """
    )
    with engine.connect() as conn:
        return [_row_to_access_request(row) for row in conn.execute(sql, params).fetchall()]


def list_access_request_targets(access_request_id: int) -> List[AccessRequestTargetRow]:
    sql = text(
        """
        SELECT id, access_request_id, source_id, status, mapped_by_external_user_id, mapped_by_email, created_at
        FROM access_request_targets
        WHERE access_request_id = :access_request_id
        ORDER BY id ASC
        """
    )
    with engine.connect() as conn:
        return [_row_to_target(row) for row in conn.execute(sql, {"access_request_id": access_request_id}).fetchall()]


def get_access_request_routing(access_request_id: int) -> Optional[AccessRequestRoutingRow]:
    sql = text(
        """
        SELECT id, access_request_id, admin_coordinator_external_user_id, admin_coordinator_email,
               business_approver_external_user_id, business_approver_email, business_approver_display_name,
               acl_manager_external_user_id, acl_manager_email, acl_manager_display_name,
               requester_manager_external_user_id, requester_manager_email, requester_manager_display_name,
               routed_at, responded_at, created_at, updated_at
        FROM access_request_routing
        WHERE access_request_id = :access_request_id
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"access_request_id": access_request_id}).first()
    return _row_to_routing(row) if row else None


def create_notification_event(
    *,
    access_request_id: Optional[int],
    event_type: str,
    recipient_external_user_id: Optional[str],
    recipient_email: Optional[str],
    recipient_display_name: Optional[str],
    recipient_role: Optional[str],
    title: str,
    body: str,
    email_subject: Optional[str],
    email_payload_json: Optional[Dict[str, Any]],
    payload_json: Optional[Dict[str, Any]],
) -> int:
    sql = text(
        """
        INSERT INTO notification_events (
            access_request_id, event_type, recipient_external_user_id, recipient_email, recipient_display_name,
            recipient_role, title, body, email_subject, email_payload_json, payload_json
        )
        VALUES (
            :access_request_id, :event_type, :recipient_external_user_id, :recipient_email, :recipient_display_name,
            :recipient_role, :title, :body, :email_subject, CAST(:email_payload_json AS jsonb), CAST(:payload_json AS jsonb)
        )
        RETURNING id
        """
    )
    with engine.begin() as conn:
        return int(
            conn.execute(
                sql,
                {
                    "access_request_id": access_request_id,
                    "event_type": event_type,
                    "recipient_external_user_id": recipient_external_user_id,
                    "recipient_email": _normalize_email(recipient_email),
                    "recipient_display_name": recipient_display_name,
                    "recipient_role": recipient_role,
                    "title": title,
                    "body": body,
                    "email_subject": email_subject,
                    "email_payload_json": _json(email_payload_json),
                    "payload_json": _json(payload_json),
                },
            ).scalar_one()
        )


def list_notification_events(*, actor: Optional[AuthenticatedUser], limit: int = 100) -> List[NotificationEventRow]:
    if actor is None:
        return []
    sql = text(
        """
        SELECT id, access_request_id, event_type, recipient_external_user_id, recipient_email,
               recipient_display_name, recipient_role, title, body, email_subject,
               email_payload_json, payload_json, status, created_at, read_at
        FROM notification_events
        WHERE recipient_external_user_id = :actor_user_id
           OR LOWER(COALESCE(recipient_email, '')) = :actor_email
        ORDER BY created_at DESC, id DESC
        LIMIT :limit
        """
    )
    with engine.connect() as conn:
        return [
            _row_to_notification(row)
            for row in conn.execute(
                sql,
                {"actor_user_id": actor.user_id, "actor_email": _normalize_email(actor.email) or "", "limit": limit},
            ).fetchall()
        ]


def mark_notification_read(notification_id: int, actor: Optional[AuthenticatedUser]) -> bool:
    if actor is None:
        return False
    sql = text(
        """
        UPDATE notification_events
        SET status = 'read', read_at = now()
        WHERE id = :notification_id
          AND (recipient_external_user_id = :actor_user_id OR LOWER(COALESCE(recipient_email, '')) = :actor_email)
        """
    )
    with engine.begin() as conn:
        result = conn.execute(
            sql,
            {"notification_id": notification_id, "actor_user_id": actor.user_id, "actor_email": _normalize_email(actor.email) or ""},
        )
    return result.rowcount > 0


def list_inbox_items(*, actor: Optional[AuthenticatedUser], limit: int = 100) -> List[ApprovalInboxItemRow]:
    if actor is None:
        return []
    sql = text(
        """
        SELECT id, access_request_id, routing_id, assigned_external_user_id, assigned_email, assigned_display_name,
               status, decision, decision_reason, request_payload_json, resolution_payload_json, created_at, decided_at
        FROM approval_inbox_items
        WHERE assigned_external_user_id = :actor_user_id
           OR LOWER(COALESCE(assigned_email, '')) = :actor_email
        ORDER BY created_at DESC, id DESC
        LIMIT :limit
        """
    )
    with engine.connect() as conn:
        return [
            _row_to_inbox(row)
            for row in conn.execute(
                sql,
                {"actor_user_id": actor.user_id, "actor_email": _normalize_email(actor.email) or "", "limit": limit},
            ).fetchall()
        ]


def _create_inbox_item(
    *,
    access_request_id: int,
    routing_id: int,
    assigned_external_user_id: Optional[str],
    assigned_email: Optional[str],
    assigned_display_name: Optional[str],
    request_payload_json: Optional[Dict[str, Any]],
) -> int:
    sql = text(
        """
        INSERT INTO approval_inbox_items (
            access_request_id, routing_id, assigned_external_user_id, assigned_email, assigned_display_name, request_payload_json
        )
        VALUES (
            :access_request_id, :routing_id, :assigned_external_user_id, :assigned_email, :assigned_display_name, CAST(:request_payload_json AS jsonb)
        )
        RETURNING id
        """
    )
    with engine.begin() as conn:
        return int(
            conn.execute(
                sql,
                {
                    "access_request_id": access_request_id,
                    "routing_id": routing_id,
                    "assigned_external_user_id": assigned_external_user_id,
                    "assigned_email": _normalize_email(assigned_email),
                    "assigned_display_name": assigned_display_name,
                    "request_payload_json": _json(request_payload_json),
                },
            ).scalar_one()
        )


def route_access_request(
    *,
    access_request_id: int,
    source_ids: List[int],
    admin_actor: Optional[AuthenticatedUser],
    business_approver: Dict[str, Optional[str]],
    acl_manager: Optional[Dict[str, Optional[str]]],
    requester_manager: Optional[Dict[str, Optional[str]]],
    fallback_requester_manager: Optional[Dict[str, Optional[str]]] = None,
    review_reason: str = "",
) -> Optional[AccessRequestRow]:
    access_request = get_access_request(access_request_id)
    if access_request is None:
        return None
    resolved_requester_manager = requester_manager or fallback_requester_manager or {
        "contact_external_user_id": access_request.requester_manager_external_user_id,
        "contact_email": access_request.requester_manager_email,
        "contact_display_name": access_request.requester_manager_display_name,
    }
    with engine.begin() as conn:
        next_source_ids = sorted({int(item) for item in source_ids if item is not None})
        if next_source_ids:
            conn.execute(text("DELETE FROM access_request_targets WHERE access_request_id = :access_request_id"), {"access_request_id": access_request_id})
            for source_id in next_source_ids:
                conn.execute(
                    text(
                        """
                        INSERT INTO access_request_targets (access_request_id, source_id, status, mapped_by_external_user_id, mapped_by_email)
                        VALUES (:access_request_id, :source_id, 'mapped', :mapped_by_external_user_id, :mapped_by_email)
                        """
                    ),
                    {
                        "access_request_id": access_request_id,
                        "source_id": source_id,
                        "mapped_by_external_user_id": admin_actor.user_id if admin_actor else None,
                        "mapped_by_email": admin_actor.email if admin_actor else None,
                    },
                )
        routing_row = conn.execute(
            text(
                """
                INSERT INTO access_request_routing (
                    access_request_id, admin_coordinator_external_user_id, admin_coordinator_email,
                    business_approver_external_user_id, business_approver_email, business_approver_display_name,
                    acl_manager_external_user_id, acl_manager_email, acl_manager_display_name,
                    requester_manager_external_user_id, requester_manager_email, requester_manager_display_name,
                    routed_at, updated_at
                )
                VALUES (
                    :access_request_id, :admin_coordinator_external_user_id, :admin_coordinator_email,
                    :business_approver_external_user_id, :business_approver_email, :business_approver_display_name,
                    :acl_manager_external_user_id, :acl_manager_email, :acl_manager_display_name,
                    :requester_manager_external_user_id, :requester_manager_email, :requester_manager_display_name,
                    now(), now()
                )
                ON CONFLICT (access_request_id) DO UPDATE
                SET admin_coordinator_external_user_id = EXCLUDED.admin_coordinator_external_user_id,
                    admin_coordinator_email = EXCLUDED.admin_coordinator_email,
                    business_approver_external_user_id = EXCLUDED.business_approver_external_user_id,
                    business_approver_email = EXCLUDED.business_approver_email,
                    business_approver_display_name = EXCLUDED.business_approver_display_name,
                    acl_manager_external_user_id = EXCLUDED.acl_manager_external_user_id,
                    acl_manager_email = EXCLUDED.acl_manager_email,
                    acl_manager_display_name = EXCLUDED.acl_manager_display_name,
                    requester_manager_external_user_id = EXCLUDED.requester_manager_external_user_id,
                    requester_manager_email = EXCLUDED.requester_manager_email,
                    requester_manager_display_name = EXCLUDED.requester_manager_display_name,
                    routed_at = now(),
                    updated_at = now()
                RETURNING id
                """
            ),
            {
                "access_request_id": access_request_id,
                "admin_coordinator_external_user_id": admin_actor.user_id if admin_actor else None,
                "admin_coordinator_email": admin_actor.email if admin_actor else None,
                "business_approver_external_user_id": business_approver.get("contact_external_user_id"),
                "business_approver_email": _normalize_email(business_approver.get("contact_email")),
                "business_approver_display_name": business_approver.get("contact_display_name"),
                "acl_manager_external_user_id": (acl_manager or {}).get("contact_external_user_id"),
                "acl_manager_email": _normalize_email((acl_manager or {}).get("contact_email")),
                "acl_manager_display_name": (acl_manager or {}).get("contact_display_name"),
                "requester_manager_external_user_id": resolved_requester_manager.get("contact_external_user_id"),
                "requester_manager_email": _normalize_email(resolved_requester_manager.get("contact_email")),
                "requester_manager_display_name": resolved_requester_manager.get("contact_display_name"),
            },
        ).first()
        row = conn.execute(
            text(
                """
                UPDATE access_requests
                SET status = 'awaiting_business_approval',
                    business_approval_status = 'pending',
                    review_reason = :review_reason,
                    requester_manager_external_user_id = COALESCE(:requester_manager_external_user_id, requester_manager_external_user_id),
                    requester_manager_email = COALESCE(:requester_manager_email, requester_manager_email),
                    requester_manager_display_name = COALESCE(:requester_manager_display_name, requester_manager_display_name),
                    updated_at = now()
                WHERE id = :access_request_id
                RETURNING id, status, question, business_reason, source_hint, request_id, answer_path,
                          requester_external_user_id, requester_email, requester_display_name,
                          requester_manager_external_user_id, requester_manager_email, requester_manager_display_name,
                          approved_duration_hours, business_approval_status, business_approval_decision,
                          business_approval_reason, business_approved_at, granted_at, expires_at,
                          granted_by_external_user_id, granted_by_email, review_reason, metadata_json, created_at, updated_at
                """
            ),
            {
                "access_request_id": access_request_id,
                "review_reason": review_reason,
                "requester_manager_external_user_id": resolved_requester_manager.get("contact_external_user_id"),
                "requester_manager_email": _normalize_email(resolved_requester_manager.get("contact_email")),
                "requester_manager_display_name": resolved_requester_manager.get("contact_display_name"),
            },
        ).first()

    targets = [target.source_id for target in list_access_request_targets(access_request_id)]
    _create_inbox_item(
        access_request_id=access_request_id,
        routing_id=int(routing_row[0]),
        assigned_external_user_id=business_approver.get("contact_external_user_id"),
        assigned_email=business_approver.get("contact_email"),
        assigned_display_name=business_approver.get("contact_display_name"),
        request_payload_json={
            "source_ids": targets,
            "review_reason": review_reason,
            "question": access_request.question,
            "business_reason": access_request.business_reason,
            "source_hint": access_request.source_hint,
            "requester_email": access_request.requester_email,
            "requester_display_name": access_request.requester_display_name,
            "requester_manager_email": access_request.requester_manager_email,
            "suggested_approver_email": (access_request.metadata_json or {}).get("suggested_approver_email"),
            "suggested_approver_display_name": (access_request.metadata_json or {}).get("suggested_approver_display_name"),
            "admin_note": review_reason,
        },
    )
    recipients = [
        ("business_approver", business_approver),
        ("acl_manager_observer", acl_manager or {}),
        ("requester_manager_observer", resolved_requester_manager or {}),
        (
            "requester",
            {
                "contact_external_user_id": access_request.requester_external_user_id,
                "contact_email": access_request.requester_email,
                "contact_display_name": access_request.requester_display_name,
            },
        ),
    ]
    for role, contact in recipients:
        if not contact.get("contact_email") and not contact.get("contact_external_user_id"):
            continue
        create_notification_event(
            access_request_id=access_request_id,
            event_type="access_request_routed",
            recipient_external_user_id=contact.get("contact_external_user_id"),
            recipient_email=contact.get("contact_email"),
            recipient_display_name=contact.get("contact_display_name"),
            recipient_role=role,
            title="Access request routed for review" if role == "business_approver" else "Access request update",
            body=f"Access request #{access_request_id} is awaiting business approval.",
            email_subject=f"Access request #{access_request_id} routed",
            email_payload_json={"request_id": access_request_id, "role": role},
            payload_json={"request_id": access_request_id, "source_ids": targets},
        )
    return _row_to_access_request(row)


def decide_inbox_item(
    *,
    inbox_item_id: int,
    actor: Optional[AuthenticatedUser],
    decision: str,
    decision_reason: str,
    selected_source_ids: Optional[List[int]] = None,
    alternate_business_approver: Optional[Dict[str, Optional[str]]] = None,
) -> Optional[AccessRequestRow]:
    if decision not in {"approve_24h", "approve_7d", "approve_30d", "deny", "return_not_owner", "return_not_relevant", "return_reroute"}:
        return None
    hours = {"approve_24h": 24, "approve_7d": 24 * 7, "approve_30d": 24 * 30}.get(decision)
    next_source_ids = sorted({int(item) for item in (selected_source_ids or []) if item is not None})
    if decision == "return_reroute" and not ((alternate_business_approver or {}).get("contact_email") or (alternate_business_approver or {}).get("contact_external_user_id")):
        return None
    with engine.begin() as conn:
        visible_row = conn.execute(
            text(
                """
                SELECT access_request_id, routing_id
                FROM approval_inbox_items
                WHERE id = :inbox_item_id
                  AND (assigned_external_user_id = :actor_user_id OR LOWER(COALESCE(assigned_email, '')) = :actor_email)
                """
            ),
            {
                "inbox_item_id": inbox_item_id,
                "actor_user_id": actor.user_id if actor else None,
                "actor_email": _normalize_email(actor.email) if actor else "",
            },
        ).first()
        if visible_row is None:
            return None
        access_request_id = int(visible_row[0])
        routing_id = int(visible_row[1]) if visible_row[1] is not None else None
        existing_target_count = int(
            conn.execute(
                text("SELECT COUNT(*) FROM access_request_targets WHERE access_request_id = :access_request_id"),
                {"access_request_id": access_request_id},
            ).scalar_one()
            or 0
        )
        if decision in {"approve_24h", "approve_7d", "approve_30d"} and not next_source_ids and existing_target_count == 0:
            return None
        inbox_row = conn.execute(
            text(
                """
                UPDATE approval_inbox_items
                SET status = CASE
                        WHEN :decision = 'deny' THEN 'denied'
                        WHEN :decision IN ('return_not_owner', 'return_not_relevant', 'return_reroute') THEN 'returned'
                        ELSE 'approved'
                    END,
                    decision = :decision,
                    decision_reason = :decision_reason,
                    resolution_payload_json = CAST(:resolution_payload_json AS jsonb),
                    decided_at = now()
                WHERE id = :inbox_item_id
                  AND (assigned_external_user_id = :actor_user_id OR LOWER(COALESCE(assigned_email, '')) = :actor_email)
                RETURNING access_request_id, routing_id
                """
            ),
            {
                "inbox_item_id": inbox_item_id,
                "decision": decision,
                "decision_reason": decision_reason,
                "resolution_payload_json": _json(
                    {
                        "decision": decision,
                        "hours": hours,
                        "selected_source_ids": sorted({int(item) for item in (selected_source_ids or []) if item is not None}),
                        "alternate_business_approver": alternate_business_approver or {},
                    }
                ),
                "actor_user_id": actor.user_id if actor else None,
                "actor_email": _normalize_email(actor.email) if actor else "",
            },
        ).first()
        if inbox_row is None:
            return None
        if next_source_ids:
            conn.execute(text("DELETE FROM access_request_targets WHERE access_request_id = :access_request_id"), {"access_request_id": access_request_id})
            for source_id in next_source_ids:
                conn.execute(
                    text(
                        """
                        INSERT INTO access_request_targets (access_request_id, source_id, status, mapped_by_external_user_id, mapped_by_email)
                        VALUES (:access_request_id, :source_id, 'approver_mapped', :mapped_by_external_user_id, :mapped_by_email)
                        """
                    ),
                    {
                        "access_request_id": access_request_id,
                        "source_id": source_id,
                        "mapped_by_external_user_id": actor.user_id if actor else None,
                        "mapped_by_email": actor.email if actor else None,
                    },
                )
        metadata_row = conn.execute(
            text("SELECT metadata_json FROM access_requests WHERE id = :access_request_id"),
            {"access_request_id": access_request_id},
        ).first()
        next_metadata = dict((metadata_row[0] or {}) if metadata_row else {})
        if decision in {"return_not_owner", "return_not_relevant", "return_reroute"}:
            next_metadata["approver_return"] = {
                "decision": decision,
                "decision_reason": decision_reason,
                "alternate_business_approver": alternate_business_approver or {},
                "selected_source_ids": next_source_ids,
                "returned_by_email": actor.email if actor else None,
                "returned_by_external_user_id": actor.user_id if actor else None,
            }
        row = conn.execute(
            text(
                """
                UPDATE access_requests
                SET status = CASE
                        WHEN :decision = 'deny' THEN 'business_denied'
                        WHEN :decision IN ('return_not_owner', 'return_not_relevant', 'return_reroute') THEN 'triaged'
                        ELSE 'business_approved'
                    END,
                    business_approval_status = CASE
                        WHEN :decision = 'deny' THEN 'denied'
                        WHEN :decision IN ('return_not_owner', 'return_not_relevant', 'return_reroute') THEN 'returned'
                        ELSE 'approved'
                    END,
                    business_approval_decision = :decision,
                    business_approval_reason = :decision_reason,
                    approved_duration_hours = :approved_duration_hours,
                    business_approved_at = now(),
                    metadata_json = CAST(:metadata_json AS jsonb),
                    updated_at = now()
                WHERE id = :access_request_id
                RETURNING id, status, question, business_reason, source_hint, request_id, answer_path,
                          requester_external_user_id, requester_email, requester_display_name,
                          requester_manager_external_user_id, requester_manager_email, requester_manager_display_name,
                          approved_duration_hours, business_approval_status, business_approval_decision,
                          business_approval_reason, business_approved_at, granted_at, expires_at,
                          granted_by_external_user_id, granted_by_email, review_reason, metadata_json, created_at, updated_at
                """
            ),
            {
                "access_request_id": access_request_id,
                "decision": decision,
                "decision_reason": decision_reason,
                "approved_duration_hours": hours,
                "metadata_json": _json(next_metadata),
            },
        ).first()
        if routing_id is not None:
            conn.execute(
                text(
                    """
                    UPDATE access_request_routing
                    SET responded_at = now(), updated_at = now()
                    WHERE access_request_id = :access_request_id
                    """
                ),
                {"access_request_id": access_request_id},
            )
    access_request = _row_to_access_request(row)
    routing = get_access_request_routing(access_request.id)
    requester_body = (
        "Your access request was reviewed and is waiting for admin follow-through."
        if decision in {"approve_24h", "approve_7d", "approve_30d"}
        else "Your access request was denied."
        if decision == "deny"
        else "Your access request was returned to admin for rerouting or additional review."
    )
    create_notification_event(
        access_request_id=access_request.id,
        event_type="business_approval_decided",
        recipient_external_user_id=access_request.requester_external_user_id,
        recipient_email=access_request.requester_email,
        recipient_display_name=access_request.requester_display_name,
        recipient_role="requester",
        title="Access request reviewed",
        body=requester_body,
        email_subject=f"Access request #{access_request.id} reviewed",
        email_payload_json={"decision": decision, "request_id": access_request.id},
        payload_json={"decision": decision, "request_id": access_request.id},
    )
    if decision in {"return_not_owner", "return_not_relevant", "return_reroute"} and routing:
        create_notification_event(
            access_request_id=access_request.id,
            event_type="access_request_returned_to_admin",
            recipient_external_user_id=routing.admin_coordinator_external_user_id,
            recipient_email=routing.admin_coordinator_email,
            recipient_display_name=None,
            recipient_role="admin_coordinator",
            title="Access request returned to admin",
            body="The approver returned this request for rerouting or closure.",
            email_subject=f"Access request #{access_request.id} returned to admin",
            email_payload_json={"decision": decision, "request_id": access_request.id},
            payload_json={"decision": decision, "request_id": access_request.id, "alternate_business_approver": alternate_business_approver or {}},
        )
    return access_request


def grant_access_request(*, access_request_id: int, actor: Optional[AuthenticatedUser]) -> Optional[AccessRequestRow]:
    access_request = get_access_request(access_request_id)
    if access_request is None or access_request.business_approval_status != "approved" or not access_request.approved_duration_hours:
        return None
    starts_at = _now()
    expires_at = starts_at + timedelta(hours=int(access_request.approved_duration_hours))
    targets = list_access_request_targets(access_request_id)
    if not targets:
        return None
    with engine.begin() as conn:
        for target in targets:
            conn.execute(
                text(
                    """
                    INSERT INTO user_source_access_grants (
                        access_request_id, source_id, grantee_external_user_id, grantee_email, grant_reason,
                        granted_by_external_user_id, granted_by_email, starts_at, expires_at, metadata_json
                    )
                    VALUES (
                        :access_request_id, :source_id, :grantee_external_user_id, :grantee_email, :grant_reason,
                        :granted_by_external_user_id, :granted_by_email, :starts_at, :expires_at, CAST(:metadata_json AS jsonb)
                    )
                    """
                ),
                {
                    "access_request_id": access_request_id,
                    "source_id": target.source_id,
                    "grantee_external_user_id": access_request.requester_external_user_id,
                    "grantee_email": access_request.requester_email,
                    "grant_reason": access_request.business_reason or "approved_access_request",
                    "granted_by_external_user_id": actor.user_id if actor else None,
                    "granted_by_email": actor.email if actor else None,
                    "starts_at": starts_at,
                    "expires_at": expires_at,
                    "metadata_json": _json({"approved_duration_hours": access_request.approved_duration_hours}),
                },
            )
        row = conn.execute(
            text(
                """
                UPDATE access_requests
                SET status = 'grant_completed',
                    granted_at = :granted_at,
                    expires_at = :expires_at,
                    granted_by_external_user_id = :granted_by_external_user_id,
                    granted_by_email = :granted_by_email,
                    updated_at = now()
                WHERE id = :access_request_id
                RETURNING id, status, question, business_reason, source_hint, request_id, answer_path,
                          requester_external_user_id, requester_email, requester_display_name,
                          requester_manager_external_user_id, requester_manager_email, requester_manager_display_name,
                          approved_duration_hours, business_approval_status, business_approval_decision,
                          business_approval_reason, business_approved_at, granted_at, expires_at,
                          granted_by_external_user_id, granted_by_email, review_reason, metadata_json, created_at, updated_at
                """
            ),
            {
                "access_request_id": access_request_id,
                "granted_at": starts_at,
                "expires_at": expires_at,
                "granted_by_external_user_id": actor.user_id if actor else None,
                "granted_by_email": actor.email if actor else None,
            },
        ).first()
    result = _row_to_access_request(row)
    create_notification_event(
        access_request_id=access_request_id,
        event_type="access_granted",
        recipient_external_user_id=result.requester_external_user_id,
        recipient_email=result.requester_email,
        recipient_display_name=result.requester_display_name,
        recipient_role="requester",
        title="Temporary access granted",
        body=f"Your temporary access is active until {result.expires_at}. Retry your question from the workspace.",
        email_subject=f"Access request #{access_request_id} granted",
        email_payload_json={"expires_at": result.expires_at, "request_id": access_request_id},
        payload_json={"expires_at": result.expires_at, "request_id": access_request_id},
    )
    from app.db.repo_semantic_cache import bump_cache_revision

    bump_cache_revision(scope_type="access", reason=f"direct_grant:{access_request_id}")
    return result


def deny_access_request(*, access_request_id: int, actor: Optional[AuthenticatedUser], reason: str) -> Optional[AccessRequestRow]:
    sql = text(
        """
        UPDATE access_requests
        SET status = 'cancelled',
            review_reason = :reason,
            updated_at = now()
        WHERE id = :access_request_id
        RETURNING id, status, question, business_reason, source_hint, request_id, answer_path,
                  requester_external_user_id, requester_email, requester_display_name,
                  requester_manager_external_user_id, requester_manager_email, requester_manager_display_name,
                  approved_duration_hours, business_approval_status, business_approval_decision,
                  business_approval_reason, business_approved_at, granted_at, expires_at,
                  granted_by_external_user_id, granted_by_email, review_reason, metadata_json, created_at, updated_at
        """
    )
    with engine.begin() as conn:
        row = conn.execute(sql, {"access_request_id": access_request_id, "reason": reason}).first()
    if row is None:
        return None
    result = _row_to_access_request(row)
    create_notification_event(
        access_request_id=access_request_id,
        event_type="access_request_denied",
        recipient_external_user_id=result.requester_external_user_id,
        recipient_email=result.requester_email,
        recipient_display_name=result.requester_display_name,
        recipient_role="requester",
        title="Access request closed",
        body="Your access request was closed without a grant.",
        email_subject=f"Access request #{access_request_id} closed",
        email_payload_json={"request_id": access_request_id, "reason": reason},
        payload_json={"request_id": access_request_id, "reason": reason},
    )
    return result


def get_active_grant_counts() -> dict[str, int]:
    sql = text(
        """
        SELECT
            COUNT(*) FILTER (WHERE revoked_at IS NULL AND expires_at > now())::bigint AS active_grants,
            COUNT(*) FILTER (WHERE revoked_at IS NULL AND expires_at <= now())::bigint AS expired_grants
        FROM user_source_access_grants
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql).first()
    return {"active_grants": int(row[0] or 0), "expired_grants": int(row[1] or 0)}
