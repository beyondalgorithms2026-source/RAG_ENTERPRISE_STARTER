from fastapi import HTTPException, Request

from app.auth.context import AuthenticatedUser
from app.auth.service import non_local_runtime_enabled
from app.core.config import settings


def require_high_impact_approval(*, request: Request, actor: AuthenticatedUser | None, action: str) -> dict[str, str]:
    roles = {role.lower() for role in (actor.roles if actor else [])}
    if "auditor" in roles and "admin" not in roles:
        raise HTTPException(status_code=403, detail={"error": "auditor_read_only", "message": "Auditor role is read-only."})
    if not settings.SEGREGATION_OF_DUTIES_ENABLED or not non_local_runtime_enabled():
        return {"approval_actor": "local-dev-not-required", "action": action}
    approval_actor = request.headers.get("X-Approval-Actor", "").strip()
    if not approval_actor:
        raise HTTPException(
            status_code=409,
            detail={"error": "approval_actor_required", "message": f"{action} requires a separate approval actor."},
        )
    if actor and approval_actor == actor.user_id:
        raise HTTPException(
            status_code=409,
            detail={"error": "segregation_of_duties_required", "message": "Approval actor must differ from executing actor."},
        )
    return {"approval_actor": approval_actor, "action": action}
