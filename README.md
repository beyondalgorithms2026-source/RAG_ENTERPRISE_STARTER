This project is an enterprise-grade Retrieval-Augmented Generation (RAG) platform designed to enable users to upload documents in multiple formats, including PDF, DOCX, Excel, email, TXT, and others. The system can retrieve relevant information from within these documents and automate downstream actions based on content-driven rules and predefined parameters.

The platform provides administrators with extensive control over core components of the RAG pipeline, including the choice of embedding models, reranking methods, indexing strategies (such as vector, graph, keyword, or hybrid), LLM models, connected applications for automated actions, asynchronous ingestion options, and the ability to add new documents to an existing knowledge base even at the query stage.

It also supports enterprise access controls, including user-level access management, login and OAuth-based authentication, SSO, ACLs, and function-level filtering both before and after database retrieval. For sensitive documents or workflows, the system can incorporate human review checkpoints.

The solution includes an evaluation and continuous improvement framework based on sample Q&A benchmarking, along with a user feedback mechanism to improve retrieval quality and overall performance over time.

In addition, it is designed to integrate with existing cloud and database infrastructure, including AWS, Azure, Google Cloud, and on-premise environments, while supporting both open-source and widely used database technologies. It can also assess and incorporate the readiness of existing databases for RAG use cases, including factors such as indexing, chunking strategy, and current database/provider architecture.

Finally, the platform is built with granular customization and modularity in mind, allowing reusable building blocks across the codebase based on customer-specific requirements, while maintaining a master framework document that captures the full scope of the solution.

For reuse planning, start with `docs/scenario_profiles_and_reuse_blueprint.md`. It maps the repo into modules and explains which blocks to keep, disable, or replace for small-enterprise corpus access, employee-wide RAG, trusted no-auth research, and full enterprise OIDC + ACL + governance scenarios.

“This repo is forked-by-copy from `RAG_MM_MASTER_POC` as a baseline engine; enterprise features are added in milestones with explicit DoD checks.”


## 🚀 First Run (2026 Setup)

Use the actual local repo path:

```bash
cd /Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER
```

### 1. Persist Postgres on the host

Create the backup folder:

```bash
mkdir -p /Users/Work/Projects/Backup/Database/rag-enterprise-pgdata
```

Update `docker-compose.yml` so the database volume is:

```yaml
volumes:
  - /Users/Work/Projects/Backup/Database/rag-enterprise-pgdata:/var/lib/postgresql/data
```

Start Postgres:

```bash
docker compose up -d
docker compose ps
```

### 2. Pull the Ollama model

```bash
ollama pull llama3.2:3b
```

### 3. Optional: restore an existing backup

Plain SQL dump:

```bash
docker exec -i rag_enterprise_starter_db psql \
  -U rag_enterprise_starter \
  -d rag_enterprise_starter < /absolute/path/to/backup.sql
```

Custom dump:

```bash
docker exec -i rag_enterprise_starter_db pg_restore \
  --clean --if-exists --no-owner --no-privileges \
  -U rag_enterprise_starter \
  -d rag_enterprise_starter < /absolute/path/to/backup.dump
```

### 4. Frontend env file

```bash
cp web/.env.example web/.env.local
```

Set the frontend env in `web/.env.local`:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_DEV_MODE=true
```

### 5. Confirm backend env values

Make sure your restored `backend/.env` includes:

```dotenv
AUTH_ENABLED=true
AUTH_MODE=dev
FRONTEND_APP_URL=http://127.0.0.1:3001
LLM_PROVIDER=ollama
LLM_BASE_URL=http://localhost:11434
LLM_MODEL=llama3.2:3b
```

Security mode quick guide:

- `AUTH_MODE=none`: trusted research/no-sensitive-data mode. Search/ask are available, admin stays protected, and upload is disabled unless `AUTH_NONE_ALLOW_UPLOAD=true`.
- `AUTH_MODE=dev`: local learning mode with built-in test user/admin identities. Use only with `APP_ENV=local` or `APP_ENV=dev`.
- `AUTH_MODE=password`: reserved for a future small-enterprise username/password module.
- `AUTH_MODE=oidc`: enterprise SSO mode for staging/prod. Use strong non-default auth secrets.

Security hardening notes:

- Non-local environments require HTTPS frontend URLs, strong auth/database secrets, secure cookies, and configured CORS origins.
- Cookie-authenticated `POST`, `PATCH`, and `DELETE` requests require the CSRF cookie value to be echoed in `X-CSRF-Token`.
- High-impact admin actions such as ACL edits, tuning promotion/rollback, cache clearing, retention runs, model warm-up, and audit export require a separate `X-Approval-Actor` header outside local/dev.
- Office parsers reject unsafe archive expansion patterns before DOCX/PPTX/XLSX parsing.
- Model warm-up accepts approved registry model names only by default.

### 6. Python setup with `uv`

Open one terminal for the backend:

```bash
cd /Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/backend
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
python -m app.db.migrate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Notes:
- Keep this backend terminal open while the server runs.
- If you open a new backend terminal later, run `source .venv/bin/activate` again first.

### 7. Frontend setup with `pnpm`

Open a second terminal for the frontend:

```bash
cd /Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/web
rm -f package-lock.json
pnpm install
pnpm run dev -- --port 3001
```

### 8. Open the app

- Frontend: `http://127.0.0.1:3001`
- Login: `http://127.0.0.1:3001/login`
- Backend health: `http://127.0.0.1:8000/health`

Local dev accounts:

- `test-user@ragenterprise.local` / `password123`
- `test-admin@ragenterprise.local` / `password123`

### Notes

- This repo currently uses custom SQLAlchemy migrations, not Prisma or Drizzle.
- Python is managed with `uv`, but dependencies still come from `backend/requirements.txt`.
- Node should be managed with `pnpm`; `npm` and `package-lock.json` should be retired from this repo.
- The first migration may download the embedding model used to size the `vector(...)` column.
- `llama3.2:3b` is the recommended lightweight Ollama model for this first run on an 8GB Mac.
