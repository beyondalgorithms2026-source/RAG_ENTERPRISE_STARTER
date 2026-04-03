This project is an enterprise-grade Retrieval-Augmented Generation (RAG) platform designed to enable users to upload documents in multiple formats, including PDF, DOCX, Excel, email, TXT, and others. The system can retrieve relevant information from within these documents and automate downstream actions based on content-driven rules and predefined parameters.

The platform provides administrators with extensive control over core components of the RAG pipeline, including the choice of embedding models, reranking methods, indexing strategies (such as vector, graph, keyword, or hybrid), LLM models, connected applications for automated actions, asynchronous ingestion options, and the ability to add new documents to an existing knowledge base even at the query stage.

It also supports enterprise access controls, including user-level access management, login and OAuth-based authentication, SSO, ACLs, and function-level filtering both before and after database retrieval. For sensitive documents or workflows, the system can incorporate human review checkpoints.

The solution includes an evaluation and continuous improvement framework based on sample Q&A benchmarking, along with a user feedback mechanism to improve retrieval quality and overall performance over time.

In addition, it is designed to integrate with existing cloud and database infrastructure, including AWS, Azure, Google Cloud, and on-premise environments, while supporting both open-source and widely used database technologies. It can also assess and incorporate the readiness of existing databases for RAG use cases, including factors such as indexing, chunking strategy, and current database/provider architecture.

Finally, the platform is built with granular customization and modularity in mind, allowing reusable building blocks across the codebase based on customer-specific requirements, while maintaining a master framework document that captures the full scope of the solution.

“This repo is forked-by-copy from `RAG_MM_MASTER_POC` as a baseline engine; enterprise features are added in milestones with explicit DoD checks.”


Commands to run the app:

The backend lives under `backend/app/main.py` and the primary frontend now lives under `web/`.

```bash
docker compose up -d

cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m app.db.migrate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
cd web
npm install
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run dev -- --port 3001
```

Then open:

- Marketing homepage: `http://127.0.0.1:3001/`
- Console login: `http://127.0.0.1:3001/login`
- Backend health: `http://127.0.0.1:8000/health`
- Legacy static frontend fallback: `http://127.0.0.1:8000/frontend/`

Notes:

- `requirements.txt` is in `backend/`, not the repo root.
- The ASGI app is `app.main:app`, not `app:app`.
- The app expects Postgres on `localhost:55432` by default, so `docker compose up -d` should happen first.
- Running `python -m app.db.migrate` before starting the server is recommended so the schema exists.
- Backend auth still owns the SSO flow; the Next.js app is the primary UI client.

Local dev login:

```bash
cd backend
source .venv/bin/activate
AUTH_ENABLED=true AUTH_MODE=dev FRONTEND_APP_URL=http://127.0.0.1:3001 uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd web
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 NEXT_PUBLIC_DEV_MODE=true npm run dev -- --port 3001
```

- Local dev user: `test-user@ragenterprise.local` / `password123`
- Local dev admin: `test-admin@ragenterprise.local` / `password123`
- Shortcut: `make dev-web`
