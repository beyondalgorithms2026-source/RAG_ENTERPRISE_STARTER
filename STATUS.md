# STATUS.md — Milestone Progress Tracker

**Current Milestone:** M30 — Implemented; DB-backed re-run checks pending

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
- M11: Admin Workspace Polish And Operational UX (2026-04-16)
- M11.1: Ingestion Queue Visibility, ETA, And Priority Governance (2026-04-16)
- M12: Cloud DB And Structured Source Connectors (2026-04-20)
- M13: Enterprise Email And Attachment Ingestion (2026-04-21)
- M14: Tool Actions With Policy Gate (2026-04-21)
- M15: Human Approval Workflow For Sensitive Outputs/Actions (2026-04-21)
- M16: Fallback, Clarification, And Feedback Loop (2026-04-21)
- M16.1: Access-Limited Retrieval, Routed Business Approval, And Time-Bound Access Grants (2026-05-19)
- M17.a: Enterprise Test Environment Seed Pack, ACL Input Mapping, And Executive Access Baseline (2026-05-20)
- M17.b.1: Stitch-Faithful Tuning Lab Shell, Live Card, And Governed Registries (2026-05-21)
- M17.b.2: Interactive Sandbox Controls And Side-By-Side Compare (2026-05-21)

**Implemented / Pending DB-backed Re-run Checks**
- M17.b.3: Draft Promotion, Rollback, Embedding Safety, And Warm-Up (2026-05-28)
- M18: Query Transformation Layer (2026-05-28)
- M19: Semantic Cache (2026-05-28)
- M20: Retrieval Eval Ops And Real User Query Mining (2026-05-28)
- M21: Access Request Misuse Controls, User Blocking, And Governance Escalation (2026-05-28)
- M22: Structured Negative Feedback Capture And Answer Failure Logging (2026-06-02)
- M23: Security Posture Hardening And Explicit Auth Modes (2026-06-02)
- M24: Endpoint Authorization, Upload Safety, And Abuse Controls (2026-06-02)
- M25: Cache, Prompt-Injection, Session, And Browser Security Hardening (2026-06-03)
- M26: Secrets, Audit Integrity, Data Retention, And Parser Hardening (2026-06-03)
- M27: Scenario Profiles And Reuse Blueprint Documentation (2026-06-03)
- M28: Access Strategy Abstraction And Corpus-Level Authorization (2026-06-03)
- M29: Modular Admin Console And Feature Flag Packaging (2026-06-03)
- M30: Scenario Build Packs, Validation Suites, And Reuse Runbooks (2026-06-03)

**M10 summary**
- Replaced the primary product path with a new Next.js app in `web/` featuring a marketing homepage plus SSO-first login and register entry pages
- Added a role-aware `/console/*` shell so standard users land in a unified workspace and admins/approvers land in an operations workspace
- Delivered user workspace pages for grounded chat, enterprise search, source browsing, uploads, and connector requests on top of the existing backend APIs
- Pulled the admin UI forward into M10 with corpora, jobs, profiles, evals, traces, and policy views backed by the existing `/admin/*` endpoints
- Updated backend CORS and root redirect behavior so the new frontend is the main entrypoint while preserving the legacy `/frontend` fallback
- See docs/milestones/m10_nextjs_enterprise_console_ui.md

**M10.1 summary**
- Rebuilt the exposed frontend routes as Stitch-faithful ports so the public marketing flow, login flow, chat workspace, sources workspace, and admin dashboard now follow the reference package structure rather than a custom approximation
- Kept the guarded local-dev auth path with test user and test admin accounts, but moved the local login UI into a secondary disclosure below the unchanged Stitch-style SSO card
- Added the extra Stitch CTA routes (`/get-a-demo` and `/watch-video-tour`) and redirected non-reference routes back to the Stitch-backed surfaces
- Preserved the default frontend runtime and backend redirect target on port `3001` while keeping the backend local-dev auth checks green
- See docs/milestones/m10_1_polished_ui_with_test_users.md

**M10.1.1 summary**
- Added graceful auth capability probing on `/auth/providers` so local-dev-first environments no longer fail the login page when OIDC is not configured
- Updated `/auth/login` to redirect back to the frontend login route with `dev_login=1` in local-dev-only environments instead of returning an OIDC configuration dead-end
- Updated the login screen to promote the supported local dev sign-in path when SSO is unavailable while preserving the SSO-first primary action in real OIDC-backed environments
- Made the first-run guidance for test-user and test-admin accounts explicit near the primary login action
- See docs/milestones/m10_1_1_local_dev_auth_and_first_run_entry_path_coherence.md

**M10.1.2 summary**
- Replaced redirect-only user routes with truthful workspace pages for search, uploads, and connectors while preserving the existing console structure
- Persisted new chat threads before route transition and rendered live `/ask/stream` progress states so submitted questions no longer disappear into a blank pane
- Added explicit no-evidence and request-failed terminal states in chat plus source-context drill-in and open-file actions in the evidence rail
- Switched single-file upload HTTP handling to queue background ingestion and surfaced job-stage progress in the uploads workspace
- Added a local-dev retrieval bypass for built-in test identities when no explicit ACL exists so uploaded dev sources can be exercised end to end without manual ACL setup
- Follow-up remediation keeps user entry on a fresh chat state, groups retrieved sources by answer turn, keeps the workspace rails visible during long thread review, and propagates auth context into streamed ask workers
- See docs/milestones/m10_1_2_user_workspace_contract_completion.md

**M10.1.2.1 summary**
- Turned answer actions into working user-console controls with modern styling, transient feedback acknowledgements, and client-only helpful/not-helpful toggles
- Made the retrieved-sources rail easier to scan by default-collapsing older answer groups, switching to clearer `+/-` affordances, and keeping citation clicks scoped to the correct answer section
- Closed the retrieved-sources persistence gap at refresh hydration time so the rail now keeps the same selected answer group and citation context instead of silently reverting to the latest answer
- Replaced the generic selected-context heading with cleaner source-aware file details, proper spacing for locator metadata, and a separate open-file link line so grounded context reads more like a real source viewer
- Clarified upload and source readiness states so chunked files are clearly marked as not searchable yet, embedded/indexed files are marked ready, and polling/logging behavior is explained in plain language
- See docs/milestones/m10_1_2_1_user_workspace_interaction_polish_and_upload_readiness_clarity.md

**M10.1.3 summary**
- Preserved `/console/admin` as a true system overview page and added an explicit `Overview` destination in the admin sidebar
- Replaced redirect-only admin routes with real routed pages for corpora, jobs, profiles, evals, traces, policies, and audit log
- Wired supported backend control-plane actions into the routed pages for corpus creation, job inspection, profile activation, eval triggering, and trace review
- Kept policies and audit log truthful as read-only or live-summary surfaces where deeper workflows still belong to later milestones
- Fixed admin workspace trust gaps such as the `New Corpus` CTA target and nav active-state behavior so the console feels like an operator workspace instead of a summary shell
- See docs/milestones/m10_1_3_admin_workspace_route_wiring_and_operator_completeness.md

**M10.1.3.1 summary**
- Replaced the admin overview’s fabricated fallback counts, fake notifications, placeholder trace rows, and misleading source-count formatting with a live `/admin/overview` contract
- Added real admin `Sources` and `Access` routes so operators can inspect source placement, ACL posture, and access-state visibility without inferring state from unrelated pages
- Introduced append-only `admin_audit_events` persistence plus backend audit APIs, and wired profile activation, corpus changes, source edits, reindex/enrichment actions, and eval runs into stored admin audit records
- Upgraded corpora, jobs, profiles, evals, traces, and audit-log pages from shallow summary surfaces into more operational routed views with detail, drill-in, and cross-links
- See docs/milestones/m10_1_3_1_admin_trustworthiness_operational_depth_and_audit_foundations.md

**M10.1.4 summary**
- Replaced dead-end hash links across the public, login, user-console, and admin-console surfaces with real lightweight `/privacy`, `/terms`, `/security`, and `/status` pages
- Aligned misleading public CTA copy with the actual private-beta product motion by converting register/free-trial/demo prompts into truthful request-access or console-login paths
- Disabled decorative notification/settings and embedded-video controls with explicit explanations instead of leaving them clickable with no effect
- Simplified the shared public navigation so every visible header/footer destination points somewhere real rather than to missing sections
- See docs/milestones/m10_1_4_placeholder_and_cta_hygiene_across_public_and_console_surfaces.md

**M10.1.5 summary**
- Reworked the clean-DB user workspace experience so Chat, Search, History, and Sources now explain what happens first, what “indexed” means, and what to do next instead of feeling blank or broken
- Replaced misleading source-sidebar storage chrome with truthful first-run guidance and clarified upload/search/retrieval copy so users can tell the difference between waiting on upload, indexing, retrieval, answer generation, and permission-limited visibility
- Added first-run operator guidance in the admin overview plus explicit loading-vs-empty-vs-no-activity states across corpora, jobs, evals, and traces so a clean install reads as intentional
- Tightened admin empty-state copy around first corpus, first source placement, first job, first trace, and first eval so operators always have a concrete next step
- See docs/milestones/m10_1_5_first_run_empty_states_and_operator_onboarding.md

**M11 summary**
- Added saved-view and filtering workflows across the admin sources, jobs, traces, and audit surfaces so non-developer operators can reopen the same operational slices without manually rebuilding query state each visit
- Upgraded the sources workspace with multi-select bulk actions for corpus placement, sensitivity changes, reindexing, and enrichment on top of the existing live source controls
- Added operator-facing queue and trace ergonomics including filtered summaries, sortable lists, latency/fallback rollups, and clearer detail selection behavior when views narrow
- Expanded eval usability with a side-by-side report comparison view and added an explicit approval-inbox stub in the admin overview so the future workflow is visible without pretending it is fully wired yet
- See docs/milestones/m11_admin_workspace_polish_and_operational_ux.md

**M11.1 summary**
- Replaced raw upload polling with queue-aware indexing status that exposes current stage, ETA window, confidence, queue-delay messaging, and admin-reviewed priority-request state on the user workspace
- Shifted ingestion onto a real priority-aware queue worker with waiting-job ownership, bounded pause/resume/cancel/requeue/retry controls, and ETA recomputation based on file size, chunk discovery, and recent throughput
- Upgraded the admin jobs workspace into a real queue console with backlog and throughput summary cards, owner/stage/priority/source-type filters, priority preview and approval actions, and explicit queue-governance controls
- Extended the admin audit foundation for queue operations with stored request/decision/reprioritization/control events plus filterable/exportable JSONL audit output for enterprise review workflows
- See docs/milestones/m11_1_ingestion_queue_visibility_eta_and_priority_governance.md

**M12 summary**
- Added persisted Postgres/MySQL connector configuration with sync cursors and connector audit events
- Added read-only DB row ingestion that serializes rows into `db_row` sources, source parts, chunks, row provenance, and `db_rows` corpus policy metadata
- Preserved metadata filters such as `customer_id` and `region` in locator/provenance fields so they are enforced with SQL-level ACL trimming during retrieval
- Added a dedicated admin connector governance page for scoped request review, DB setup, schema inspection, sync preview, cursor/status visibility, and approved row syncs
- Kept the user connector workspace focused on scoped connector requests, Google Drive file request details, email archive requests, and connected-source visibility
- See docs/milestones/m12_cloud_db_and_structured_source_connectors.md

**M13 summary**
- Kept uploaded `.eml` parsing while preserving header/body-aware chunks and `email_casework` corpus policy routing
- Added a mailbox/archive email connector abstraction that normalizes enterprise email records into the same parsed source model as uploaded email
- Added attachment child-source ingestion for supported attachment file types, with parent-child links stored in `attachments`
- Added ingestion-time NUL character sanitization for parsed email/PDF attachment text and metadata so valid real-world attachments do not fail Postgres persistence
- Extended connector request screens so Email Archive and Google Drive file requests carry visible scope details and user-visible review status
- See docs/milestones/m13_enterprise_email_and_attachment_ingestion.md

**M14 summary**
- Added a governed tool registry for email, Slack, calendar, and report-generation actions
- Added role and corpus policy gates before tool execution
- Persisted tool invocation requests, completions, approval waits, and denials
- Logged blocked and allowed tool attempts into the admin audit trail
- See docs/milestones/m14_tool_actions_with_policy_gate.md

**M15 summary**
- Added rules-based sensitive detection for compensation, personal identifiers, secrets, and sensitive source labels
- Held sensitive answers behind approval requests instead of releasing the generated content
- Added approval review APIs and an admin Actions console for approving or denying requests with reason
- Wired approval decisions into the audit trail
- See docs/milestones/m15_human_approval_workflow.md

**M16 summary**
- Added backend clarification metadata for missing evidence, ambiguous wording/date/entity signals, and source suggestions
- Automatically records missing-evidence feedback for no-context answers
- Persisted helpful/not-helpful feedback and missing-source hints from chat
- Added admin visibility for top failed queries and recent feedback in the Actions console
- See docs/milestones/m16_fallback_clarification_feedback_loop.md

**M16.1 summary**
- Preserved SQL-level ACL enforcement while adding an access-limited clarification state for protected-source no-answer cases
- Added a dedicated access-request workflow with admin triage, routed business approver inbox tasks, and admin-executed temporary direct source grants
- Added workspace surfaces for requester tracking, approver decisions, and in-app notifications with email-ready payload persistence
- Extended access posture and retrieval behavior so approved temporary grants change results only for the intended user and only until expiry
- Refined the access-request workflow so requesters can provide business context plus optional suggested approver/manager details, admins can route without exact source ids, and approvers can map sources or return misrouted requests with alternate approver suggestions
- See docs/milestones/m16_1_access_limited_retrieval_routed_business_approval_and_time_bound_access_grants.md

**M17.a summary**
- Added a reusable enterprise ACL seed pack with canonical users, groups, memberships, protected/open source inventory, explicit source contacts, and executive-access mappings
- Added an idempotent `python -m app.seed.enterprise_acl` import path plus a `make seed-enterprise-acl` shortcut so the seeded environment can be recreated without ad hoc database setup
- Expanded `/admin/access` into a richer seeded-environment contract with source contacts, org edges, direct grants, and seed-pack readiness, then added management endpoints for memberships, ACL mappings, source contacts, bulk assignment, and user/source access explanations
- Upgraded the admin Access page into a working seeded ACL-management surface while preserving the M16.1 request-routing and direct-grant workflow
- Consolidated the local-dev test-user story by reusing the existing built-in and M16.1 identities first, then adding only the missing M17.2 personas such as restricted requester, governance observer, CEO, CFO, and misuse-test user
- See docs/milestones/m17_2_enterprise_seed_pack_acl_baseline.md

**M17.b.1 summary**
- Added durable `tuning_config_versions` storage so the production-active configuration and candidate drafts now exist as first-class operator-visible objects instead of being inferred only from scattered active-profile rows
- Seeded approved registry-backed LLM, embedding, and reranker options into the existing profile registry while keeping retrieval profiles under the established runtime profile model
- Added admin tuning endpoints for live configuration visibility plus candidate draft create/update/list workflows, and extended profile activation so the synced live tuning record stays current
- Reworked the admin Profiles page into a closer Stitch-faithful tuning-lab shell with a branded left rail, a live configuration spotlight card, an experimentation sandbox laid out with slider-style generation controls plus bottom model selectors, a right-side candidate rail, and shell-only compare/footer actions that stay truthfully gated for later M17.b milestones
- See docs/milestones/m17_b_1_live_configuration_candidate_drafts_and_approved_model_registry.md

**M17.b.2 summary**
- Added admin sandbox compare execution at `/admin/tuning/compare` so the same query now runs against live production and a governed candidate without mutating `active_profiles`
- Reused temporary profile override patterns to execute candidate LLM, reranker, retrieval-depth, and answer-time context-cap changes through the normal retrieval and answer path while preserving ACL trimming and citations
- Extended LLM profile/runtime handling with `top_p` and surfaced real compare output with latency, citation, and used-chunk deltas plus retrieval/rerank summaries
- Kept embedding selection visible but returns a truthful warning/precondition state when the candidate embedding differs from live, with a future-enhancement note for file-, corpus-, or folder-scoped shadow embedding experiments
- Updated the tuning lab UI so sliders/selectors are now interactive, chunk-size helper copy explains answer-time context cap semantics, and live/candidate results render side by side with grounded citations
- See docs/milestones/m17_b_2_interactive_sandbox_controls_and_side_by_side_compare.md

**M17.b.3 summary**
- Added audited promote-to-live and rollback APIs on top of candidate tuning versions, with prior live retention and operator promotion notes
- Added embedding experiment safety records with double-confirmation, locked selected-5-file scope, and full-corpus reindex job creation for all-file embedding changes
- Added model warm-up result recording for embedding and reranker candidates
- Extended the tuning lab with real promotion, rollback, version history, and retrieval-ops guardrail visibility
- See docs/milestones/m17_b_3_draft_promotion_rollback_embedding_safety_warmup.md

**M18 summary**
- Added optional query rewrite, expansion, and HyDE-style transform controls to retrieval profiles, all disabled by default
- Added a deterministic query transformation layer and trace metadata for original/effective/generated query variants, strategy, latency, and fallback
- Wired transformed query execution into retrieval while preserving the default baseline when transforms are off
- Exposed transformation posture in the tuning-lab ops guardrail panel
- See docs/milestones/m18_query_transformation_layer.md

**M19 summary**
- Added semantic cache tables, hit tracking, health API, and admin clear-cache action
- Cache scope includes normalized query, ACL scope hash, active profile snapshot hash, corpus scope hash, and retrieval mode
- Answering can serve cache hits only when the active retrieval profile enables semantic cache, with invalidation on profile activation, reindex, explicit clear, and TTL expiry
- Exposed cache health in the tuning-lab ops guardrail panel
- See docs/milestones/m19_semantic_cache.md

**M20 summary**
- Added query event capture for no-evidence answers, feedback outcomes, completed ask paths, and retrieval metadata
- Added failure clustering, annotation, and derived eval-pack APIs for real-query-driven retrieval improvement
- Exposed query mining counts and cluster build action in the tuning-lab ops guardrail panel
- Added smoke coverage for query event capture, cluster annotation, and derived eval-pack creation
- See docs/milestones/m20_retrieval_eval_ops_real_user_query_mining.md

**M21 summary**
- Added access-request risk signals for repeated similar requests and approver-swapping behavior
- Added reversible governance restrictions for extra review, access-request blocks, and severe query blocks with audit-backed unblock flow
- Enforced access-request restrictions in the request path and severe query blocks before ask generation
- Exposed governance risk/restriction counts in the tuning-lab ops guardrail panel
- See docs/milestones/m21_access_request_misuse_controls_user_blocking_governance_escalation.md

**M22 summary**
- Added a dedicated structured negative-feedback event log that captures thumbs-down reason, optional note, question, answer, citations, chunk/source ids, actor, profile snapshot, and request metadata
- Extended `/feedback` so helpful feedback remains lightweight while not-helpful feedback requires a guided reason and still records query-feedback/query-mining compatibility events
- Updated the chat workspace thumbs-down action to open a compact guided form and preserve copy/helpful/citation interactions
- Added admin Actions visibility for structured answer failures and reason-count summaries
- See docs/milestones/m22_structured_negative_feedback_capture_and_answer_failure_logging.md

**M23 summary**
- Added explicit auth posture handling for `AUTH_MODE=none|dev|password|oidc` and `APP_ENV=local|dev|staging|prod`
- Added startup safety checks for unsafe staging/prod modes, reserved password auth, and weak/default secrets
- Restricted local-dev login and impersonation endpoints to explicit local/dev runtime plus dev auth mode
- Kept no-auth research mode intentional while admin and connector-control paths fail closed
- See docs/milestones/m23_security_posture_hardening_and_explicit_auth_modes.md

**M24 summary**
- Added scenario-aware authorization to search, ask, compare, upload, batch upload, and connector request endpoints
- Disabled no-auth uploads by default while keeping an explicit `AUTH_NONE_ALLOW_UPLOAD` trusted-mode override
- Required admin/editor upload roles in secured modes and retained uploader metadata binding
- Added early 413 upload rejection, bounded chunked upload reads, and lightweight in-memory request throttling
- See docs/milestones/m24_endpoint_authorization_upload_safety_and_abuse_controls.md

**M25 summary**
- Extended semantic-cache scoping with direct-grant fingerprints and reauthorized cached citations before serving cached answers
- Fenced retrieved context as untrusted source text and added log-only indirect prompt-injection signal detection during ingestion/retrieval
- Added env-driven CORS allowlists, security headers, secure non-local cookie posture, and CSRF checks for cookie-authenticated mutations
- See docs/milestones/m25_cache_prompt_injection_session_browser_security.md

**M26 summary**
- Extended non-local secret validation for HTTPS, database passwords, OIDC secrets, and provider API-key posture
- Added tamper-evident admin audit hash chaining plus an integrity-check endpoint
- Added retention/redaction controls for query events, feedback, traces, semantic cache, and audit review metadata
- Hardened parser archive handling and restricted model warm-up to approved registry models by default
- See docs/milestones/m26_secrets_audit_integrity_retention_parser_hardening.md

**M27 summary**
- Added `docs/scenario_profiles_and_reuse_blueprint.md` as the scenario-first entry point for reusing this repo as a modular RAG starter
- Documented keep/disable/replace checklists for small-enterprise corpus access, employee-wide RAG, trusted no-auth research, and enterprise OIDC + ACL + governance
- Added a Mermaid module-selection map and a doc validation test to keep scenario guidance anchored to real repo paths
- See docs/milestones/m27_scenario_profiles_and_reuse_blueprint_documentation.md

**M28 summary**
- Added an explicit access strategy layer for `none`, `employee_all`, `corpus_level`, `document_acl`, and `document_acl_with_time_bound_grants`
- Added corpus-level access grants and SQL-level corpus authorization while preserving the strongest document ACL plus time-bound grant behavior as the default
- Reused the same strategy for retrieval, chunk materialization, source browsing, citation context, file access, and semantic cache reauthorization
- See docs/milestones/m28_access_strategy_abstraction_and_corpus_level_authorization.md

**M29 summary**
- Added scenario-aware admin module presets and `ADMIN_MODULES_ENABLED` overrides so smaller products can hide advanced admin capabilities without deleting code
- Added `/admin/modules`, backend module enforcement for direct API access, and frontend admin navigation/route gating
- Preserved the full enterprise admin console as the default scenario
- See docs/milestones/m29_modular_admin_console_and_feature_flag_packaging.md

**M30 summary**
- Added reusable scenario build packs for no-auth research, employee-wide RAG, small-enterprise corpus ACL, and full enterprise OIDC ACL
- Added scenario env samples, admin module inventories, validation checklists, reuse runbooks, and an acceptance report template
- Added `make scenario-validate` plus scenario pack validation tests
- See docs/milestones/m30_scenario_build_packs_validation_suites_and_reuse_runbooks.md

**M9 summary**
- Added explicit corpus policies for legal, transcripts, db rows, email/casework, and the default baseline
- Source-scoped retrieval now honors corpus default modes so different corpora behave differently without changing global settings
- Chunking now adapts target size and overlap by corpus policy, and transcript-oriented policies emit speaker/time metadata
- Added structured metadata filters for row-shaped corpora plus a corpus-policy eval matrix fixture and smoke coverage
- See docs/milestones/m9_per_corpus_indexing_and_adaptive_chunking_policies.md

**M8 summary**
- Expanded the reranker profile into a policy layer with selective controls by mode, corpus, candidate depth, and latency budget
- Added rerank policy traces so operators can see when reranking was applied, skipped, and which candidate corpora were considered
- Reserved an explicit MMR placeholder hook in the rerank trace without changing current ranking behavior
- Extended compare-eval with rerank A/B variants and a latency delta report for rerank-off vs rerank-on comparisons
- See docs/milestones/m8_reranking_policy_layer.md

**M7 summary**
- Expanded lexical-first routing for quote-like exact wording queries, identifier/code lookups, and date-heavy lexical queries
- Kept semantic-first queries on the hybrid baseline while preserving graph/temporal readiness fallback behavior
- Added structured route metadata to retrieval traces and retrieval-eval outputs: route class, preferred mode, and per-signal route details
- Added a router benchmark fixture pack covering quote, code, semantic, and temporal query sets
- See docs/milestones/m7_router_and_lexical_intent_expansion.md

**M6 summary**
- Preserved linear fusion as the default hybrid baseline while adding configurable `rrf` support through retrieval profile settings
- Added explicit retrieval fusion settings for `fusion_method` and `rrf_k`
- Extended retrieval traces and score diagnostics with fusion method, rank inputs, and per-method component scores
- Updated benchmark fixtures and compare reporting so fusion-method comparisons are visible in reports
- See docs/milestones/m6_hybrid_fusion_upgrade.md

**M5 summary**
- Added admin-role enforcement for `/admin/*` so the control plane is no longer reachable by authenticated non-admin users
- Added corpus registry APIs to create, update, list, and assign sources to corpora without editing code
- Added admin surfaces for retrieval profile metadata/defaults, query-time retrieval debug traces, eval triggers, report listing, and ingestion/enrichment job inspection
- Added admin reindex and enrichment trigger endpoints on top of the existing synchronous ingestion/enrichment flows
- See docs/milestones/m5_admin_api_control_plane.md

**M1 summary**
- DB-backed profile registries: embedding, reranker, LLM, retrieval, eval_pack
- Admin endpoints: GET /admin/profiles, POST /admin/profiles/active
- Resolver overlay pattern with TTL cache + Settings fallback
- All consumers (embedder, reranker, LLM client, retrieval) wired to profiles
- Eval reports include active profile metadata snapshot
- See docs/milestones/m1_profiles_and_retrieval_controls.md

**M2 summary**
- Request-level retrieval traces stored in `retrieval_traces` with requested/resolved mode, retrieval path, candidate counts, fallback reason, answer path, and active profile snapshot
- Stage-level latency traces captured for `search`, `rerank`, `ask`, and `total`, with `search_total` preserved on ask flows
- Score-path diagnostics persisted for top candidates: vector, keyword, combined, rerank, and anchor score
- Admin inspection endpoints added for trace listing and single-trace lookup
- Eval outputs include `report_metadata` with active profiles, retrieval settings, and per-case trace summaries
- See docs/milestones/m2_retrieval_observability_and_traceability.md

**Next actions**
- Start M17: fast/slow and budget-aware query policies
- Add latency/token budget-aware orchestration
- Make fast and slow retrieval policies explicit and measurable

**Notes / DoD checklist (M10)**
- [x] Anonymous users can view the homepage but cannot access `/console/*`
- [x] Login flow routes users into the correct workspace by role
- [x] Users can search, chat, upload, inspect citations, and browse sources from the new console
- [x] Admins can operate current control-plane capabilities from the new console UI
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M10.1)**
- [x] Stitch-backed public and console routes now drive the visible UI
- [x] Local test-user and test-admin auth still works without changing the backend auth contract
- [x] Non-reference routes redirect back to the Stitch-backed surfaces
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M10.1.1)**
- [x] A first-time local user does not hit a dead-end primary login CTA
- [x] Test user and admin entry flows are explicit enough for a clean-machine first run
- [x] SSO-first branding remains intact in real deployed environments without breaking local usability
- [x] docs/milestones/ note added
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
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M10.1.2.1)**
- [x] Copy action shows visible success feedback and still copies the answer
- [x] Helpful / not-helpful answer controls are interactive without introducing backend logging early
- [x] Retrieved-source groups default to a more scannable collapsed state
- [x] Retrieved-source rail selection and collapse state survive refresh within the same thread
- [x] Selected context shows source-aware locator details with readable title/link formatting when available
- [x] Upload and source readiness states explain when a document is actually searchable
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M10.1.3)**
- [x] Every advertised admin destination is a real page, not a redirect back to the dashboard
- [x] The overview page remains intact and useful for a real admin on first login
- [x] Admins can use current live controls where supported and still gain value from read-only/live-summary pages where deeper controls arrive later
- [x] The admin console feels like an operator workspace rather than a pretty summary shell
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M10.1.3.1)**
- [x] Admin overview never invents system state when APIs return empty or unavailable data
- [x] Every admin sidebar destination is both real and operationally meaningful
- [x] Sources, corpora, jobs, profiles, evals, traces, policies, access, and audit each have a distinct operator purpose
- [x] Audit log is backed by stored admin events, not inferred summaries
- [x] Admin can understand what happened, who changed it, and what object was affected without using the terminal or database directly
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M10.1.4)**
- [x] No primary CTA appears clickable while doing nothing
- [x] Demo and trial flows set the right expectation for enterprise/private-beta reality
- [x] Placeholder actions are intentional and legible rather than feeling broken
- [x] Useful overview and summary surfaces remain visible while misleading dead-end affordances are removed or disabled
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M10.1.5)**
- [x] A clean install feels intentionally empty rather than misconfigured
- [x] User and admin both have an obvious next step to make the product useful
- [x] Empty-state copy reduces the feeling that functionality is missing when the issue is simply lack of data
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M11)**
- [x] Non-developer can operate daily workflows comfortably with less engineering assistance
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M11.1)**
- [x] Users can see more than a raw status poll and are no longer forced to guess whether indexing delay is normal
- [x] ETA is present when reasonably inferable and degrades gracefully when confidence is low
- [x] Users can submit a priority request without bypassing governance
- [x] Admin can inspect the queue at both file and user level and take bounded, auditable action
- [x] Reprioritization updates affected queued-job timing/status rather than leaving stale expectations in place
- [x] Every queue-control and priority decision is audit-recorded with actor, reason, and impact
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M12)**
- [x] Can ingest DB rows into a corpus-backed `db_row` source
- [x] Can query synced DB rows with metadata filters preserved
- [x] Filters are enforced alongside SQL-level ACL trimming
- [x] Admin connector screen exposes DB configuration, schema preview, sync preview, sync, and visibility
- [x] User connector screen supports request submission and approved connected-source visibility
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M13)**
- [x] Uploaded `.eml` support remains intact
- [x] Email ingestion is no longer limited conceptually to uploaded `.eml`
- [x] Mailbox/archive records normalize into email header/body source parts
- [x] Supported attachments can be modeled as searchable child sources
- [x] Parsed email and attachment text is sanitized before DB persistence for Postgres-incompatible NUL characters
- [x] Source and connector pages expose email/mailbox-style request flows
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M14)**
- [x] Tool invocation works for allowed users
- [x] Denied actions are blocked and logged
- [x] Role and corpus policy gate exists
- [x] Tool invocation request, payload, status, and result/denial are persisted
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M15)**
- [x] Sensitive query triggers approval path
- [x] Nothing sensitive is released without approval
- [x] Approval queue stores pending approvals
- [x] Admin can approve or deny with reason
- [x] Full audit trail exists
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M16)**
- [x] Missing-evidence queries do not hallucinate
- [x] Feedback is captured and visible
- [x] Missing source hints are captured from the user chat
- [x] Clarification path has backend/product contract
- [x] Admin can see top failed queries
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M9)**
- [x] Different corpora behave differently by policy
- [x] Policies are explicit and test-covered
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M8)**
- [x] Reranking can be enabled selectively rather than globally
- [x] Operators can compare rerank-off vs rerank-on quality and latency
- [x] Future MMR hook is planned without blocking milestone completion
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M7)**
- [x] Router routes quote-like and ID-like queries more reliably
- [x] Route decisions are inspectable in debug traces
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M6)**
- [x] Linear remains the default and regression-safe baseline
- [x] RRF can be enabled by retrieval config/profile
- [x] Fusion comparisons are visible in reports
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M5)**
- [x] Admin can reindex without code changes
- [x] Admin can run evals and inspect report listings over API
- [x] Retrieval defaults and active profile metadata are inspectable over API
- [x] Basic ingestion/enrichment job status surface is available
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**M4 summary**
- Added authz data model tables for users, groups, memberships, and document ACL mappings
- Added `sources.sensitivity_label` to support `public` / `internal` / `confidential` style gating
- Retrieval SQL now trims results at query time based on the authenticated principal’s synced group memberships
- Chunk fetch paths used for graph/deep-research supplementation also enforce the same ACL predicate
- Forbidden documents are excluded before answer assembly so citations cannot leak restricted doc ids
- Search audit logs record user identity, groups, corpus labels, document ids, and sensitivity labels
- See docs/milestones/m4_authorization_and_acl_security_trimming.md

**Notes / DoD checklist (M4)**
- [x] Two test users with different groups get different retrieval results
- [x] Forbidden content cannot appear in retrieved chunks nor citations
- [x] Audit log records user, groups, corpus, doc ids accessed
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**M3 summary**
- Generic OIDC settings and discovery-based auth support added for Azure AD / Okta / Google Workspace style providers
- Backend auth middleware validates JWTs from bearer headers or auth cookies and attaches authenticated user context to each request
- `/auth/login`, `/auth/callback`, `/auth/logout`, `/auth/me`, and `/auth/providers` endpoints added for backend-managed login flow support
- `/ask` and `/ask/stream` require auth when `AUTH_ENABLED=true`
- Structured logs now include authenticated user identity and simple mapped roles: `user`, `admin`, `approver`
- See docs/milestones/m3_identity_and_sso_auth.md

**Notes / DoD checklist (M3)**
- [x] `/ask` requires auth
- [x] user identity appears in logs/audit events
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M2)**
- [x] Operators can explain why a query used a specific retrieval path
- [x] Latency is stored and inspectable per request
- [x] Eval output captures enough trace data to compare strategies meaningfully
- [x] docs/milestones/ note added
- [x] STATUS.md updated

**Notes / DoD checklist (M1)**
- [x] Switch embedding model by config and re-index successfully
- [x] Switch reranker on/off by config and see report deltas
- [x] Switch LLM model by config without breaking answer contract
- [x] Retrieval defaults are stored and visible by profile
- [x] Eval reports store active profile metadata
- [x] docs/milestones/ note added
- [x] STATUS.md updated
