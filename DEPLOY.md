# Deploying the RAG enterprise Starter API on Coolify

Branch `deploy/coolify` (made from `main`). The container runs the FastAPI backend on port 8000 with **hosted** embedding and
language-model APIs and the existing Supabase Postgres (pgvector). No local model is loaded, so memory stays small.
Do not install `backend/requirements-local.txt` on the server: it adds torch (2-3 GB of memory).

## Coolify fields

| Field | Value |
|---|---|
| Build pack | Dockerfile |
| Base directory | `/` |
| Dockerfile location | `/Dockerfile` |
| Ports Exposes | 8000 |
| Domain | https://ragapi.spanfold.com |
| Health check path | `/healthz` (HTTP 200, `{"status":"ok"}`; no database call) |
| Persistent storage | Volume, destination path `/data` |
| Memory limit | 512 MB |
| Replicas | 1 (single process by design) |

DNS: add an A record `ragapi` pointing at the server.

## Environment variables to type in

Names match `backend/.env.example` (the deploy section is at the bottom). Values below come from `render.yaml`, which is what runs today.

- **Secrets (mark "Is secret"):** `DATABASE_URL` (Supabase session-pooler address), `EMBEDDING_API_KEY`, `LLM_API_KEY`, and `AUTH_STATE_SIGNING_SECRET` / `DEV_LOCAL_JWT_SECRET` only if you change `AUTH_MODE` away from `none`.
- **Same as Render today:** `APP_ENV=demo`, `AUTH_ENABLED=false`, `AUTH_MODE=none`, `AUTH_NONE_ALLOW_UPLOAD=false`, `PUBLIC_DEMO_AUTOSEED=true`, `ACCESS_STRATEGY=document_acl_with_time_bound_grants`, `RATE_LIMIT_ENABLED=true`, `RATE_LIMIT_ASK_PER_MINUTE=12`, `RATE_LIMIT_SEARCH_PER_MINUTE=10`, `RATE_LIMIT_UPLOAD_PER_MINUTE=0`, `RATE_LIMIT_ADMIN_EXPENSIVE_PER_MINUTE=0`, `CONNECTOR_SCHEDULER_ENABLED=false`, `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS=384`, `EMBEDDING_BASE_URL`, `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_TIMEOUT_S=60`, `LLM_MAX_TOKENS=2048`, `LLM_COST_ALERT_USD=0.01`, and every `ENABLE_*`, `EXTRACT_*`, `BUILD_GRAPH_ON_INGEST`, `ALLOW_LAZY_ENRICHMENT`, `RERANK_ENABLED` set to `false`.
- **New for the VPS:**
  - `ALLOWED_ORIGINS=https://governance.spanfold.com,https://spanfold.com,https://www.spanfold.com` (browser access; add the evaluation page's origin if it still calls this API from a browser)
  - `FRONTEND_APP_URL` = the https address of the page people land on
  - `DAILY_SPEND_CAP_USD=0.50`, `MONTHLY_SPEND_CAP_USD=5`, `EST_COST_PER_CALL_USD=0.002`, `EMBED_PRICE_PER_MTOK=0.02`
- **Baked into the image:** `UPLOAD_DIR=/data/uploads`, `SPEND_DB_PATH=/data/spend.sqlite`, `WEB_CONCURRENCY=1`.

The older `API_ALLOWED_ORIGINS` still works; `ALLOWED_ORIGINS` wins when both are set.

## Spend caps and 429

Every model call is counted in `/data/spend.sqlite` from the token usage in the provider's reply (or `EST_COST_PER_CALL_USD` if none). Embedding calls are counted too. Over the daily or monthly cap, ask, search and upload answer HTTP 429: "This demo has reached its daily limit. Please try again tomorrow." `/healthz`, `/health`, sign-in and admin routes keep working. If the ledger file cannot be read, visitors are not blocked.

## Keep Supabase awake (Scheduled Task)

Supabase pauses free projects with no real database activity. `/healthz` deliberately does not touch the database, so a separate task does.

| Field | Value |
|---|---|
| Scheduled Task name | supabase-keepalive |
| Frequency | `0 6 * * *` (daily, 06:00) |
| Command | `python scripts/keepalive.py` |
| Container | this application |

The script runs `SELECT COUNT(*) FROM sources` through the app's own database engine and exits with code 1 if it fails, so a failed run shows red in Coolify. It prints the error type only, never the connection string.

## Memory estimate

About 250-400 MB with the Render settings (hosted models, graph and rerank off). Start-up runs migrations and seeds the public demo corpus once, which briefly adds some memory and a small embedding bill.

## What changed from Render

- New `Dockerfile` and `.dockerignore`; `/healthz`; spend caps; `ALLOWED_ORIGINS`; `scripts/keepalive.py`.
- CORS: localhost origins only when `APP_ENV=local` (before, `dev` also allowed them). Cross-origin methods are now `GET`, `POST`, `OPTIONS` (before: also `PATCH`, `DELETE`). The admin console must be served from the same origin as the API for those.
- `render.yaml` is untouched, so Render keeps working.

## Before you build

The Docker engine was not running when this was prepared, so the image has not been built. The first Coolify build is its first real test.
Database-backed tests need a live migrated Postgres and were skipped (36 skipped, 171 ran and passed).
