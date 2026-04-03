# STATUS.md — Milestone Progress Tracker

**Current Milestone:** M11 — Admin Workspace Polish And Operational UX

**Completed**
- M0: Baseline Stable Import (baseline-import-stable)
- M1: Profiles And Retrieval Controls (2026-04-01)
- M2: Retrieval Observability And Traceability (2026-04-01)
- M3: Identity + SSO Auth (2026-04-01)
- M4: Authorization + ACL Security Trimming (2026-04-01)
- M5: Admin API Control Plane (2026-04-01)
- M6: Hybrid Fusion Upgrade (2026-04-02)
- M7: Router And Lexical Intent Expansion (2026-04-02)
- M8: Reranking Policy Layer (2026-04-02)
- M9: Per-Corpus Indexing And Adaptive Chunking Policies (2026-04-02)
- M10: Next.js Enterprise Console UI (2026-04-02)
- M10.1: Stitch Fidelity Remediation (2026-04-02)

**M10 summary**
- Replaced the primary product path with a new Next.js app in `web/` featuring a marketing homepage plus SSO-first login and register entry pages
- Added a role-aware `/console/*` shell so standard users land in a unified workspace and admins/approvers land in an operations workspace
- Delivered user workspace pages for grounded chat, enterprise search, source browsing, uploads, and connector requests on top of the existing backend APIs
- Pulled the admin UI forward into M10 with corpora, jobs, profiles, evals, traces, and policy views backed by the existing `/admin/*` endpoints
- Updated backend CORS and root redirect behavior so the new frontend is the main entrypoint while preserving the legacy `/frontend` fallback
- See docs/m10_nextjs_enterprise_console_ui.md

**M10.1 summary**
- Rebuilt the exposed frontend routes as Stitch-faithful ports so the public marketing flow, login flow, chat workspace, sources workspace, and admin dashboard now follow the reference package structure rather than a custom approximation
- Kept the guarded local-dev auth path with test user and test admin accounts, but moved the local login UI into a secondary disclosure below the unchanged Stitch-style SSO card
- Added the extra Stitch CTA routes (`/get-a-demo` and `/watch-video-tour`) and redirected non-reference routes back to the Stitch-backed surfaces
- Preserved the default frontend runtime and backend redirect target on port `3001` while keeping the backend local-dev auth checks green
- See docs/m10_1_polished_ui_with_test_users.md

**M9 summary**
- Added explicit corpus policies for legal, transcripts, db rows, email/casework, and the default baseline
- Source-scoped retrieval now honors corpus default modes so different corpora behave differently without changing global settings
- Chunking now adapts target size and overlap by corpus policy, and transcript-oriented policies emit speaker/time metadata
- Added structured metadata filters for row-shaped corpora plus a corpus-policy eval matrix fixture and smoke coverage
- See docs/m9_per_corpus_indexing_and_adaptive_chunking_policies.md

**M8 summary**
- Expanded the reranker profile into a policy layer with selective controls by mode, corpus, candidate depth, and latency budget
- Added rerank policy traces so operators can see when reranking was applied, skipped, and which candidate corpora were considered
- Reserved an explicit MMR placeholder hook in the rerank trace without changing current ranking behavior
- Extended compare-eval with rerank A/B variants and a latency delta report for rerank-off vs rerank-on comparisons
- See docs/m8_reranking_policy_layer.md

**M7 summary**
- Expanded lexical-first routing for quote-like exact wording queries, identifier/code lookups, and date-heavy lexical queries
- Kept semantic-first queries on the hybrid baseline while preserving graph/temporal readiness fallback behavior
- Added structured route metadata to retrieval traces and retrieval-eval outputs: route class, preferred mode, and per-signal route details
- Added a router benchmark fixture pack covering quote, code, semantic, and temporal query sets
- See docs/m7_router_and_lexical_intent_expansion.md

**M6 summary**
- Preserved linear fusion as the default hybrid baseline while adding configurable `rrf` support through retrieval profile settings
- Added explicit retrieval fusion settings for `fusion_method` and `rrf_k`
- Extended retrieval traces and score diagnostics with fusion method, rank inputs, and per-method component scores
- Updated benchmark fixtures and compare reporting so fusion-method comparisons are visible in reports
- See docs/m6_hybrid_fusion_upgrade.md

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
- Start M11: admin workspace polish and operational UX refinement
- Improve operator workflows on top of the new console without changing existing backend control-plane contracts
- Preserve the new role-aware console split while refining non-developer operations

**Notes / DoD checklist (M10)**
- [x] Anonymous users can view the homepage but cannot access `/console/*`
- [x] Login flow routes users into the correct workspace by role
- [x] Users can search, chat, upload, inspect citations, and browse sources from the new console
- [x] Admins can operate current control-plane capabilities from the new console UI
- [x] docs/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M10.1)**
- [x] Stitch-backed public and console routes now drive the visible UI
- [x] Local test-user and test-admin auth still works without changing the backend auth contract
- [x] Non-reference routes redirect back to the Stitch-backed surfaces
- [x] docs/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M9)**
- [x] Different corpora behave differently by policy
- [x] Policies are explicit and test-covered
- [x] docs/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M8)**
- [x] Reranking can be enabled selectively rather than globally
- [x] Operators can compare rerank-off vs rerank-on quality and latency
- [x] Future MMR hook is planned without blocking milestone completion
- [x] docs/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M7)**
- [x] Router routes quote-like and ID-like queries more reliably
- [x] Route decisions are inspectable in debug traces
- [x] docs/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M6)**
- [x] Linear remains the default and regression-safe baseline
- [x] RRF can be enabled by retrieval config/profile
- [x] Fusion comparisons are visible in reports
- [x] docs/ note added
- [x] STATUS.md updated

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
