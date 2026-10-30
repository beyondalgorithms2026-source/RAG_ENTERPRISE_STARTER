# RAG enterprise Starter API (FastAPI) - port 8000. Built for Coolify (build pack: Dockerfile, base directory /).
# Hosted models only (EMBEDDING_PROVIDER=openai-style API, LLM over HTTPS). Do not install requirements-local.txt here:
# it pulls torch and needs several GB of memory.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WEB_CONCURRENCY=1 \
    UPLOAD_DIR=/data/uploads \
    SPEND_DB_PATH=/data/spend.sqlite

# The app finds its siblings (frontend/, corpus/, eval/) relative to backend/, so keep the repository layout.
WORKDIR /srv/backend

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /srv/backend/
COPY frontend/ /srv/frontend/
COPY corpus/ /srv/corpus/
COPY eval/ /srv/eval/

# Non-root user. /data is where the volume is mounted: spend ledger and uploaded/seeded documents.
RUN useradd --system --uid 10001 --no-create-home app \
    && mkdir -p /data/uploads \
    && chown -R app:app /data /srv
USER app

EXPOSE 8000

# Slim images have no curl, so the check uses Python. /healthz calls no model and no database.
# The long start period covers migrations and the first seed at start-up.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"

# One worker only: the app keeps its ingestion queue and rate limits in this process.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
