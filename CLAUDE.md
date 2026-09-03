# Contributor operating guide

This repository is the data layer of the three-repository Governed RAG proof of concept.
It contains a FastAPI backend, PostgreSQL/pgvector retrieval, SQL-level access control,
and a Next.js operator console. Start with `README.md`; use `STATUS.md` for current state.

## Repository boundaries

- Active backend: `backend/`
- Active frontend: `web/`
- Legacy fallback UI: `frontend/` — do not build new work there
- Generated local reports: `data/reports/` — gitignored unless deliberately promoted
- The LangGraph agent and MCP integration layer live in separate repositories

The agent layer has no database access. Retrieval, access control, citations, audit, and
retrieval profiles remain in this backend. Do not move those controls into the agent.

## Non-negotiable behavior

- Access trimming is composed into retrieval SQL via
  `backend/app/auth/access_strategy.py` and `backend/app/db/repo_search.py`; never rely on
  UI or Python post-filtering for authorization.
- Preserve citation provenance and safe not-found behavior. An unsupported answer must
  not be presented as grounded.
- Retrieval changes must be measured, traced, reversible through a flag/profile, and
  evaluated before promotion.
- Never hardcode an embedding dimension. Read the live `vector(N)` column and use the
  managed swap lifecycle in `backend/app/embedding/lifecycle.py` for dimension changes.
- The runtime is single-process by design. Do not introduce multi-worker assumptions or
  bypass the existing guard.
- Do not add a dependency, weaken security/governance behavior, or alter auth flows
  without explicit approval.
- Never commit `.env` files, credentials, corpus data, or generated local reports.

## Working paths

| Area | Path |
|---|---|
| Backend API | `backend/app/` |
| Retrieval | `backend/app/core_rag/` |
| SQL retrieval and ACL | `backend/app/db/repo_search.py`, `backend/app/auth/access_strategy.py` |
| Embeddings | `backend/app/embedding/` |
| Tests | `backend/tests/` |
| Operator console | `web/` |
| UI design rules | `web/DESIGN.md` |
| Scenario packs | `scenarios/` |
| Runbooks | `docs/runbooks/` |
| Milestone evidence | `docs/milestones/` |

For UI changes, read `web/DESIGN.md` before editing and reuse the existing component,
token, button, form, and table systems. The interface must work without external fonts,
icons, images, or other runtime UI dependencies.

## Verification

Use the checks appropriate to the files changed:

```bash
make test
make reader-clarity-check       # documentation and onboarding
make scenario-validate          # auth, ACL, or module changes
make repo-hygiene-check         # always before a commit
cd web && npx tsc --noEmit && pnpm run build   # frontend changes
```

Database-backed tests require a live migrated Postgres. `RAG_REQUIRE_DB=1` converts
database skips into failures when a database is expected.

Report the checks actually run, including failures and skips. Do not describe an
unmeasured result as verified.

## Further documentation

- Local setup: `docs/01_quickstart.md`
- Repository navigation: `docs/04_repo_navigation_blueprint.md`
- Safe extension path: `docs/runbooks/SAFE_EXTENSION_BLUEPRINT.md`
- Embedding swaps: `docs/runbooks/EMBEDDING_MODEL_SWAP.md`
- Source-control workflow: `docs/runbooks/SOURCE_CONTROL_WORKFLOW.md`

Older imported documents under `docs/_master_docs/` and `docs/README_from_master.md` are
reference material, not current truth. When documents disagree, prefer `STATUS.md`, then
`README.md`, then the navigation blueprint and current runbooks.
