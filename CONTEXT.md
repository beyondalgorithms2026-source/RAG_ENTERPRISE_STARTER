# Project context

This repository is the data layer of a three-part governed retrieval proof of concept.
It provides FastAPI, PostgreSQL/pgvector retrieval, SQL-level access control, citations,
audit, retrieval-profile governance, evaluation packs, and a Next.js operator console.

The other layers are published separately:

- `RAG_ENTERPRISE_LANGGRAPH_APP` decides whether an answer may be released.
- `RAG_ENTERPRISE_MCP_SERVER` provides the read-only integration boundary.
- This repository owns data access, retrieval behavior, and authorization.

The split is deliberate: the agent has no database credentials and cannot widen its own
access or change the backend's retrieval profile.

## Current state

- AR0–AR20 audit-remediation milestones are complete.
- UX0–UX12 interface-remediation milestones are complete.
- M20–M30 still have historical manual-verification notes to close; this is documentation
  debt, not an assertion that their implemented code is absent.
- The active code is `backend/` and `web/`; `frontend/` is retained legacy fallback code.
- Retrieval augmentation is implemented but off by default and enabled by a backend
  operator per corpus.

This remains a self-built proof of concept. It has not been deployed to a client
environment and has no users or real workload evidence.

## Sources of truth

Use `README.md` for the public entry point and `STATUS.md` for the concise operational
snapshot. Current runbooks live under `docs/runbooks/`; completed change evidence lives
under `docs/milestones/`. Dated audits and imported `_master_docs` are historical context,
not current status.
