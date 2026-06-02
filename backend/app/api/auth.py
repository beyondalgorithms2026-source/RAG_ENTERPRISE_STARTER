from urllib.parse import quote

from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.auth.dependencies import require_authenticated_user
from app.auth.service import (
    AuthError,
    authenticate_local_dev_user,
    auth_required,
    build_local_dev_user,
    build_login_url,
    exchange_code_for_token,
    get_oidc_metadata,
    issue_local_dev_token,
    local_dev_auth_enabled,
    oidc_configured,
    resolve_post_login_path,
    validate_access_token,
    verify_state,
)
from app.core.config import settings


router = APIRouter(prefix="/auth", tags=["auth"])


class LocalDevLoginRequest(BaseModel):
    email: str
    password: str
    next_path: str | None = None


class LocalDevAssumeRequest(BaseModel):
    email: str
    name: str | None = None
    user_id: str | None = None
    roles: list[str] = ["user"]
    groups: list[str] = []
    next_path: str | None = None
    manager_email: str | None = None
    manager_display_name: str | None = None
    manager_external_user_id: str | None = None


@router.get("/providers")
def auth_providers():
    if not auth_required():
        return {
            "auth_enabled": False,
            "auth_mode": settings.AUTH_MODE,
            "local_dev_enabled": False,
            "oidc_configured": False,
            "sso_available": False,
            "provider_error": None,
            "providers": [],
        }
    local_dev_enabled = local_dev_auth_enabled()
    configured = oidc_configured()
    if not configured:
        return {
            "auth_enabled": True,
            "auth_mode": settings.AUTH_MODE,
            "local_dev_enabled": local_dev_enabled,
            "oidc_configured": False,
            "sso_available": False,
            "provider_error": None,
            "providers": [],
        }
    try:
        metadata = get_oidc_metadata()
    except AuthError as exc:
        return {
            "auth_enabled": True,
            "auth_mode": settings.AUTH_MODE,
            "local_dev_enabled": local_dev_enabled,
            "oidc_configured": True,
            "sso_available": False,
            "provider_error": {"error": exc.code, "message": exc.message},
            "providers": [],
        }
    return {
        "auth_enabled": True,
        "auth_mode": settings.AUTH_MODE,
        "local_dev_enabled": local_dev_enabled,
        "oidc_configured": True,
        "sso_available": True,
        "provider_error": None,
        "providers": [
            {
                "issuer": metadata.get("issuer"),
                "authorization_endpoint": metadata.get("authorization_endpoint"),
                "token_endpoint": metadata.get("token_endpoint"),
            }
        ],
    }


@router.get("/login")
def auth_login(next_path: str = Query(default_factory=lambda: settings.FRONTEND_APP_URL)):
    if not auth_required():
        raise HTTPException(status_code=503, detail={"error": "auth_disabled", "message": "Authentication is disabled."})
    if local_dev_auth_enabled() and not oidc_configured():
        redirect_target = f"{settings.FRONTEND_APP_URL.rstrip('/')}/login?next={quote(next_path, safe='')}&dev_login=1"
        return RedirectResponse(url=redirect_target, status_code=302)
    try:
        login_url, state = build_login_url(next_path=next_path)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"error": exc.code, "message": exc.message})
    response = RedirectResponse(url=login_url, status_code=302)
    response.set_cookie(
        key=settings.AUTH_STATE_COOKIE_NAME,
        value=state,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="lax",
        max_age=600,
        path="/",
    )
    return response


@router.get("/callback")
def auth_callback(request: Request, code: str, state: str):
    expected_state = request.cookies.get(settings.AUTH_STATE_COOKIE_NAME, "")
    if expected_state != state:
        raise HTTPException(status_code=400, detail={"error": "invalid_state", "message": "OIDC state cookie mismatch."})
    try:
        state_payload = verify_state(state)
        token_payload = exchange_code_for_token(code)
        access_token = token_payload.get("access_token") or token_payload.get("id_token")
        if not access_token:
            raise AuthError("oidc_token_missing", "OIDC token response did not include an access token", 502)
        user = validate_access_token(access_token)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"error": exc.code, "message": exc.message})

    response = RedirectResponse(url=state_payload.get("next_path") or settings.FRONTEND_APP_URL, status_code=302)
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    response.delete_cookie(settings.AUTH_STATE_COOKIE_NAME, path="/")
    response.headers["X-Authenticated-User"] = user.user_id
    return response


def _logout_response():
    response = RedirectResponse(url=settings.FRONTEND_APP_URL, status_code=302)
    response.delete_cookie(settings.AUTH_COOKIE_NAME, path="/")
    response.delete_cookie(settings.AUTH_STATE_COOKIE_NAME, path="/")
    return response


@router.get("/logout")
def auth_logout_get():
    return _logout_response()


@router.post("/logout")
def auth_logout():
    return _logout_response()


@router.get("/me")
def auth_me(request: Request):
    user = require_authenticated_user(request)
    return {"user": user.model_dump() if user else None}


@router.post("/local-dev-login")
def auth_local_dev_login(payload: LocalDevLoginRequest):
    if not local_dev_auth_enabled():
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Local dev login is not enabled."})
    user = authenticate_local_dev_user(payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail={"error": "invalid_credentials", "message": "Invalid local dev credentials."})
    access_token = issue_local_dev_token(user)
    redirect_path = resolve_post_login_path(user, payload.next_path)
    response = JSONResponse({"user": user.model_dump(), "redirect_path": redirect_path})
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/local-dev-assume")
def auth_local_dev_assume(payload: LocalDevAssumeRequest):
    if not local_dev_auth_enabled():
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Local dev assume is not enabled."})
    email = payload.email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail={"error": "invalid_email", "message": "Email is required."})
    local_part = email.split("@", 1)[0]
    user = build_local_dev_user(
        user_id=(payload.user_id or f"dev-{local_part}").strip(),
        email=email,
        name=payload.name,
        roles=payload.roles,
        groups=payload.groups,
        raw_claims={
            "manager_email": payload.manager_email,
            "manager_display_name": payload.manager_display_name,
            "manager_external_user_id": payload.manager_external_user_id,
        },
    )
    access_token = issue_local_dev_token(user)
    redirect_path = resolve_post_login_path(user, payload.next_path)
    response = JSONResponse({"user": user.model_dump(), "redirect_path": redirect_path})
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return response
