# Contributing

Thank you for improving the governed RAG data layer. Read `README.md`, `STATUS.md`,
[`AGENTS.md`](../AGENTS.md), and `CLAUDE.md` before changing this repository. Also read
the canonical
[B004 engineering standard](https://github.com/beyondalgorithms2026-source/RAG_ENTERPRISE_LANGGRAPH_APP/blob/main/docs/ENGINEERING_STANDARDS.md).
The local guides contain enough essential information for safe work when APP is
unavailable; preserve the stricter rule when instructions overlap. These documents are
contributor guidance, while named CI and test checks provide mechanical enforcement.

The active backend is under `backend/` and the active operator console is under `web/`.
Do not add new work to the legacy `frontend/` directory. Access control must remain in
retrieval SQL, citation provenance must be preserved, and unsupported answers must remain
safe not-found responses.

## Development setup

The supported local setup uses Docker and Python 3.12:

```bash
docker compose up -d
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-local.txt
cp .env.example .env
python -m app.db.migrate
```

Set required local values in `.env` without sharing, printing, or committing them. See
`docs/01_quickstart.md` for corpus generation, seeding, and service startup.

The root `pyproject.toml` configures repository tooling. `backend/requirements.txt` is
the runtime dependency source of truth; `backend/requirements-local.txt` adds the local
embedding stack.

## Before opening a pull request

Run the checks appropriate to the change:

```bash
make test
make reader-clarity-check
make repo-hygiene-check
python3 -m ruff check .
python3 -m ruff format --check .
```

For authentication, ACL, or module-boundary changes, also run:

```bash
make scenario-validate
```

For active frontend changes, first read `web/DESIGN.md`, then run:

```bash
cd web
npx tsc --noEmit
pnpm run build
```

Database-bound tests require a live migrated Postgres. Set `RAG_REQUIRE_DB=1` in a job
that is expected to provide it so missing database coverage fails rather than silently
skips. Report actual passes and skips in the pull request.

Install and run the repository hooks when contributing locally:

```bash
python -m pip install pre-commit
pre-commit install
pre-commit run --all-files
```

CI requires `lint`, `Offline tests`, and `security`. It checks Ruff formatting and lint,
runs the offline unittest suite and documentation/hygiene checks, scans committed history
for secrets, and audits Python dependencies.

Never commit credentials, `.env` files, corpus data, or generated local reports. Ask
before adding dependencies or changing authentication, access control, retrieval,
embedding, or governance behaviour.

P12 is APP's fast mocked evaluation-harness smoke test. P12B is the authoritative real
APP → MCP → STARTER → PostgreSQL/pgvector 25-question gate. Quality-sensitive retrieval,
embedding, prompt, ACL, citation, or answer/refusal changes must include the applicable
evaluation evidence. Mocked tests do not prove live retrieval or SQL ACL enforcement.
P12B baselines must never be automatically overwritten after regression; every baseline
change must be explicit, justified, and owner/CODEOWNER-reviewed.

## Protected branch policy

Changes to `main` should go through a pull request with all required CI checks passing,
all review conversations resolved, and a CODEOWNERS review when an eligible second
maintainer is available. Force pushes and branch deletion are disabled. A solo owner
cannot approve their own pull request, so mandatory approving reviews should only be
enabled after another maintainer has been granted access.
