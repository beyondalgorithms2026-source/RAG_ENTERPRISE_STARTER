from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.context import get_current_user
from app.auth.dependencies import require_admin_user, require_authenticated_user
from app.db.repo_access_requests import (
    create_access_request,
    create_notification_event,
    decide_inbox_item,
    deny_access_request,
    get_access_request,
    get_access_request_routing,
    grant_access_request,
    list_access_request_targets,
    list_access_requests,
    list_inbox_items,
    list_notification_events,
    list_source_access_contacts,
    mark_notification_read,
    resolve_source_contacts,
    route_access_request,
)
from app.db.repo_admin_audit import insert_admin_audit_event
from app.db.repo_governance import evaluate_access_request_risk, is_restricted
from app.db.repo_sources import get_source_by_id


router = APIRouter()


class AccessRequestCreate(BaseModel):
    question: str
    business_reason: str = ""
    source_hint: Optional[str] = None
    suggested_approver_email: Optional[str] = None
    suggested_approver_display_name: Optional[str] = None
    requester_manager_email: Optional[str] = None
    requester_manager_display_name: Optional[str] = None
    requester_comment: Optional[str] = None
    request_id: Optional[str] = None
    answer_path: Optional[str] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class RouteAccessRequestBody(BaseModel):
    source_ids: list[int] = Field(default_factory=list)
    business_approver_external_user_id: Optional[str] = None
    business_approver_email: Optional[str] = None
    business_approver_display_name: Optional[str] = None
    acl_manager_external_user_id: Optional[str] = None
    acl_manager_email: Optional[str] = None
    acl_manager_display_name: Optional[str] = None
    requester_manager_external_user_id: Optional[str] = None
    requester_manager_email: Optional[str] = None
    requester_manager_display_name: Optional[str] = None
    review_reason: str = ""


class ApprovalDecisionBody(BaseModel):
    decision: str = Field(pattern="^(approve_24h|approve_7d|approve_30d|deny|return_not_owner|return_not_relevant|return_reroute)$")
    decision_reason: str = ""
    selected_source_ids: list[int] = Field(default_factory=list)
    alternate_business_approver_external_user_id: Optional[str] = None
    alternate_business_approver_email: Optional[str] = None
    alternate_business_approver_display_name: Optional[str] = None


class DenyAccessRequestBody(BaseModel):
    reason: str = ""


def _request_payload(row) -> dict[str, Any]:
    payload = row.__dict__.copy()
    payload["targets"] = [target.__dict__ for target in list_access_request_targets(row.id)]
    routing = get_access_request_routing(row.id)
    payload["routing"] = routing.__dict__ if routing else None
    return payload


@router.post("/access-requests")
def create_access_request_endpoint(body: AccessRequestCreate, _user=Depends(require_authenticated_user)):
    actor = get_current_user()
    restriction = is_restricted(actor, {"access_request_block", "extra_review_required"})
    if restriction and restriction.get("restriction_type") == "access_request_block":
        raise HTTPException(status_code=403, detail={"error": "access_request_blocked", "message": restriction.get("reason")})
    question = body.question.strip()
    business_reason = body.business_reason.strip()
    if not question:
        raise HTTPException(status_code=400, detail={"error": "question_required", "message": "Question context is missing. Ask the question again and then request access."})
    if not business_reason:
        raise HTTPException(status_code=400, detail={"error": "business_reason_required", "message": "Add a business reason before requesting access."})
    risk_signals = evaluate_access_request_risk(
        actor=actor,
        question=question,
        suggested_approver_email=body.suggested_approver_email,
    )
    metadata_json = dict(body.metadata_json or {})
    metadata_json.update(
        {
            "suggested_approver_email": (body.suggested_approver_email or "").strip().lower() or None,
            "suggested_approver_display_name": (body.suggested_approver_display_name or "").strip() or None,
            "requester_comment": (body.requester_comment or "").strip() or None,
            "governance_risk_signals": risk_signals,
            "extra_review_required": bool(restriction and restriction.get("restriction_type") == "extra_review_required"),
        }
    )
    row = create_access_request(
        question=question,
        business_reason=business_reason,
        source_hint=body.source_hint.strip() if body.source_hint else None,
        request_id=body.request_id,
        answer_path=body.answer_path,
        actor=actor,
        requester_manager={
            "contact_external_user_id": None,
            "contact_email": (body.requester_manager_email or "").strip().lower() or None,
            "contact_display_name": (body.requester_manager_display_name or "").strip() or None,
        }
        if body.requester_manager_email or body.requester_manager_display_name
        else None,
        metadata_json=metadata_json,
    )
    create_notification_event(
        access_request_id=row.id,
        event_type="access_request_submitted",
        recipient_external_user_id=row.requester_external_user_id,
        recipient_email=row.requester_email,
        recipient_display_name=row.requester_display_name,
        recipient_role="requester",
        title="Access request submitted",
        body=f"Access request #{row.id} was submitted for admin review.",
        email_subject=f"Access request #{row.id} submitted",
        email_payload_json={"request_id": row.id},
        payload_json={"request_id": row.id},
    )
    insert_admin_audit_event(
        event_type="access_request",
        action="access_request.submitted",
        resource_type="access_request",
        resource_id=str(row.id),
        resource_name="access_request",
        request_id=row.request_id,
        after_json=row.__dict__,
    )
    return {"status": "submitted", "access_request": _request_payload(row)}


@router.get("/access-requests")
def list_my_access_requests(_user=Depends(require_authenticated_user)):
    actor = get_current_user()
    return {"access_requests": [_request_payload(row) for row in list_access_requests(requester_external_user_id=actor.user_id, actor_email=actor.email, limit=200)]}


@router.get("/access-requests/{access_request_id}")
def get_my_access_request(access_request_id: int, _user=Depends(require_authenticated_user)):
    actor = get_current_user()
    row = get_access_request(access_request_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "access_request_not_found"})
    routing = get_access_request_routing(access_request_id)
    allowed = row.requester_external_user_id == actor.user_id or (routing and ((routing.business_approver_external_user_id == actor.user_id) or ((routing.business_approver_email or "").lower() == (actor.email or "").lower())))
    if not allowed and "admin" not in {role.lower() for role in actor.roles}:
        raise HTTPException(status_code=403, detail={"error": "access_request_not_visible"})
    return {"access_request": _request_payload(row)}


@router.get("/me/approvals")
def list_my_approvals(_user=Depends(require_authenticated_user)):
    actor = get_current_user()
    return {"approvals": [row.__dict__ for row in list_inbox_items(actor=actor, limit=200)]}


@router.post("/me/approvals/{inbox_item_id}/decision")
def decide_my_approval(inbox_item_id: int, body: ApprovalDecisionBody, _user=Depends(require_authenticated_user)):
    actor = get_current_user()
    row = decide_inbox_item(
        inbox_item_id=inbox_item_id,
        actor=actor,
        decision=body.decision,
        decision_reason=body.decision_reason.strip(),
        selected_source_ids=body.selected_source_ids,
        alternate_business_approver={
            "contact_external_user_id": body.alternate_business_approver_external_user_id,
            "contact_email": body.alternate_business_approver_email,
            "contact_display_name": body.alternate_business_approver_display_name,
        }
        if body.alternate_business_approver_external_user_id or body.alternate_business_approver_email or body.alternate_business_approver_display_name
        else None,
    )
    if row is None:
        raise HTTPException(status_code=400, detail={"error": "approval_inbox_item_not_actionable"})
    insert_admin_audit_event(
        event_type="access_request",
        action="access_request.business_decision",
        resource_type="access_request",
        resource_id=str(row.id),
        resource_name="access_request",
        after_json=row.__dict__,
        actor=actor,
    )
    return {"status": "recorded", "access_request": _request_payload(row)}


@router.get("/me/notifications")
def list_my_notifications(_user=Depends(require_authenticated_user)):
    actor = get_current_user()
    return {"notifications": [row.__dict__ for row in list_notification_events(actor=actor, limit=200)]}


@router.post("/me/notifications/{notification_id}/read")
def mark_my_notification_read(notification_id: int, _user=Depends(require_authenticated_user)):
    actor = get_current_user()
    if not mark_notification_read(notification_id, actor):
        raise HTTPException(status_code=404, detail={"error": "notification_not_found"})
    return {"status": "read"}


@router.get("/admin/access-requests")
def list_admin_access_requests(_admin=Depends(require_admin_user)):
    return {"access_requests": [_request_payload(row) for row in list_access_requests(limit=200)]}


@router.post("/admin/access-requests/{access_request_id}/route")
def route_admin_access_request(access_request_id: int, body: RouteAccessRequestBody, _admin=Depends(require_admin_user)):
    actor = get_current_user()
    request_row = get_access_request(access_request_id)
    if request_row is None:
        raise HTTPException(status_code=404, detail={"error": "access_request_not_found"})
    source_ids = [item for item in body.source_ids if item is not None]
    first_source_id = source_ids[0] if source_ids else None
    default_contacts = resolve_source_contacts(first_source_id) if first_source_id is not None else {"business_approver": None, "acl_manager": None}
    metadata = request_row.metadata_json or {}
    business_approver = {
        "contact_external_user_id": body.business_approver_external_user_id or (default_contacts.get("business_approver") or {}).get("contact_external_user_id"),
        "contact_email": body.business_approver_email or (metadata.get("suggested_approver_email")) or (default_contacts.get("business_approver") or {}).get("contact_email"),
        "contact_display_name": body.business_approver_display_name or (metadata.get("suggested_approver_display_name")) or (default_contacts.get("business_approver") or {}).get("contact_display_name"),
    }
    if not business_approver["contact_email"] and not business_approver["contact_external_user_id"]:
        raise HTTPException(status_code=400, detail={"error": "business_approver_required"})
    row = route_access_request(
        access_request_id=access_request_id,
        source_ids=source_ids,
        admin_actor=actor,
        business_approver=business_approver,
        acl_manager={
            "contact_external_user_id": body.acl_manager_external_user_id or (default_contacts.get("acl_manager") or {}).get("contact_external_user_id"),
            "contact_email": body.acl_manager_email or (default_contacts.get("acl_manager") or {}).get("contact_email"),
            "contact_display_name": body.acl_manager_display_name or (default_contacts.get("acl_manager") or {}).get("contact_display_name"),
        },
        requester_manager=None,
        fallback_requester_manager={
            "contact_external_user_id": body.requester_manager_external_user_id,
            "contact_email": body.requester_manager_email or request_row.requester_manager_email,
            "contact_display_name": body.requester_manager_display_name or request_row.requester_manager_display_name,
        },
        review_reason=body.review_reason.strip(),
    )
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "access_request_not_found"})
    insert_admin_audit_event(
        event_type="access_request",
        action="access_request.routed",
        resource_type="access_request",
        resource_id=str(access_request_id),
        resource_name="access_request",
        after_json=_request_payload(row),
        actor=actor,
    )
    return {"status": "routed", "access_request": _request_payload(row)}


@router.post("/admin/access-requests/{access_request_id}/grant")
def grant_admin_access_request(access_request_id: int, _admin=Depends(require_admin_user)):
    actor = get_current_user()
    row = grant_access_request(access_request_id=access_request_id, actor=actor)
    if row is None:
        raise HTTPException(status_code=400, detail={"error": "access_request_not_grantable"})
    insert_admin_audit_event(
        event_type="access_request",
        action="access_request.granted",
        resource_type="access_request",
        resource_id=str(access_request_id),
        resource_name="access_request",
        after_json=_request_payload(row),
        actor=actor,
    )
    return {"status": "granted", "access_request": _request_payload(row)}


@router.post("/admin/access-requests/{access_request_id}/deny")
def deny_admin_access_request(access_request_id: int, body: DenyAccessRequestBody, _admin=Depends(require_admin_user)):
    actor = get_current_user()
    row = deny_access_request(access_request_id=access_request_id, actor=actor, reason=body.reason.strip())
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "access_request_not_found"})
    insert_admin_audit_event(
        event_type="access_request",
        action="access_request.cancelled",
        resource_type="access_request",
        resource_id=str(access_request_id),
        resource_name="access_request",
        after_json=_request_payload(row),
        actor=actor,
    )
    return {"status": "cancelled", "access_request": _request_payload(row)}


@router.get("/admin/access-requests/{access_request_id}/contacts")
def get_access_request_contacts(access_request_id: int, _admin=Depends(require_admin_user)):
    row = get_access_request(access_request_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "access_request_not_found"})
    targets = list_access_request_targets(access_request_id)
    source_id = targets[0].source_id if targets else None
    contacts = list_source_access_contacts(source_id) if source_id is not None else []
    source = get_source_by_id(source_id) if source_id is not None else None
    return {
        "source": source.__dict__ if source else None,
        "contacts": [contact.__dict__ for contact in contacts],
        "resolved_defaults": resolve_source_contacts(source_id) if source_id is not None else {},
    }
