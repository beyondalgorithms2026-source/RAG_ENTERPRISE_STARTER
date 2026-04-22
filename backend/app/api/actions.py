from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.actions.policy import TOOL_REGISTRY, evaluate_tool_policy
from app.auth.context import get_current_user
from app.auth.dependencies import require_admin_user, require_authenticated_user
from app.db.repo_actions import (
    create_approval_request,
    create_query_feedback,
    create_tool_invocation,
    get_approval_request,
    list_approval_requests,
    list_query_feedback,
    list_tool_invocations,
    review_approval_request,
    top_failed_queries,
)
from app.db.repo_admin_audit import insert_admin_audit_event


router = APIRouter()


class ToolInvokeRequest(BaseModel):
    tool_name: str
    corpus_name: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ToolInvokeResponse(BaseModel):
    status: str
    invocation_id: int
    tool_name: str
    result: dict[str, Any] = Field(default_factory=dict)
    denial_reason: Optional[str] = None
    approval_request_id: Optional[int] = None


class ApprovalReviewRequest(BaseModel):
    status: Literal["approved", "denied"]
    review_reason: str = ""


class QueryFeedbackCreate(BaseModel):
    question: str
    feedback_type: Literal["helpful", "not_helpful", "missing_evidence", "clarification", "source_suggestion"]
    rating: Optional[str] = None
    reason: str = ""
    suggested_source: Optional[str] = None
    request_id: Optional[str] = None
    answer_path: Optional[str] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


def _approval_payload(row) -> dict[str, Any]:
    return row.__dict__


def _tool_result(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "generate_report":
        return {
            "artifact_type": payload.get("artifact_type") or "csv",
            "status": "placeholder_generated",
            "download_ready": False,
        }
    return {
        "prepared": True,
        "external_dispatch": False,
        "message": f"{tool_name} is prepared but awaits approval before external delivery.",
    }


@router.get("/tools")
def list_tools(_user=Depends(require_authenticated_user)):
    return {"tools": [{"name": name, **config} for name, config in TOOL_REGISTRY.items()]}


@router.post("/tools/invoke", response_model=ToolInvokeResponse)
def invoke_tool(body: ToolInvokeRequest, _user=Depends(require_authenticated_user)):
    actor = get_current_user()
    tool_name = body.tool_name.strip()
    allowed, reason = evaluate_tool_policy(tool_name=tool_name, actor=actor, corpus_name=body.corpus_name)
    if not allowed:
        invocation_id = create_tool_invocation(
            tool_name=tool_name,
            status="denied",
            actor=actor,
            corpus_name=body.corpus_name,
            request_payload_json=body.payload,
            denial_reason=reason,
        )
        insert_admin_audit_event(
            event_type="tool",
            action="tool.invocation.denied",
            outcome="denied",
            resource_type="tool_invocation",
            resource_id=str(invocation_id),
            resource_name=tool_name,
            corpus_name=body.corpus_name,
            after_json={"denial_reason": reason, "payload": body.payload},
        )
        return ToolInvokeResponse(status="denied", invocation_id=invocation_id, tool_name=tool_name, denial_reason=reason)

    tool = TOOL_REGISTRY[tool_name]
    result = _tool_result(tool_name, body.payload)
    approval_id = None
    status = "completed"
    if tool.get("requires_approval"):
        approval_id = create_approval_request(
            approval_type="tool_action",
            reason=f"{tool_name} requires human approval before external execution.",
            actor=actor,
            requested_payload_json={"tool_name": tool_name, "corpus_name": body.corpus_name, "payload": body.payload},
            response_payload_json=result,
        )
        status = "pending_approval"
    invocation_id = create_tool_invocation(
        tool_name=tool_name,
        status=status,
        actor=actor,
        corpus_name=body.corpus_name,
        request_payload_json=body.payload,
        result_payload_json=result,
        approval_request_id=approval_id,
    )
    insert_admin_audit_event(
        event_type="tool",
        action="tool.invocation.requested" if approval_id else "tool.invocation.completed",
        resource_type="tool_invocation",
        resource_id=str(invocation_id),
        resource_name=tool_name,
        corpus_name=body.corpus_name,
        after_json={"status": status, "approval_request_id": approval_id, "result": result},
    )
    return ToolInvokeResponse(status=status, invocation_id=invocation_id, tool_name=tool_name, result=result, approval_request_id=approval_id)


@router.get("/approvals")
def list_user_approvals(_user=Depends(require_authenticated_user)):
    actor = get_current_user()
    requester_id = None if actor and "admin" in {role.lower() for role in actor.roles} else actor.user_id if actor else None
    return {"approvals": [_approval_payload(row) for row in list_approval_requests(requester_external_user_id=requester_id)]}


@router.get("/approvals/{approval_id}")
def get_user_approval(approval_id: int, _user=Depends(require_authenticated_user)):
    row = get_approval_request(approval_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "approval_not_found", "approval_id": approval_id})
    actor = get_current_user()
    if actor and "admin" not in {role.lower() for role in actor.roles} and row.requester_external_user_id != actor.user_id:
        raise HTTPException(status_code=403, detail={"error": "approval_not_visible"})
    return _approval_payload(row)


@router.get("/admin/approvals")
def list_admin_approvals(_admin=Depends(require_admin_user)):
    return {"approvals": [_approval_payload(row) for row in list_approval_requests(limit=200)]}


@router.post("/admin/approvals/{approval_id}/review")
def review_admin_approval(approval_id: int, body: ApprovalReviewRequest, _admin=Depends(require_admin_user)):
    actor = get_current_user()
    before = get_approval_request(approval_id)
    row = review_approval_request(approval_id=approval_id, status=body.status, review_reason=body.review_reason, reviewer=actor)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "approval_not_found", "approval_id": approval_id})
    insert_admin_audit_event(
        event_type="approval",
        action="approval.reviewed",
        resource_type="approval_request",
        resource_id=str(approval_id),
        resource_name=row.approval_type,
        before_json=before.__dict__ if before else {},
        after_json=row.__dict__,
    )
    return _approval_payload(row)


@router.post("/feedback")
def create_feedback(body: QueryFeedbackCreate, _user=Depends(require_authenticated_user)):
    actor = get_current_user()
    feedback_id = create_query_feedback(
        question=body.question.strip(),
        feedback_type=body.feedback_type,
        rating=body.rating,
        reason=body.reason.strip(),
        suggested_source=body.suggested_source.strip() if body.suggested_source else None,
        request_id=body.request_id,
        answer_path=body.answer_path,
        actor=actor,
        metadata_json=body.metadata_json,
    )
    return {"status": "recorded", "feedback_id": feedback_id}


@router.get("/admin/feedback")
def list_admin_feedback(_admin=Depends(require_admin_user)):
    return {
        "feedback": [row.__dict__ for row in list_query_feedback(limit=200)],
        "top_failed_queries": top_failed_queries(limit=20),
    }


@router.get("/admin/tools")
def list_admin_tools(_admin=Depends(require_admin_user)):
    return {"tools": [{"name": name, **config} for name, config in TOOL_REGISTRY.items()], "invocations": [row.__dict__ for row in list_tool_invocations(limit=200)]}
