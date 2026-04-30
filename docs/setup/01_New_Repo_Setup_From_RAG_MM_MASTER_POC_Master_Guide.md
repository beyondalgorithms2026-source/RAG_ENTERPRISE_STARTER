# New Repo Setup Guide (from `RAG_MM_MASTER_POC`) — baby steps

**Purpose**  
You want to create a *new* repo from scratch while reusing `RAG_MM_MASTER_POC` as safely as possible, without an AI tool auto-moving files for you. This guide is a “master checklist + copy plan” that minimizes breakage and keeps you aligned with the repo’s intended adoption path (upload → parse → chunk → embed → search/ask → eval).

**What this guide assumes**
- You already have a working `RAG_MM_MASTER_POC` repo on your machine.
- You want a new project repo (new folder) that can run the same baseline behavior first, *then* you’ll add enterprise features in later milestones.
- You want to do the file moves yourself and reduce “mystery breakage.”

**What this guide does NOT do**
- It does not add new features (SSO/ACL/admin/tools). It is only about creating a clean new repo that runs baseline correctly.

---

## 0) The non-negotiables (read once)

These are the “rules” that prevent you from accidentally breaking the engine:

1. **Do not change retrieval internals first.** Start with the current schema and baseline upload → search → ask flow.  
2. **Start with mode=`hybrid`.** Treat `graph_hybrid`, `full`, router, compare as optional layers after baseline is stable.  
3. **Change providers/adapters before changing retrieval.** If you want different embedding/LLM providers later, do it after baseline works.  
4. **Keep metadata contracts stable.** Casual edits to metadata shapes can break retrieval, router, compare, eval in subtle ways.  
5. **Respect current maturity:** strong reusable PoC base; not yet enterprise platform. Start stable, then extend deliberately.

*(These principles mirror the repo’s own “Safest default usage path / What to keep vs what to replace / Known limitations” guidance.)*

---

## 1) Create the new repo (folder) with a clean identity

### 1.1 Create a new folder and init git
```bash
mkdir RAG_ENTERPRISE_STARTER
cd RAG_ENTERPRISE_STARTER
git init
```

### 1.2 Decide your new repo name and “product identity”
Create these files now (even if placeholders):
- `README.md` (1 paragraph: what it is, what it is not)
- `STATUS.md` (your milestones + what’s done)
- `docs/` folder

```bash
mkdir -p docs backend frontend
touch README.md STATUS.md
```

**Tip:** Add a one-line statement in README like:  
> “This repo is forked-by-copy from `RAG_MM_MASTER_POC` as a baseline engine; enterprise features are added in milestones with explicit DoD checks.”

---

## 2) Copy only what you need from `RAG_MM_MASTER_POC` (safe copy plan)

### 2.1 Copy the backend
From your existing repo folder (adjust path):
```bash
cp -R ~/local_dev/"rag workflow"/RAG_MM_MASTER_POC/backend ./backend
```

### 2.2 Copy docker-compose and top-level run docs (if present)
```bash
cp ~/local_dev/"rag workflow"/RAG_MM_MASTER_POC/docker-compose.yml ./docker-compose.yml
cp ~/local_dev/"rag workflow"/RAG_MM_MASTER_POC/README.md ./docs/README_from_master.md
cp ~/local_dev/"rag workflow"/RAG_MM_MASTER_POC/docs/master_guide.md ./docs/master_guide.md
cp -R ~/local_dev/"rag workflow"/RAG_MM_MASTER_POC/docs ./docs/_master_docs
```

### 2.3 Copy the frontend (only as demo shell)
```bash
cp -R ~/local_dev/"rag workflow"/RAG_MM_MASTER_POC/frontend ./frontend
```

### 2.4 What NOT to copy (on purpose)
Do **not** copy:
- any local `.env` files with secrets
- any local `uploads/`, `data/`, `outputs/`, `reports/` folders unless you’re using them as fixtures
- any venv folders (`.venv/`, `venv/`) or node_modules

---

## 3) Re-stamp the repo: rename references + documentation

### 3.1 Update “repo identity strings”
Search/replace the old name in:
- `README.md`
- `docs/*`
- `backend/*` (only if hard-coded project name appears)

Use ripgrep:
```bash
rg -n "RAG_MM_MASTER_POC" .
```
Then edit occurrences. Keep it minimal—don’t touch code behavior.

### 3.2 Create your own docs “entry points”
Create:
- `docs/01_quickstart.md` (how to run locally)
- `docs/02_architecture.md` (copy your canonical diagram + summary)
- `docs/03_adoption_rules.md` (the “non-negotiables” from section 0)

---

## 4) Environment: run baseline locally (no changes yet)

### 4.1 Backend Python environment
From repo root:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4.2 Configure environment variables
Copy example env file:
```bash
cp .env.example .env
```

Now open `.env` and fill in:
- DB connection values (match docker-compose)
- LLM provider keys if required for `/ask`
- embedding model settings if required

**Rule:** keep all secrets out of git. Add `.env` to `.gitignore`.

### 4.3 Start Postgres + pgvector
From repo root:
```bash
docker compose up -d
```

Confirm DB is up:
```bash
docker ps
```

### 4.4 Run DB migrations / schema setup
The repo typically has a lightweight migration approach. Run the provided migration/verify step.
Examples (use whatever your repo provides):
```bash
cd backend
python -m app.db.migrate
python -m app.db.verify_db
```

If the repo uses `schema.sql`, ensure it’s applied by the migration script.

### 4.5 Start backend API
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Test:
- `GET /health`
- `GET /corpus` (likely empty until uploads)

---

## 5) Baseline smoke run (the “don’t break” checklist)

Your success condition here is **not** “it runs.” It is “baseline behavior matches the master.”

### 5.1 Upload a sample document
Use the UI or curl. Example (adjust endpoint/path):
```bash
curl -F "file=@/~/local_dev/"rag workflow"/sample.pdf" http://localhost:8000/upload
```

### 5.2 Confirm corpus state
```bash
curl http://localhost:8000/corpus
```

### 5.3 Run `/search` in `hybrid`
```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query":"termination notice period", "mode":"hybrid"}'
```

### 5.4 Run `/ask` and confirm citations
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the termination notice period?", "mode":"hybrid"}'
```

**Pass criteria:**
- you get an answer
- you get citations (chunk/source provenance)
- no crash; no empty retrieval when data is clearly present

---

## 6) Evaluation harness smoke run (must pass before any feature work)

### 6.1 Run the baseline eval harness
Your repo has eval modules (retrieval/answer/compare/bench). Run the simplest one first.
Examples (adapt to actual commands in your repo):
```bash
cd backend
python -m app.eval.retrieval_eval --mode hybrid
python -m app.eval.enriched_eval --mode hybrid
```

**Pass criteria:**
- reports generated
- no schema errors
- results consistent with expectation

### 6.2 Snapshot your “baseline known-good”
Create a folder:
- `reports/baseline/`
Store:
- eval output JSON
- git commit hash
- config snapshot (redacted)

---

## 7) Freeze the baseline (so future changes are measurable)

### 7.1 Create a “baseline lock” tag
```bash
git add -A
git commit -m "Baseline import from RAG_MM_MASTER_POC: upload/search/ask/eval stable"
git tag baseline-import-stable
```

### 7.2 Create a “change discipline” rule
In `docs/03_adoption_rules.md`, add:
- Every milestone must include: (a) DoD, (b) which tests/evals to rerun, (c) rollback plan.

---

## 8) Common breakages and how to debug (fast)

### 8.1 DB connection / pgvector issues
- Verify Postgres container is running
- Verify DB URL in `.env`
- Verify extension installed (`CREATE EXTENSION vector;`)
- Run verify script

### 8.2 “Upload works but search returns nothing”
Common causes:
- ingestion didn’t chunk/embed (check ingestion job records)
- embedding model misconfigured / dimension mismatch
- wrong `mode` default (force `hybrid` explicitly)
- schema not migrated correctly

### 8.3 “Ask fails but search works”
Common causes:
- LLM key missing
- LLM client config mismatch
- prompt expects citations but retrieval payload missing fields

### 8.4 “Eval fails”
- fixture paths wrong
- tests expect local Postgres reachable
- reports path not writeable

---

## 9) What you do next (do NOT skip this ordering)

Once baseline is stable:
1. Add “profiles” (embedding/reranker/LLM/eval-pack registry) **without changing baseline behavior**.
2. Add SSO + ACL trimming before tools and admin actions.
3. Only then build admin UI and tool actions.

That’s the sequence that prevents you from rebuilding everything twice.

---

## Appendix A — Minimal repo layout (recommended)

```text
RAG_ENTERPRISE_STARTER/
├── README.md
├── STATUS.md
├── docker-compose.yml
├── backend/
├── frontend/              # demo UI (later: replace with real apps)
├── docs/
│   ├── 01_quickstart.md
│   ├── 02_architecture.md
│   ├── 03_adoption_rules.md
│   ├── master_guide.md     # copied for reference
│   └── _master_docs/       # optional full docs mirror
└── reports/
    └── baseline/
```

---

## Appendix B — What “done” looks like for setup

You are done with this guide when:
- you can `docker compose up -d`
- you can upload a file
- `/search` in `hybrid` returns relevant chunks
- `/ask` returns grounded answer with citations
- eval harness runs and produces reports
- you committed + tagged `baseline-import-stable`
