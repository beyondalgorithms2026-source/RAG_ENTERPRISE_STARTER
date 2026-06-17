from fastapi import HTTPException, Request

from app.auth.context import AuthenticatedUser
from app.auth.service import anonymous_research_enabled, auth_required, no_auth_upload_enabled


def get_request_user(request: Request) -> AuthenticatedUser | None:
    return getattr(request.state, "user", None)


def require_authenticated_user(request: Request) -> AuthenticatedUser | None:
    if anonymous_research_enabled():
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


def require_admin_user(request: Request) -> AuthenticatedUser | None:
    user = require_authenticated_user(request)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={"error": "authentication_required", "message": "Admin endpoints require authentication."},
        )
    if "admin" not in {role.lower() for role in user.roles}:
        raise HTTPException(
            status_code=403,
            detail={"error": "admin_required", "message": "Admin role is required for this endpoint."},
        )
    return user


def require_search_user(request: Request) -> AuthenticatedUser | None:
    return None if anonymous_research_enabled() else require_authenticated_user(request)


def require_ask_user(request: Request) -> AuthenticatedUser | None:
    return None if anonymous_research_enabled() else require_authenticated_user(request)


def require_upload_user(request: Request) -> AuthenticatedUser | None:
    if no_auth_upload_enabled():
        return None
    user = require_authenticated_user(request)
    if user is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "upload_disabled", "message": "Uploads are disabled in no-auth research mode."},
        )
    roles = {role.lower() for role in user.roles}
    if auth_required() and not (roles & {"admin", "editor"}):
        raise HTTPException(
            status_code=403,
            detail={"error": "upload_role_required", "message": "Upload requires admin or editor role."},
        )
    return user


def require_connector_request_user(request: Request) -> AuthenticatedUser | None:
    if anonymous_research_enabled():
        raise HTTPException(
            status_code=403,
            detail={"error": "connector_requests_disabled", "message": "Connector requests require authentication."},
        )
    return require_authenticated_user(request)
