from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.auth.dependencies import require_authenticated_user
from app.auth.service import AuthError, build_login_url, exchange_code_for_token, get_oidc_metadata, validate_access_token, verify_state
from app.core.config import settings


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/providers")
def auth_providers():
    if not settings.AUTH_ENABLED:
        return {"auth_enabled": False, "providers": []}
    metadata = get_oidc_metadata()
    return {
        "auth_enabled": True,
        "providers": [
            {
                "issuer": metadata.get("issuer"),
                "authorization_endpoint": metadata.get("authorization_endpoint"),
                "token_endpoint": metadata.get("token_endpoint"),
            }
        ],
    }


@router.get("/login")
def auth_login(next_path: str = Query(default="/frontend/")):
    if not settings.AUTH_ENABLED:
        raise HTTPException(status_code=503, detail={"error": "auth_disabled", "message": "Authentication is disabled."})
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

    response = RedirectResponse(url=state_payload.get("next_path") or "/frontend/", status_code=302)
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


@router.post("/logout")
def auth_logout():
    response = RedirectResponse(url="/frontend/", status_code=302)
    response.delete_cookie(settings.AUTH_COOKIE_NAME, path="/")
    response.delete_cookie(settings.AUTH_STATE_COOKIE_NAME, path="/")
    return response


@router.get("/me")
def auth_me(request: Request):
    user = require_authenticated_user(request)
    return {"user": user.model_dump() if user else None}
