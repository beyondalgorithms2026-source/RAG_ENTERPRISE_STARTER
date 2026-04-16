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
- M10.1.1: Local Dev Auth And First-Run Entry Path Coherence (2026-04-08)
- M10.1.2: User Workspace Contract Completion (2026-04-09)
- M10.1.2.1: User Workspace Interaction Polish And Upload Readiness Clarity (2026-04-12)
- M10.1.3: Admin Workspace Route Wiring And Operator Completeness (2026-04-14)
- M10.1.3.1: Admin Trustworthiness, Operational Depth, And Audit Foundations (2026-04-14)
- M10.1.4: Placeholder And CTA Hygiene Across Public And Console Surfaces (2026-04-14)
- M10.1.5: First-Run Empty States And Operator Onboarding (2026-04-14)

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

**M10.1.1 summary**
- Added graceful auth capability probing on `/auth/providers` so local-dev-first environments no longer fail the login page when OIDC is not configured
- Updated `/auth/login` to redirect back to the frontend login route with `dev_login=1` in local-dev-only environments instead of returning an OIDC configuration dead-end
- Updated the login screen to promote the supported local dev sign-in path when SSO is unavailable while preserving the SSO-first primary action in real OIDC-backed environments
- Made the first-run guidance for test-user and test-admin accounts explicit near the primary login action
- See docs/m10_1_1_local_dev_auth_and_first_run_entry_path_coherence.md

**M10.1.2 summary**
- Replaced redirect-only user routes with truthful workspace pages for search, uploads, and connectors while preserving the existing console structure
- Persisted new chat threads before route transition and rendered live `/ask/stream` progress states so submitted questions no longer disappear into a blank pane
- Added explicit no-evidence and request-failed terminal states in chat plus source-context drill-in and open-file actions in the evidence rail
- Switched single-file upload HTTP handling to queue background ingestion and surfaced job-stage progress in the uploads workspace
- Added a local-dev retrieval bypass for built-in test identities when no explicit ACL exists so uploaded dev sources can be exercised end to end without manual ACL setup
- Follow-up remediation keeps user entry on a fresh chat state, groups retrieved sources by answer turn, keeps the workspace rails visible during long thread review, and propagates auth context into streamed ask workers
- See docs/m10_1_2_user_workspace_contract_completion.md

**M10.1.2.1 summary**
- Turned answer actions into working user-console controls with modern styling, transient feedback acknowledgements, and client-only helpful/not-helpful toggles
- Made the retrieved-sources rail easier to scan by default-collapsing older answer groups, switching to clearer `+/-` affordances, and keeping citation clicks scoped to the correct answer section
- Closed the retrieved-sources persistence gap at refresh hydration time so the rail now keeps the same selected answer group and citation context instead of silently reverting to the latest answer
- Replaced the generic selected-context heading with cleaner source-aware file details, proper spacing for locator metadata, and a separate open-file link line so grounded context reads more like a real source viewer
- Clarified upload and source readiness states so chunked files are clearly marked as not searchable yet, embedded/indexed files are marked ready, and polling/logging behavior is explained in plain language
- See docs/m10_1_2_1_user_workspace_interaction_polish_and_upload_readiness_clarity.md

**M10.1.3 summary**
- Preserved `/console/admin` as a true system overview page and added an explicit `Overview` destination in the admin sidebar
- Replaced redirect-only admin routes with real routed pages for corpora, jobs, profiles, evals, traces, policies, and audit log
- Wired supported backend control-plane actions into the routed pages for corpus creation, job inspection, profile activation, eval triggering, and trace review
- Kept policies and audit log truthful as read-only or live-summary surfaces where deeper workflows still belong to later milestones
- Fixed admin workspace trust gaps such as the `New Corpus` CTA target and nav active-state behavior so the console feels like an operator workspace instead of a summary shell
- See docs/m10_1_3_admin_workspace_route_wiring_and_operator_completeness.md

**M10.1.3.1 summary**
- Replaced the admin overview’s fabricated fallback counts, fake notifications, placeholder trace rows, and misleading source-count formatting with a live `/admin/overview` contract
- Added real admin `Sources` and `Access` routes so operators can inspect source placement, ACL posture, and access-state visibility without inferring state from unrelated pages
- Introduced append-only `admin_audit_events` persistence plus backend audit APIs, and wired profile activation, corpus changes, source edits, reindex/enrichment actions, and eval runs into stored admin audit records
- Upgraded corpora, jobs, profiles, evals, traces, and audit-log pages from shallow summary surfaces into more operational routed views with detail, drill-in, and cross-links
- See docs/m10_1_3_1_admin_trustworthiness_operational_depth_and_audit_foundations.md

**M10.1.4 summary**
- Replaced dead-end hash links across the public, login, user-console, and admin-console surfaces with real lightweight `/privacy`, `/terms`, `/security`, and `/status` pages
- Aligned misleading public CTA copy with the actual private-beta product motion by converting register/free-trial/demo prompts into truthful request-access or console-login paths
- Disabled decorative notification/settings and embedded-video controls with explicit explanations instead of leaving them clickable with no effect
- Simplified the shared public navigation so every visible header/footer destination points somewhere real rather than to missing sections
- See docs/m10_1_4_placeholder_and_cta_hygiene_across_public_and_console_surfaces.md

**M10.1.5 summary**
- Reworked the clean-DB user workspace experience so Chat, Search, History, and Sources now explain what happens first, what “indexed” means, and what to do next instead of feeling blank or broken
- Replaced misleading source-sidebar storage chrome with truthful first-run guidance and clarified upload/search/retrieval copy so users can tell the difference between waiting on upload, indexing, retrieval, answer generation, and permission-limited visibility
- Added first-run operator guidance in the admin overview plus explicit loading-vs-empty-vs-no-activity states across corpora, jobs, evals, and traces so a clean install reads as intentional
- Tightened admin empty-state copy around first corpus, first source placement, first job, first trace, and first eval so operators always have a concrete next step
- See docs/m10_1_5_first_run_empty_states_and_operator_onboarding.md

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
- Start M11: admin workspace polish and operational UX
- Improve operator ergonomics across jobs, sources, traces, and audit with stronger filtering, bulk workflows, and comparison UX
- Preserve the truthful admin control-plane foundations added in M10.1.3.1 and the first-run clarity added in M10.1.5

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

**Notes / DoD checklist (M10.1.1)**
- [x] A first-time local user does not hit a dead-end primary login CTA
- [x] Test user and admin entry flows are explicit enough for a clean-machine first run
- [x] SSO-first branding remains intact in real deployed environments without breaking local usability
- [x] docs/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M10.1.2)**
- [x] Built-in dev test accounts can exercise the end-to-end user workflow without being accidentally blocked by implicit ACL gaps
- [x] User-facing actions no longer feel decorative or mismatched
- [x] Citation/evidence interactions increase trust instead of acting like static display chrome
- [x] Workspace behavior around history and persistence is predictable to non-technical users
- [x] The console no longer suggests capabilities that disappear into unrelated routes
- [x] Distinct user pages remain distinct with truthful contracts
- [x] Ask and upload flows show visible progress and a visible terminal state
- [x] No-context questions render an explicit assistant response
- [x] docs/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M10.1.2.1)**
- [x] Copy action shows visible success feedback and still copies the answer
- [x] Helpful / not-helpful answer controls are interactive without introducing backend logging early
- [x] Retrieved-source groups default to a more scannable collapsed state
- [x] Retrieved-source rail selection and collapse state survive refresh within the same thread
- [x] Selected context shows source-aware locator details with readable title/link formatting when available
- [x] Upload and source readiness states explain when a document is actually searchable
- [x] docs/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M10.1.3)**
- [x] Every advertised admin destination is a real page, not a redirect back to the dashboard
- [x] The overview page remains intact and useful for a real admin on first login
- [x] Admins can use current live controls where supported and still gain value from read-only/live-summary pages where deeper controls arrive later
- [x] The admin console feels like an operator workspace rather than a pretty summary shell
- [x] docs/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M10.1.3.1)**
- [x] Admin overview never invents system state when APIs return empty or unavailable data
- [x] Every admin sidebar destination is both real and operationally meaningful
- [x] Sources, corpora, jobs, profiles, evals, traces, policies, access, and audit each have a distinct operator purpose
- [x] Audit log is backed by stored admin events, not inferred summaries
- [x] Admin can understand what happened, who changed it, and what object was affected without using the terminal or database directly
- [x] docs/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M10.1.4)**
- [x] No primary CTA appears clickable while doing nothing
- [x] Demo and trial flows set the right expectation for enterprise/private-beta reality
- [x] Placeholder actions are intentional and legible rather than feeling broken
- [x] Useful overview and summary surfaces remain visible while misleading dead-end affordances are removed or disabled
- [x] docs/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M10.1.5)**
- [x] A clean install feels intentionally empty rather than misconfigured
- [x] User and admin both have an obvious next step to make the product useful
- [x] Empty-state copy reduces the feeling that functionality is missing when the issue is simply lack of data
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
