# Agent guide

Read `README.md`, `STATUS.md`, and `CLAUDE.md` before changing this repository.
`CLAUDE.md` is the detailed contributor guide; `STATUS.md` is the current-state record.

## Scope

- Active backend: `backend/`
- Active frontend: `web/`
- Legacy fallback UI: `frontend/` — do not add new work there
- Retrieval, ACL enforcement, citations, embeddings, and governance belong in this repo
- The sibling LangGraph app must continue to have no direct backend or database access

## Required invariants

- Enforce document access inside retrieval SQL, never only after retrieval.
- Preserve citation provenance and safe not-found behavior.
- Make retrieval changes measurable, traced, reversible, and eval-backed.
- Derive embedding dimensions from the live database and use the swap lifecycle.
- Preserve the guarded single-process runtime.
- Read `web/DESIGN.md` before UI work; add no external UI dependency.
- Ask before adding any dependency or weakening security/governance behavior.
- Never commit secrets, `.env` files, corpus data, or local report output.

## Verification

```bash
make test
make reader-clarity-check       # docs changes
make scenario-validate          # auth, ACL, or module changes
make repo-hygiene-check         # always
cd web && npx tsc --noEmit && pnpm run build   # UI changes
```

Report real results, including failures and skips. For detailed paths, escalation rules,
and specialized change procedures, follow `CLAUDE.md` and the relevant runbook under
`docs/runbooks/`.
