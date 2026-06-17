# Scenario Profiles And Reuse Blueprint

This is the M27 entry point for teams reusing Enterprise RAG Starter as a modular RAG foundation. It explains which repo blocks to keep, disable, or replace for common starter scenarios without reading every milestone note.

## Current Reuse Boundary

M27 documents reusable scenarios. It does not introduce new access-control code, admin feature flags, or scenario build packs. Those are planned in M28-M30.

Current strongest implemented mode is enterprise-style OIDC/dev identity plus document ACL trimming, governance, audit, feedback, tuning, and security hardening. M28 adds explicit access strategies so simpler scenarios can opt into `none`, `employee_all`, or `corpus_level` retrieval authorization without rewriting retrieval internals.

## Module Map

| Module block | Main repo areas | Keep when | Replace or disable when |
|---|---|---|---|
| Ingestion connectors | `backend/app/api/upload.py`, `backend/app/connectors/`, `backend/app/ingestion/` | Files, DB rows, uploaded `.eml`, or queue visibility are needed | Static prebuilt index or read-only research corpus is enough |
| Parsing and chunking | `backend/app/adapters/`, `backend/app/ingestion/chunking.py` | Any uploaded or connected source must become searchable | External pipeline already emits normalized chunks |
| Embeddings and index | `backend/app/embedding/`, `backend/app/db/repo_chunks.py`, `backend/app/db/repo_search.py` | Any vector, hybrid, or rerank retrieval is needed | A separate vector DB/search service owns indexing |
| Retrieval engine | `backend/app/core_rag/`, `backend/app/db/repo_search.py` | Grounded search/ask/compare is required | Rarely replace first; adapt providers and access before retrieval internals |
| Auth layer | `backend/app/auth/`, `backend/app/api/auth.py` | User identity, SSO, or admin access is needed | Trusted no-auth research deployments only |
| Access/ACL layer | `backend/app/db/repo_acl.py`, `backend/app/auth/dependencies.py` | Protected corpora or document permissions are needed | Public/trusted non-sensitive corpora only |
| Chat UI | `web/components/chat-workspace.tsx`, `web/app/console/page.tsx` | End users ask questions with citations | Headless API-only deployment |
| Admin console | `web/components/admin-*.tsx`, `backend/app/api/admin.py` | Operators manage sources, profiles, traces, access, governance, tuning | Minimal research tool with no operator UI |
| Eval and observability | `backend/app/eval/`, `backend/app/db/repo_traces.py`, `backend/app/db/repo_query_mining.py` | Retrieval quality must be measured or improved | Short-lived demo with no tuning loop |
| Governance and audit | `backend/app/actions/`, `backend/app/db/repo_admin_audit.py`, `backend/app/db/repo_governance.py` | Enterprise review, approvals, audit integrity, retention are needed | Simple internal RAG with low-risk data |

See the visual selection map in `docs/diagrams/m27_module_selection_map.mmd`.

## Scenario Profiles

### 1. Small Enterprise Login/Password With Corpus-Level Access

Best for an MSME that wants simple employee accounts, a few corpora, and access by corpus rather than per-document ACL.

Current implementation status: partially implemented. `ACCESS_STRATEGY=corpus_level` is available for SQL-level corpus authorization; `AUTH_MODE=password` remains reserved until the password login module is implemented.

Keep:
- Core ingestion, parsing/chunking, embeddings, retrieval, chat UI, corpus/source admin, eval basics, feedback logging.

Disable:
- OIDC-only setup paths unless enterprise SSO is available.
- Advanced governance approvals, tuning lab, and tool actions unless the customer needs them.

Replace:
- Auth layer with a password provider or external identity provider.
- Document ACL strategy with corpus-level SQL access strategy when M28 lands.

Required env:
- `AUTH_ENABLED=true`
- `AUTH_MODE=password` after password mode is implemented, or `AUTH_MODE=oidc`/`dev` with a simple identity provider until then
- `ACCESS_STRATEGY=corpus_level`
- `APP_ENV=staging` or `prod` for non-local pilots
- `FRONTEND_APP_URL=https://...`
- `API_ALLOWED_ORIGINS=https://...`

Security assumptions:
- Corpus membership is enough for the business risk.
- Upload rights should be limited to editor/admin users.
- Do not use `AUTH_MODE=dev` or weak secrets outside local/dev.

Minimum test pack:
- Upload/search/ask baseline.
- Citation provenance check.
- Corpus-level allow/deny checks.
- Admin source/corpus management smoke.
- M23-M26 security posture checks.

Expected admin UI:
- Source admin, corpus admin, limited access admin, eval/observability.
- Hide or disable tuning/governance modules after M29.

### 2. Employee-Wide RAG With Equal Access

Best for an internal assistant where all authenticated employees can access the same non-sensitive employee knowledge base.

Current implementation status: implemented as an explicit access strategy.

Keep:
- Auth layer, ingestion, parsing/chunking, embeddings, retrieval, chat UI, source/corpus admin, eval/observability, feedback.

Disable:
- Per-document ACL management, access-request workflow, direct grants, governance escalation, and sensitive tool actions unless later needed.

Replace:
- Document ACL access strategy with `employee_all` SQL access strategy when M28 lands.

Required env:
- `AUTH_ENABLED=true`
- `AUTH_MODE=oidc` for real deployments, or `AUTH_MODE=dev` only for local learning
- `ACCESS_STRATEGY=employee_all`
- `APP_ENV=staging` or `prod`
- Strong auth secrets and explicit CORS origins

Security assumptions:
- Every authenticated employee can see every enabled employee corpus.
- Admin APIs remain protected even if employee search is broad.
- Data must be reviewed before adding sensitive documents.

Minimum test pack:
- Authenticated search/ask works.
- Unauthenticated search/upload fails.
- Employee-wide corpus visibility works.
- Citation provenance and semantic-cache safety checks pass.

Expected admin UI:
- Source/corpus admin, eval/observability, audit log.
- Minimal access admin; no complex approval inbox by default.

### 3. No-Auth Research/Admin RAG For Trusted Environments

Best for a trusted research lab, admin data-management sandbox, or non-sensitive knowledge exploration tool on a controlled network.

Current implementation status: implemented as an explicit mode for search/ask with protected admin behavior and upload restrictions.

Keep:
- Parsing/chunking, embeddings/index, retrieval, chat UI, eval/observability, source/corpus admin if operators are trusted.

Disable:
- OIDC, password login, ACL workflows, governance approvals, sensitive tool actions, advanced admin tuning unless explicitly needed.

Replace:
- Nothing required for a basic trusted local research deployment.

Required env:
- `AUTH_ENABLED=false` or `AUTH_MODE=none`
- `ACCESS_STRATEGY=none`
- `APP_ENV=local` or controlled non-production environment only
- `AUTH_NONE_ALLOW_UPLOAD=true` only when trusted operators may upload

Security assumptions:
- No sensitive data.
- Trusted network or local machine only.
- Anyone who can reach search/ask can query the corpus.
- Upload remains disabled unless explicitly allowed.

Minimum test pack:
- No-auth search/ask allowed.
- Admin protected or intentionally unavailable.
- Upload disabled unless `AUTH_NONE_ALLOW_UPLOAD=true`.
- Citation provenance and baseline ask/search smoke.

Expected admin UI:
- Research/source management only.
- Remove admin tuning/governance modules after M29 if the subset should be simple.

### 4. Full Enterprise OIDC + ACL + Governance Mode

Best for production-like enterprise pilots with SSO, document ACLs, time-bound grants, audit, retention, feedback, governance, and operator controls.

Current implementation status: strongest current implemented scenario.

Keep:
- All core modules: ingestion, parsing/chunking, embeddings/index, retrieval, auth, document ACL, chat UI, admin console, eval/observability, governance/audit, retention, semantic cache safety, tuning controls.

Disable:
- Local-dev impersonation outside `APP_ENV=local|dev`.
- No-auth mode in staging/prod.

Replace:
- OIDC provider config, LLM provider/model, storage/deployment details, and enterprise connector credentials.

Required env:
- `AUTH_ENABLED=true`
- `AUTH_MODE=oidc`
- `ACCESS_STRATEGY=document_acl_with_time_bound_grants`
- `APP_ENV=staging` or `prod`
- `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`
- Strong `AUTH_STATE_SIGNING_SECRET`, `DEV_LOCAL_JWT_SECRET`, database password, provider API keys as required
- HTTPS `FRONTEND_APP_URL` and explicit `API_ALLOWED_ORIGINS`

Security assumptions:
- Document ACL trimming stays inside SQL retrieval queries.
- Admin mutations are audited.
- High-impact admin actions require second-actor approval outside local/dev.
- Retention and audit integrity are operational responsibilities.

Minimum test pack:
- M4 ACL leak regression.
- M16.1 time-bound grant checks.
- M22 feedback checks.
- M23-M26 security hardening checks.
- Baseline citation/search/ask smoke.

Expected admin UI:
- Full admin console: source/corpus/access/profile/eval/trace/actions/audit/tuning/governance.

## First 2 Hours Guide

1. Pick one scenario profile and write it at the top of your project notes.
2. Read only these docs first: `README.md`, this blueprint, `docs/04_repo_navigation_blueprint.md`, and `docs/runbooks/SAFE_EXTENSION_BLUEPRINT.md`.
3. Start Postgres with `docker compose up -d`.
4. Copy frontend env with `cp web/.env.example web/.env.local`.
5. Set backend auth variables for the selected scenario.
6. Run migrations from `backend/` with `.venv/bin/python -m app.db.migrate`.
7. Use `make dev-web` when you want backend and frontend together.
8. Upload or seed one tiny corpus.
9. Run the scenario minimum test pack before changing retrieval code.
10. Replace providers/adapters/auth first; change retrieval internals only after traces and evals are in place.

## Security Consequences By Scenario

| Scenario | Main security consequence |
|---|---|
| Small enterprise corpus access | Simpler access is easier to operate but less granular than document ACLs |
| Employee-wide RAG | Authentication protects entry, but all enabled employee corpus data is broadly visible |
| No-auth research | Fastest learning path, but network/data trust carries the whole security burden |
| Enterprise OIDC + ACL | Strongest current posture, but highest setup and operator complexity |

## Future Milestone Boundary

- M28: implemented swappable access strategies and corpus-level authorization.
- M29: implemented modular admin feature flags and scenario-specific navigation/API gating.
- M30: implemented scenario build packs, sample env files, runbooks, and validation suites.
