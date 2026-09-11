# Agent guide

Read `README.md`, `STATUS.md`, and `CLAUDE.md` before changing this repository.
`CLAUDE.md` is the detailed contributor guide; `STATUS.md` is the current-state record.
Also read [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md). The canonical shared rules
are in the
[B004 engineering standard](https://github.com/beyondalgorithms2026-source/RAG_ENTERPRISE_LANGGRAPH_APP/blob/main/docs/ENGINEERING_STANDARDS.md),
but this guide contains the essential safety rules needed when APP is unavailable. The
stricter instruction applies wherever documents overlap.

## Scope

- Active backend: `backend/`
- Active frontend: `web/`
- Legacy fallback UI: `frontend/` — do not add new work there
- Retrieval, ACL enforcement, citations, embeddings, and governance belong in this repo
- The sibling LangGraph app must continue to have no direct backend or database access
- The MCP server remains a zero-runtime-dependency integration boundary and must not
  implement or bypass backend policy
- The private-assets repository is permanently out of scope

## Required invariants

- Enforce document access inside retrieval SQL, never only after retrieval.
- Preserve citation provenance and safe not-found behavior.
- Make retrieval changes measurable, traced, reversible, and eval-backed.
- Derive embedding dimensions from the live database and use the swap lifecycle.
- Preserve the guarded single-process runtime.
- Read `web/DESIGN.md` before UI work; add no external UI dependency.
- Ask before adding any dependency or weakening security/governance behavior.
- Never commit secrets, `.env` files, private/generated corpus data, or local report
  output. Deliberately tracked synthetic source fixtures are not private corpus data.
- Treat user input, retrieved documents, connector/tool content, and model output as
  untrusted; review AI-facing paths for direct and indirect prompt injection.
- Do not weaken authentication, ACL, approval, audit, evidence, citation, refusal, or
  redaction controls to make a test pass.
- Identify meaningful failure and boundary coverage before or alongside implementation.
  Fakes may prove deterministic mechanisms but not live retrieval or SQL authorization.
- P12 is the fast mocked harness smoke test; P12B is the authoritative real APP → MCP →
  STARTER → PostgreSQL/pgvector 25-question regression gate. Quality-sensitive changes
  must run the applicable evaluation, and baselines must never be overwritten
  automatically after regression.
- Preserve public API/response shapes, status vocabularies, configuration metadata, and
  cross-repository contracts unless an approved change explicitly updates consumers.

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

For every changed API or AI-facing route, explicitly review input bounds,
authentication/authorization, prompt-injection exposure, untrusted-content handling,
redaction, citation/grounding enforcement, timeout/retry behaviour, compatibility, and
the required unit, integration, red-team, or golden-eval coverage. Documentation is
guidance rather than proof; call a rule enforced only when a named mechanical check
verifies it.
