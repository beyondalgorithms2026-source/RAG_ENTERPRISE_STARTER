from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from .api.ask import router as ask_router
from .api.compare import router as compare_router
from .api.deep_lookup import router as deep_lookup_router
from .api.health import router as health_router
from .api.search import router as search_router
from .api.upload import router as upload_router
from .api.corpus import router as corpus_router

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="RAG enterprise Starter", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["OPTIONS", "POST", "GET"],
    allow_headers=["Content-Type"],
)

app.include_router(health_router)
app.include_router(search_router)
app.include_router(deep_lookup_router)
app.include_router(ask_router)
app.include_router(compare_router)
app.include_router(upload_router)
app.include_router(corpus_router)


@app.get("/", include_in_schema=False)
def ui_root():
    return RedirectResponse(url="/frontend/")


app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
