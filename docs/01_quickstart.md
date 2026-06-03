# Quickstart

This is the canonical local run path for Enterprise RAG Starter.

If you are new to the repo, read these first:

1. [README.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/README.md)
2. [STATUS.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/STATUS.md)
3. [docs/04_repo_navigation_blueprint.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/04_repo_navigation_blueprint.md)

## What should be running

You need:

- Postgres via Docker
- Ollama for the local LLM path
- FastAPI backend on `127.0.0.1:8000`
- Next.js frontend on `127.0.0.1:3001`

## Canonical paths

- Active backend: `backend/`
- Active frontend: `web/`
- Legacy compatibility UI: `frontend/`

Use `web/` for normal development. Treat `frontend/` as fallback-only unless you are explicitly validating `/frontend`.

## First run

### 1. Start Postgres

```bash
cd /Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER
docker compose up -d
docker compose ps
```

### 2. Ensure Ollama is available

```bash
ollama list
ollama pull llama3.2:3b
```

### 3. Prepare frontend env

```bash
cp web/.env.example web/.env.local
```

Suggested values:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_DEV_MODE=true
```

`web/.env.local` is local-only and ignored by git.

### 4. Start backend

```bash
cd /Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/backend
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
python -m app.db.migrate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 5. Start frontend

```bash
cd /Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/web
pnpm install
pnpm run dev -- --port 3001
```

### 6. Open the app

- Frontend: `http://127.0.0.1:3001`
- Login: `http://127.0.0.1:3001/login`
- Backend health: `http://127.0.0.1:8000/health`

Local dev accounts:

- `test-user@ragenterprise.local` / `password123`
- `test-admin@ragenterprise.local` / `password123`

## Shortcuts

If Docker/Postgres and Ollama are already running:

```bash
cd /Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER
make dev-web
```

## Related docs

- Local run details: [docs/runbooks/LOCALHOST_DEV_RUNBOOK.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/runbooks/LOCALHOST_DEV_RUNBOOK.md)
- Repo workflow: [docs/runbooks/SOURCE_CONTROL_WORKFLOW.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/runbooks/SOURCE_CONTROL_WORKFLOW.md)
- Safe extension path: [docs/runbooks/SAFE_EXTENSION_BLUEPRINT.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/runbooks/SAFE_EXTENSION_BLUEPRINT.md)
