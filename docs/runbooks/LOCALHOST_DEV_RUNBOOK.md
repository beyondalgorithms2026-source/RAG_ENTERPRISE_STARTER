# Localhost Dev Runbook

This is the shortest path to run the app locally for development and testing.

## What should be running

You need 4 things:
- Docker Desktop for Postgres
- Ollama for the local LLM
- FastAPI backend on `127.0.0.1:8000`
- Next.js frontend on `127.0.0.1:3001`

## Assumptions

- Repo path:

```bash
cd /path/to/RAG_ENTERPRISE_STARTER
```

- Postgres data should live at:

```bash
/path/to/Projects/Backup/Database/rag-enterprise-pgdata
```

- Backend env already exists at `backend/.env`
- Frontend env exists at `web/.env.local`
- `web/.env.local` is local-only and intentionally ignored by git
- Recommended Ollama model: `llama3.2:3b`

## Terminal 1: Start Docker / Postgres

```bash
cd /path/to/RAG_ENTERPRISE_STARTER
mkdir -p /path/to/Projects/Backup/Database/rag-enterprise-pgdata
docker compose up -d
docker compose ps
```

Expected:
- container `rag_enterprise_starter_db` is up
- Postgres is exposed on `localhost:55432`

## Terminal 2: Start Ollama

If Ollama is not already running:

```bash
ollama serve
```

In another terminal, confirm the model exists:

```bash
ollama list
```

If `llama3.2:3b` is missing:

```bash
ollama pull llama3.2:3b
```

## Terminal 3: Start Backend

```bash
cd /path/to/RAG_ENTERPRISE_STARTER/backend
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
python -m app.db.migrate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Notes:
- Keep this terminal open
- If `.venv` already exists, `uv venv .venv` is safe to rerun
- If you open a new backend terminal later, run:

```bash
cd /path/to/RAG_ENTERPRISE_STARTER/backend
source .venv/bin/activate
```

## Terminal 4: Start Frontend

```bash
cd /path/to/RAG_ENTERPRISE_STARTER/web
pnpm install
pnpm run dev --port 3001
```

Keep this terminal open too.

## Canonical frontend path

- Active product UI: `web/`
- Legacy compatibility UI: `frontend/` served at `/frontend`

Use `web/` for all normal development. Treat `frontend/` as fallback-only unless a task explicitly targets legacy compatibility.

## Fast shortcut

If backend deps and frontend deps are already installed, you can also use:

```bash
cd /path/to/RAG_ENTERPRISE_STARTER
make dev-web
```

Use this only after Docker/Postgres and Ollama are already running.

## URLs to test

Open these in the browser:

- Frontend home: `http://127.0.0.1:3001`
- Login: `http://127.0.0.1:3001/login`
- Backend health: `http://127.0.0.1:8000/health`

## Local dev login

- User: `test-user@ragenterprise.local` / `<the value you set in DEV_TEST_USER_PASSWORD>`
- Admin: `test-admin@ragenterprise.local` / `<the value you set in DEV_TEST_USER_PASSWORD>`

## Quick verification commands

Backend health:

```bash
curl http://127.0.0.1:8000/health
```

Ollama models:

```bash
ollama list
```

Postgres container:

```bash
docker compose ps
```

## Common issues

If login looks SSO-first but local dev auth is enabled:
- use the local dev login path on the login page

If backend fails to start:
- confirm `backend/.env` exists
- confirm `DATABASE_URL` points to `localhost:55432`
- confirm Docker/Postgres is running

If frontend fails to call backend:
- confirm `web/.env.local` contains:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_DEV_MODE=true
```

If git shows unexpected frontend noise after local work:
- confirm you did not commit `web/.env.local`
- confirm build output stays ignored
- run `make repo-hygiene-check`

If Ollama calls fail:
- confirm `ollama serve` is running
- confirm `backend/.env` contains:

```dotenv
LLM_PROVIDER=ollama
LLM_BASE_URL=http://localhost:11434
LLM_MODEL=llama3.2:3b
```
