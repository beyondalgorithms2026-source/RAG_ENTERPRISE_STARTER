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
from .auth.context import reset_current_user, set_current_user
from .auth.service import AuthError, authenticate_request
from .db.repo_acl import sync_authenticated_user

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="RAG enterprise Starter", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["OPTIONS", "POST", "GET", "DELETE"],
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
app.include_router(admin_router)


@app.get("/", include_in_schema=False)
def ui_root():
    return RedirectResponse(url="/frontend/")


app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
