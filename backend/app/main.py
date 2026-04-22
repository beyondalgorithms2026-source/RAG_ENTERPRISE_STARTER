from pathlib import Path

from fastapi import FastAPI, Request
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
from .auth.context import reset_current_user, set_current_user
from .auth.service import AuthError, authenticate_request
from .core.config import settings
from .db.migrate import run_migrations
from .db.repo_acl import sync_authenticated_user
from .ingestion.queue_runtime import start_ingestion_queue_worker

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="RAG enterprise Starter", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["OPTIONS", "POST", "GET", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization"],
)


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
        response = await call_next(request)
        return response
    except AuthError as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": {"error": exc.code, "message": exc.message}})
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
app.include_router(admin_router)


@app.on_event("startup")
def start_background_workers() -> None:
    run_migrations()
    start_ingestion_queue_worker()


@app.get("/", include_in_schema=False)
def ui_root():
    return RedirectResponse(url=settings.FRONTEND_APP_URL)


app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
