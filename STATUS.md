# STATUS.md — Milestone Progress Tracker

**Current Milestone:** M6 — Hybrid Fusion Upgrade

**Completed**
- M0: Baseline Stable Import (baseline-import-stable)
- M1: Profiles And Retrieval Controls (2026-04-01)
- M2: Retrieval Observability And Traceability (2026-04-01)
- M3: Identity + SSO Auth (2026-04-01)
- M4: Authorization + ACL Security Trimming (2026-04-01)
- M5: Admin API Control Plane (2026-04-01)

**M5 summary**
- Added admin-role enforcement for `/admin/*` so the control plane is no longer reachable by authenticated non-admin users
- Added corpus registry APIs to create, update, list, and assign sources to corpora without editing code
- Added admin surfaces for retrieval profile metadata/defaults, query-time retrieval debug traces, eval triggers, report listing, and ingestion/enrichment job inspection
- Added admin reindex and enrichment trigger endpoints on top of the existing synchronous ingestion/enrichment flows
- See docs/m5_admin_api_control_plane.md

**M1 summary**
- DB-backed profile registries: embedding, reranker, LLM, retrieval, eval_pack
- Admin endpoints: GET /admin/profiles, POST /admin/profiles/active
- Resolver overlay pattern with TTL cache + Settings fallback
- All consumers (embedder, reranker, LLM client, retrieval) wired to profiles
- Eval reports include active profile metadata snapshot
- See docs/m1_profiles_and_retrieval_controls.md

**M2 summary**
- Request-level retrieval traces stored in `retrieval_traces` with requested/resolved mode, retrieval path, candidate counts, fallback reason, answer path, and active profile snapshot
- Stage-level latency traces captured for `search`, `rerank`, `ask`, and `total`, with `search_total` preserved on ask flows
- Score-path diagnostics persisted for top candidates: vector, keyword, combined, rerank, and anchor score
- Admin inspection endpoints added for trace listing and single-trace lookup
- Eval outputs include `report_metadata` with active profiles, retrieval settings, and per-case trace summaries
- See docs/m2_retrieval_observability_and_traceability.md

**Next actions**
- Start M6: hybrid fusion upgrade
- Add configurable fusion method support while keeping current linear fusion as the baseline-safe default
- Extend score traces and eval comparisons for fusion debugging

**Notes / DoD checklist (M5)**
- [x] Admin can reindex without code changes
- [x] Admin can run evals and inspect report listings over API
- [x] Retrieval defaults and active profile metadata are inspectable over API
- [x] Basic ingestion/enrichment job status surface is available
- [x] docs/ note added
- [x] STATUS.md updated

**M4 summary**
- Added authz data model tables for users, groups, memberships, and document ACL mappings
- Added `sources.sensitivity_label` to support `public` / `internal` / `confidential` style gating
- Retrieval SQL now trims results at query time based on the authenticated principal’s synced group memberships
- Chunk fetch paths used for graph/deep-research supplementation also enforce the same ACL predicate
- Forbidden documents are excluded before answer assembly so citations cannot leak restricted doc ids
- Search audit logs record user identity, groups, corpus labels, document ids, and sensitivity labels
- See docs/m4_authorization_and_acl_security_trimming.md

**Notes / DoD checklist (M4)**
- [x] Two test users with different groups get different retrieval results
- [x] Forbidden content cannot appear in retrieved chunks nor citations
- [x] Audit log records user, groups, corpus, doc ids accessed
- [x] docs/ note added
- [x] STATUS.md updated

**M3 summary**
- Generic OIDC settings and discovery-based auth support added for Azure AD / Okta / Google Workspace style providers
- Backend auth middleware validates JWTs from bearer headers or auth cookies and attaches authenticated user context to each request
- `/auth/login`, `/auth/callback`, `/auth/logout`, `/auth/me`, and `/auth/providers` endpoints added for backend-managed login flow support
- `/ask` and `/ask/stream` require auth when `AUTH_ENABLED=true`
- Structured logs now include authenticated user identity and simple mapped roles: `user`, `admin`, `approver`
- See docs/m3_identity_and_sso_auth.md

**Notes / DoD checklist (M3)**
- [x] `/ask` requires auth
- [x] user identity appears in logs/audit events
- [x] docs/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M2)**
- [x] Operators can explain why a query used a specific retrieval path
- [x] Latency is stored and inspectable per request
- [x] Eval output captures enough trace data to compare strategies meaningfully
- [x] docs/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M1)**
- [x] Switch embedding model by config and re-index successfully
- [x] Switch reranker on/off by config and see report deltas
- [x] Switch LLM model by config without breaking answer contract
- [x] Retrieval defaults are stored and visible by profile
- [x] Eval reports store active profile metadata
- [x] docs/ note added
- [x] STATUS.md updated
