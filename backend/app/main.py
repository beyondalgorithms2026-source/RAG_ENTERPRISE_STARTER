from pathlib import Path
import secrets

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from .api.auth import router as auth_router
from .api.ask import router as ask_router
from .api.compare import router as compare_router
from .api.deep_lookup import router as deep_lookup_router
from .api.health import router as health_router
from .api.search import router as search_router
from .api.upload import router as upload_router
from .api.corpus import router as corpus_router
from .api.admin import router as admin_router
from .api.actions import router as actions_router
from .api.access_requests import router as access_requests_router
from .auth.admin_modules import enforce_admin_module_for_request
from .auth.context import reset_current_user, set_current_user
from .auth.service import AuthError, authenticate_request, validate_security_posture
from .core.config import settings
from .db.migrate import run_migrations
from .db.repo_acl import sync_authenticated_user
from .ingestion.queue_runtime import start_ingestion_queue_worker

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="RAG enterprise Starter", version="0.1.0")


def _csv(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _allowed_cors_origins() -> list[str]:
    configured = _csv(settings.API_ALLOWED_ORIGINS)
    if configured:
        return configured
    if (settings.APP_ENV or "local").strip().lower() not in {"local", "dev"}:
        return [settings.FRONTEND_APP_URL.rstrip("/")]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_cors_origins(),
    allow_credentials=True,
    allow_methods=["OPTIONS", "POST", "GET", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization", settings.CSRF_HEADER_NAME],
)


def _request_uses_cookie_auth(request: Request) -> bool:
    authorization = request.headers.get("Authorization", "").strip().lower()
    return not authorization.startswith("bearer ") and bool(request.cookies.get(settings.AUTH_COOKIE_NAME))


def _csrf_required_for_request(request: Request) -> bool:
    if (settings.APP_ENV or "local").strip().lower() not in {"local", "dev"}:
        return True
    origin = request.headers.get("Origin", "").strip().rstrip("/")
    if not origin:
        return False
    allowed_origins = {item.rstrip("/") for item in _allowed_cors_origins()}
    return origin not in allowed_origins


def _enforce_csrf_if_needed(request: Request) -> None:
    if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return
    if request.url.path in {"/auth/local-dev-login", "/auth/local-dev-assume"}:
        return
    if not _request_uses_cookie_auth(request):
        return
    if not _csrf_required_for_request(request):
        return
    csrf_cookie = request.cookies.get(settings.CSRF_COOKIE_NAME, "")
    csrf_header = request.headers.get(settings.CSRF_HEADER_NAME, "")
    if not csrf_cookie or not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(
            status_code=403,
            detail={"error": "csrf_required", "message": "Cookie-authenticated mutations require a valid CSRF header."},
        )


def _apply_security_headers(response) -> None:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'")
    if (settings.APP_ENV or "local").strip().lower() not in {"local", "dev"}:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")


@app.middleware("http")
async def auth_context_middleware(request: Request, call_next):
    request.state.user = None
    request.state.auth_error = None
    token = set_current_user(None)
    try:
        try:
            user = authenticate_request(request)
            request.state.user = user
            sync_authenticated_user(user)
            reset_current_user(token)
            token = set_current_user(user)
        except AuthError as exc:
            request.state.auth_error = exc
        _enforce_csrf_if_needed(request)
        if request.state.user and "admin" in {role.lower() for role in request.state.user.roles}:
            enforce_admin_module_for_request(request)
        response = await call_next(request)
        _apply_security_headers(response)
        return response
    except AuthError as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": {"error": exc.code, "message": exc.message}})
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    finally:
        reset_current_user(token)

app.include_router(auth_router)
app.include_router(health_router)
app.include_router(search_router)
app.include_router(deep_lookup_router)
app.include_router(ask_router)
app.include_router(compare_router)
app.include_router(upload_router)
app.include_router(corpus_router)
app.include_router(actions_router)
app.include_router(access_requests_router)
app.include_router(admin_router)


@app.on_event("startup")
def start_background_workers() -> None:
    validate_security_posture()
    run_migrations()
    start_ingestion_queue_worker()


@app.get("/", include_in_schema=False)
def ui_root():
    return RedirectResponse(url=settings.FRONTEND_APP_URL)


app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
