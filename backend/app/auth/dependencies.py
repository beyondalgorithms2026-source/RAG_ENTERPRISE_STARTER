from fastapi import HTTPException, Request

from app.auth.context import AuthenticatedUser
from app.core.config import settings


def get_request_user(request: Request) -> AuthenticatedUser | None:
    return getattr(request.state, "user", None)


def require_authenticated_user(request: Request) -> AuthenticatedUser | None:
    if not settings.AUTH_ENABLED:
        return None
    auth_error = getattr(request.state, "auth_error", None)
    if auth_error:
        raise HTTPException(
            status_code=auth_error.status_code,
            detail={"error": auth_error.code, "message": auth_error.message},
        )
    user = get_request_user(request)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={"error": "authentication_required", "message": "Authentication is required for this endpoint."},
        )
    return user
