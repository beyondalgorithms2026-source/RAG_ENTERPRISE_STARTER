# Enterprise RAG Starter — Milestone Project Plan (from stable baseline)

**Objective (one sentence)**  
Build an enterprise-usable RAG system based on `RAG_MM_MASTER_POC` that supports SSO + ACL security trimming, multi-source ingestion (including cloud DB and enterprise email), configurable retrieval/model controls, end-user chat UI + admin console, tool actions with approvals, feedback loops, and per-corpus indexing policies—without breaking baseline correctness.

**Plan note**  
This is a revised integrated milestone plan that supersedes the earlier draft ordering while preserving the original milestone intent. The sequence has been refreshed so retrieval maturity, observability, admin control, and evaluation readiness are built into the main roadmap rather than added as follow-on patches later.

**Audit note for this docs copy**  
This version adds an explicit `M10.1.x` finish-the-job sequence between M10 and M11 so M11 can remain true polish rather than absorb missing core console and first-run behavior.

**Core philosophy**
- Retrieval + governance are the hard parts.
- LLM is last-mile generation.
- Every milestone must preserve: correctness, citation provenance, and security boundaries.
- Retrieval changes must be measurable, reversible, and explainable.

---

## 0) What this system DOES

### End-user capabilities
- “Claude-like” chat UI
- Answers grounded in approved sources with citations
- Fast/Slow toggle with visible tradeoffs
- Feedback loop (helpful/not, missing source prompts)
- Retrieval-aware clarification and “no evidence” handling later in the roadmap

### Admin capabilities
- Corpus management (create, enable/disable, sensitivity labels)
- Run indexing/reindexing and connectors
- Configure profiles (embedding model / reranker / LLM / retrieval policy) through governed admin workflows in later milestones
- Run eval packs; compare reports
- Human approval queue for sensitive responses/actions
- Audit logs and retrieval/latency traces
- Future retrieval tuning controls (fusion mode, rerank policy, query transformation, cache policy)

### Engineering capabilities
- Pluggable ingestion connectors (uploads + DB; later drive/slack/email)
- Pluggable retrieval policies per corpus (legal vs transcripts vs structured DB rows)
- Observability (latency/cost traces, retrieval score traces, errors)
- Regression testing (eval pack as a gate)
- Retrieval experimentation without breaking the answer contract

---

## 1) What this system does NOT do (explicit non-goals initially)

These are intentionally out of scope until later (or ever):
- Multi-tenant SaaS platform (workspaces/quotas/billing)
- Full async distributed ingestion pipeline (we may add async jobs, but not a Kubernetes-grade pipeline)
- Full “data residency / sovereign” guarantees (depends on deployment)
- Perfect answers / “no hallucinations” claims
- Real-time transactional truth for ERP/CRM without explicit tool integration
- “Autonomous” retrieval tuning without eval gates and rollback paths

---

## 2) Underlying architecture (high level)

Two planes:

### Ingestion Plane (build + refresh knowledge)
- Source connectors → parsing/adapters → chunking → embeddings → index storage → optional enrichment

### Query Plane (serve answers safely)
- Auth/SSO → policy/ACL trimming → retrieval routing → retrieval (keyword/vector/hybrid/etc.) → rerank (optional) → answer generation → citations + logging → feedback/approval workflows

Key design rules:
> Security trimming must happen inside retrieval (DB query/filter), not just in UI.

> Retrieval changes must surface operator-visible diagnostics (mode, trace, latency, score path), not just better-looking answers.

---

## 3) Milestones (refreshed order to minimize rework)

### Milestone M0 — Baseline Stable Import (Gate 0)
**Goal:** replicate baseline upload → search → ask → eval in the new repo.

**DoD**
- `/upload`, `/search`, `/ask` work (mode `hybrid`)
- citations included in `/ask`
- eval harness runs + produces reports
- git tag: `baseline-import-stable`

**Re-run checks**
- baseline smoke tests
- at least one eval pack run

---

### Milestone M1 — Profiles And Retrieval Controls (Gate 1: configurability without UI)
**Why now:** model swaps and retrieval tuning become invasive if they are not formalized early.

**Deliverables**
- `EmbeddingProfile` registry (name, model, dimension, batch settings)
- `RerankerProfile` registry (name, top_n, score threshold)
- `LLMProfile` registry (provider/model, max tokens, temperature, timeout)
- `RetrievalProfile` registry:
  - default mode
  - candidate caps
  - rerank defaults
  - deep-research defaults
  - fusion method placeholder (`linear` now, `rrf` later)
- `EvalPack` registry (dataset name → questions + expected cues + corpus scope)
- Backend endpoints (admin-protected later):
  - `GET /admin/profiles`
  - `POST /admin/profiles/active`

**DoD**
- Switch embedding model by config and re-index successfully
- Switch reranker on/off by config and see report deltas
- Switch LLM model by config without breaking answer contract
- Retrieval defaults are stored and visible by profile
- Eval reports store active profile metadata

**Re-run checks**
- baseline eval pack (A vs B compare)

---

### Milestone M2 — Retrieval Observability And Traceability (Gate 2: tune what you can see)
**Why now:** retrieval experimentation without traces becomes cargo-cult tuning.

**Deliverables**
- Request-level retrieval trace standard:
  - requested mode
  - resolved mode
  - retrieval path used
  - candidate counts
  - fallback reason
  - answer generation path
- Stage-level latency traces:
  - search
  - rerank
  - ask
  - total
- Score-path diagnostics for debug/eval:
  - vector score
  - keyword score
  - combined score
  - rerank score when present
- Report metadata includes active profile + retrieval settings

**DoD**
- Operators can explain why a query used a specific retrieval path
- Latency is stored and inspectable per request
- Eval output captures enough trace data to compare strategies meaningfully

**Re-run checks**
- baseline eval pack
- one trace inspection example per mode

---

### Milestone M3 — Identity + SSO Auth (Gate 3: no anonymous access)
**Deliverables**
- OIDC login support (Azure AD / Okta / Google Workspace)
- Backend auth middleware validates JWT and attaches user context
- Role concept introduced: `user`, `admin`, `approver` (simple first)

**DoD**
- `/ask` requires auth
- user identity appears in logs/audit events

**Re-run checks**
- smoke tests with auth enabled

---

### Milestone M4 — Authorization + ACL Security Trimming (Gate 4: no data leakage)
**Deliverables**
- Data model:
  - users, groups, memberships
  - `document_acl` mapping (doc_id → group list)
  - corpus sensitivity label (public/internal/confidential)
- Retrieval filters enforce ACL at query time (SQL-level)
- Citations are also trimmed (no leaked doc ids)

**DoD**
- Two test users with different groups get different retrieval results
- Forbidden content cannot appear in retrieved chunks nor citations
- Audit log records: user, groups, corpus, doc ids accessed

**Re-run checks**
- ACL-specific eval pack (“leak tests”)

---

### Milestone M5 — Admin API Control Plane (Gate 5: operable without code edits)
**Deliverables**
- Admin-only endpoints:
  - corpora create/update/list
  - reindex trigger
  - profile switch
  - eval run trigger + report listing
  - retrieval trace for a query (debug)
  - retrieval profile metadata + strategy defaults
- Basic job status surface (even if sync initially)

**DoD**
- Admin can reindex and run eval without code changes
- Reports visible + comparable
- Retrieval defaults inspectable over API

---

### Milestone M6 — Hybrid Fusion Upgrade (Gate 6: stable retrieval scoring)
**Why now:** fusion logic affects every later retrieval comparison.

**Deliverables**
- Keep current linear fusion as baseline-safe behavior
- Add configurable fusion method:
  - `linear`
  - `rrf`
- Add explicit fusion settings to retrieval profile/config
- Add score-trace support for fusion debugging
- Update eval packs to compare fusion methods on lexical vs semantic-heavy queries

**DoD**
- Linear remains default and regression-safe
- RRF can be enabled by config/profile
- Fusion comparisons are visible in reports

**Re-run checks**
- exact-match lookup benchmark
- semantic paraphrase benchmark
- hybrid regression pack

---

### Milestone M7 — Router And Lexical Intent Expansion (Gate 7: better first strategy choice)
**Deliverables**
- Expand exact-lookup detection for:
  - exact quote / final words / exact wording
  - IDs, codes, SKUs, case numbers
  - date-heavy lexical queries
- Separate lexical-first vs semantic-first query classes
- Add operator-visible route reason details

**DoD**
- Router routes quote-like and ID-like queries more reliably
- Route decisions are inspectable in debug traces

**Re-run checks**
- router benchmark cases across quote / code / semantic / temporal query sets

---

### Milestone M8 — Reranking Policy Layer (Gate 8: quality without uncontrolled cost)
**Deliverables**
- Move beyond one boolean reranker switch
- Add rerank policy controls:
  - by mode
  - by corpus
  - by candidate depth
  - by latency budget
- Reserve optional MMR/diversity placeholder after reranking

**DoD**
- Reranking can be enabled selectively rather than globally
- Operators can compare rerank-off vs rerank-on quality and latency
- Future MMR hook is planned without blocking milestone completion

**Re-run checks**
- rerank A/B eval
- latency delta report

---

### Milestone M9 — Per-Corpus Indexing And Adaptive Chunking Policies (Gate 9: domain-shaped retrieval)
**Deliverables**
- Corpus policies:
  - legal: keyword + hybrid default, smaller chunks, strict citations
  - transcripts: semantic-first, overlap windows, speaker/time metadata
  - DB rows: structured metadata filters
  - email/casework: header/body aware and attachment-aware policies later
- Parser routing by file type and corpus policy
- Selective adaptive chunking policy framework:
  - chunk size by corpus type
  - overlap by corpus type
  - future document-class overrides

**DoD**
- Different corpora behave differently by policy
- Policies are explicit and test-covered

**Re-run checks**
- corpus-policy eval matrix

---

### Milestone M10 — Next.js Enterprise Console UI (Gate 10: usable UX)
**Deliverables**
- New Next.js 15 App Router frontend in `web/` as the primary product UI
- Public marketing homepage at `/`
- SSO-first login and register entry pages
- Authenticated role-aware console under `/console/*`
- User workspace with:
  - unified search and grounded chat
  - session-level thread history
  - citations and evidence panel
  - fast/slow control
  - retrieval path and latency visibility where appropriate
  - self-service uploads
  - source listing
  - connector request UI stub for later connector milestones
- Admin workspace pulled forward into M10 with:
  - corpora management
  - ingestion/indexing job views
  - profile selection
  - eval reports and triggers
  - retrieval trace review
  - retrieval/rerank/corpus policy metadata inspection
- Backend integration kept on existing contracts:
  - `/auth/*`
  - `/ask`, `/ask/stream`, `/search`
  - `/corpus`, `/upload`
  - `/admin/*`
- Minimal backend support changes only:
  - allow the Next.js origin in CORS
  - root redirect points to the new frontend entrypoint

**DoD**
- Anonymous users can view the homepage but cannot access `/console/*`
- Login flow lands users in the correct workspace by role
- Users can search, chat, upload, inspect citations, and browse sources reliably
- Admins can operate current control-plane capabilities without code edits
- Retrieval/latency metadata remains explainable, not noisy
- Legacy static frontend is no longer the primary product path

---

### Milestone M10.1 — Truthful Console IA While Preserving The Existing Design (Gate 10.1: no misleading UX)
**Why now:** the first console shell already has the right enterprise shape. The next step is not to redesign or strip it down, but to preserve that design and make every route, page, and summary surface honest about what is live now, what is read-only, and what will deepen in later milestones.

**Deliverables**
- Keep the current console design language and left-nav information architecture as the default direction
- Keep overview pages where they are useful:
  - admin landing remains a true system overview page
  - user landing/workspace can remain a launchpad into chat/history/sources flows
- Convert redirects into meaningful pages instead of collapsing them into unrelated destinations:
  - each sidebar item must open a page with a clear purpose
  - pages may begin as interactive, read-only, live-summary, or clearly marked limited-access states
- Define a page-state contract for every visible screen:
  - live and interactive
  - live and read-only
  - live summary with drill-downs still in progress
  - coming soon / request flow only where explicitly intentional
- UX contract document for what is available in M10, what is fulfilled in M10.1.x, and what is intentionally deepened in later milestones

**DoD**
- The existing console design is preserved rather than replaced
- No primary nav item silently redirects to an unrelated page
- User and admin can predict what each page is for before clicking it
- Overview pages remain in place and feel intentional, even when some controls are read-only or summary-only
- The product no longer feels misleading on first exploration

**Re-run checks**
- route inventory review across `/`, `/login`, `/console/workspace/*`, `/console/admin/*`
- manual UX pass for nav-label-to-destination truthfulness

---

### Milestone M10.1.1 — Local Dev Auth And First-Run Entry Path Coherence (Gate 10.1.1: first start feels working)
**Why now:** an SSO-first product can still fail the first-run bar if the primary login path dead-ends in local dev while the actual working path is hidden.

**Deliverables**
- Explicit local-dev auth contract:
  - if OIDC is configured, keep SSO-first entry
  - if OIDC is not configured, the login experience must clearly expose the supported dev path
- Login page behavior reflects backend auth availability instead of assuming SSO is always live
- First-run guidance for test users/admins is obvious and near the login action, not buried
- `/auth/providers` and related frontend behavior degrade gracefully when IdP metadata is unavailable
- Environment-level distinction between local-dev, staging, and production auth expectations is documented

**DoD**
- A first-time local user does not hit a dead-end primary login CTA
- Test user and admin entry flows are explicit enough for a clean-machine first run
- SSO-first branding remains intact in real deployed environments without breaking local usability

**Re-run checks**
- local-dev login smoke with OIDC disabled
- login smoke with dev auth enabled
- auth gate redirect check for `/console/*`

---

### Milestone M10.1.2 — User Workspace Contract Completion (Gate 10.1.2: user surface matches promise)
**Deliverables**
- Keep the existing user workspace structure where it helps comprehension:
  - chat
  - history
  - my sources
  - uploads
  - connectors or source requests
- Convert each visible user route into a meaningful page with a clear role, even if some begin as read-only or limited-scope
- Establish an explicit local-dev retrieval contract for the built-in test identities:
  - in `AUTH_MODE=dev`, `test-user` and `test-admin` can retrieve from uploaded/dev-visible sources by default so they can validate the full end-to-end product flow
  - if explicit ACL rules exist for a source, those explicit rules still win
  - strict production-style ACL behavior remains unchanged outside local dev mode
- Prevent newly uploaded dev sources from becoming silently invisible to retrieval because of internal sensitivity labels with no matching ACL mapping
- Define the minimum page contract for each user screen:
  - what data is live now
  - what actions are interactive now
  - what actions are visible but intentionally read-only
  - what actions move to later milestones
- Chat request lifecycle contract:
  - show visible in-progress states immediately after submit
  - reflect backend progress labels during `/ask/stream`
  - always render a terminal state: success, no evidence found, failed
  - never leave the thread pane blank after a submitted question
- Upload request lifecycle contract:
  - upload returns quickly with a job/source reference instead of blocking the page through the entire ingest pipeline
  - sources page shows live stage/status updates such as parsing, chunking, embedding, indexed, failed
  - users can tell whether a file is queued, working, completed, or failed without reading backend logs
- Thread persistence contract:
  - a new thread and user message are durably stored before route transition
  - assistant results remain attached to the correct thread after navigation, refresh, or remount
  - route transitions must not blank the conversation because of client-state races
- Evidence panel minimum interaction contract:
  - citation click behavior
  - source/context drill-in behavior
  - retrieval-path and latency visibility rules
- No-context and no-results contract pulled forward from later UX ideas:
  - if retrieval returns zero usable chunks, the assistant must explicitly say so in-thread
  - the UI should suggest likely next steps such as asking with exact words, checking source visibility, or opening `My Sources`
  - richer clarification and feedback loops may deepen later, but the base no-evidence state must already be usable here
- Thread/history contract clarified:
  - session-local vs persisted history
  - what survives reload vs browser/device changes
- Audit all visible user controls:
  - feedback
  - copy/export
  - attachment/image/mic affordances
  - any CTA that implies retrieval or source actions
- Convert placeholders into one of:
  - real functionality
  - clearly disabled “coming soon”
  - read-only or limited-scope visibility with explicit copy
  - request flow for future capabilities such as connectors
- Uploads and connectors may remain distinct pages if they each expose a truthful contract:
  - upload page = file/job status and source onboarding
  - connectors page = request flow now, real connector configuration in later milestones

**DoD**
- Built-in dev test accounts can exercise the end-to-end user workflow without being accidentally blocked by implicit ACL gaps
- User-facing actions no longer feel decorative or mismatched
- Citation/evidence interactions increase trust instead of acting like static display chrome
- Workspace behavior around history and persistence is predictable to non-technical users
- The console no longer suggests capabilities that disappear into unrelated routes
- Distinct user pages may remain distinct as long as each one has a truthful, useful contract
- Ask and upload flows always show visible progress and a visible terminal state rather than a blank or frozen interface
- No-context questions render an explicit assistant response instead of a confusing empty chat state

**Re-run checks**
- authenticated user journey: login → ask → inspect evidence → view history → upload source
- authenticated user journey in local dev: upload a source → ask a question from that source → retrieve grounded evidence without manual ACL intervention
- upload job-state pass: accepted → parsing/chunking/embedding → completed or failed
- no-context rendering pass: zero-result search shows explicit assistant feedback in-thread
- thread persistence pass across route transition and refresh
- citation/evidence interaction pass
- empty-history and populated-history UX pass

---

### Milestone M10.1.2.1 — User Workspace Interaction Polish And Upload Readiness Clarity (Gate 10.1.2.1: user interactions feel legible and trustworthy)
**Why now:** M10.1.2 made the user workspace truthful and functional. This short follow-up tightens the remaining rough edges so M10.1.3 can stay focused on admin completeness instead of absorbing avoidable user-console polish work.

**Deliverables**
- Modernize answer action controls without pulling the full feedback-loop milestone forward:
  - `Copy answer` stays functional and shows visible acknowledgement
  - `helpful` / `not helpful` become live client-side controls
  - no backend persistence yet
- Make the retrieved-sources rail easier to scan in long threads:
  - older answer groups default collapsed
  - clearer expand/collapse affordance
  - citation clicks open the matching answer section instead of feeling like unrelated sidebar motion
- Improve selected-context clarity:
  - source file name shown prominently
  - page / section / chunk locator metadata shown when available
  - avoid fake page numbers for plain-text sources
- Clarify upload and source readiness semantics:
  - `chunked` means not searchable yet
  - `embedding` / processing means still preparing retrieval state
  - `embedded` / `indexed` means ready for search and ask
- Explain that repeated `/corpus` and `/corpus/jobs/*` requests are expected polling during live progress refresh

**DoD**
- Copy action shows visible success feedback and still copies the answer
- Helpful / not-helpful controls feel intentional rather than decorative
- Multi-turn evidence sections are easier to scan by default
- Selected context identifies the source more clearly than a generic panel heading
- Users can tell whether an uploaded document is actually ready for retrieval without reading backend logs

**Re-run checks**
- multi-turn chat UX pass covering citation click, evidence expand/collapse, and answer-action feedback
- upload readiness pass from upload accepted through indexed/embedded
- source table review for searchable vs non-searchable state clarity

---

### Milestone M10.1.3 — Admin Workspace Route Wiring And Operator Completeness (Gate 10.1.3: routed control plane)
**Why now:** backend admin APIs and richer admin views may already exist, but the product is not operator-complete until the sidebar resolves to real pages and the dashboard is treated as an overview page rather than a catch-all proxy.

**Deliverables**
- Keep the existing admin console layout and overview-first design
- Preserve the admin landing page as a true `System Overview` screen showing health, corpus state, job state, retrieval quality, and operator quick actions
- Wire the admin sidebar to real, distinct pages for:
  - corpora
  - jobs
  - profiles
  - evals
  - traces
  - policies
- For each admin page, allow one of three truthful launch states:
  - interactive if backend support already exists
  - read-only if live backend data exists but controls are still being wired
  - live summary if the page is meant to orient operators before deeper workflow controls arrive
- Expose current backend control-plane capabilities through the routed admin UI where already supported:
  - corpus inspection and management
  - indexing/reindex/job visibility
  - profile selection
  - eval trigger/report review
  - trace inspection
  - retrieval/rerank/corpus policy metadata inspection
- Explicitly map deeper admin controls that are not yet wired to later milestones instead of removing the page concept

**DoD**
- Every advertised admin destination is a real page, not a redirect back to the dashboard
- The overview page remains intact and useful for a real admin on first login
- Admins can use current live controls where supported and still gain value from read-only/live-summary pages where deeper controls arrive later
- The admin console feels like an operator workspace rather than a pretty summary shell

**Re-run checks**
- admin route smoke across all sidebar destinations
- operator journey: corpus review → profile switch → eval trigger → trace review

---

### Milestone M10.1.3.1 — Admin Trustworthiness, Operational Depth, And Audit Foundations (Gate 10.1.3.1: truthful operator control plane)
**Why now:** `M10.1.3` makes the admin workspace routable and recognizable, but it is not yet operator-grade if overview metrics can be fabricated, important pages are still shallow, or auditability is missing.

**Deliverables**
- Remove fake fallback signals from the admin landing page:
  - no invented corpus/job/eval/document counts
  - no fabricated notifications or placeholder trace rows
  - empty and unavailable states shown explicitly when real data is missing
  - metric formatting corrected so source counts are not shown as fake `k` values
- Upgrade the admin console from route-complete to operator-truthful:
  - overview becomes a real health and queue summary driven by live admin contracts
  - jobs page upgraded from list-only into queue and execution visibility with useful status, timing, actor, and failure context
  - traces page upgraded from recent-summary list into a real debug surface with drill-in
  - corpora page upgraded from create/list into corpus detail plus source-assignment visibility
  - profiles page upgraded from active-toggle only into a clearer live profile inventory with activation history visibility
  - evals page upgraded from run/list into real report-state and comparison-oriented operator flow
- Add missing admin information architecture so operators are not forced to infer state from unrelated pages:
  - `Sources` route for source-level inventory, status, corpus placement, and admin actions
  - `Access` route for user/group/document-ACL visibility and enterprise access posture
- Introduce a real audit log foundation:
  - append-only admin audit events stored separately from retrieval traces
  - profile activation, corpus edits, source assignment, reindex/enrich actions, eval runs, and other admin mutations are audit-recorded
  - audit log page becomes a true event viewer rather than a summary assembled from jobs/traces
  - audit entries capture actor, action, target, before/after context where relevant, outcome, and timestamp
- Cross-link operator workflows:
  - jobs link to related source/corpus context
  - traces link to related request/debug context
  - audit entries link to affected source/job/profile/corpus when applicable
  - overview cards and alerts route into the correct admin page instead of acting as dead-end summaries
- Preserve the existing admin workspace structure while making it trustworthy enough for enterprise use

**DoD**
- Admin overview never invents system state when APIs return empty or unavailable data
- Every admin sidebar destination is both real and operationally meaningful
- Sources, corpora, jobs, profiles, evals, traces, policies, access, and audit each have a distinct operator purpose
- Audit log is backed by stored admin events, not inferred summaries
- Admin can understand what happened, who changed it, and what object was affected without using the terminal or database directly

**Re-run checks**
- admin truthfulness pass: no fake counts, fake notifications, or fake rows render when backend data is empty
- jobs/traces/corpora drill-in pass across routed admin pages
- audit pass: profile switch, corpus/source update, reindex, enrich, and eval trigger all create audit events
- operator journey pass: overview → source/job inspection → trace/debug review → audit verification

---

### Milestone M10.1.4 — Placeholder And CTA Hygiene Across Public And Console Surfaces (Gate 10.1.4: no dead ends)
**Deliverables**
- Audit and resolve all clickable elements on:
  - marketing homepage
  - login/register/demo/video pages
  - user console
  - admin console
- Establish a consistent policy for unfinished actions:
  - disabled with explanation
  - clearly marked “coming soon”
  - read-only/live-summary where visibility is useful to operators
  - hidden only when showing the affordance would be actively misleading
- Align `/register`, demo, free-trial, and video-tour flows with the actual product/business motion
- Footer and header navigation either point somewhere real or are intentionally removed

**DoD**
- No primary CTA appears clickable while doing nothing
- Demo and trial flows set the right expectation for enterprise/private-beta reality
- Placeholder actions are intentional and legible rather than feeling broken
- Useful overview and summary surfaces are allowed to remain visible even before every downstream action is interactive

**Re-run checks**
- click-through audit of all visible CTA/button/link affordances
- public page acceptance pass on desktop and mobile

---

### Milestone M10.1.5 — First-Run Empty States And Operator Onboarding (Gate 10.1.5: clean DB does not feel broken)
**Why now:** a first app start with an empty database is the most fragile moment for perceived product quality.

**Deliverables**
- Purposeful empty states for:
  - user chat/workspace
  - session history
  - sources/uploads
  - admin corpora/jobs/evals/traces views
- “What to do next” onboarding hints for first upload, first corpus, and first eval
- Clear distinction between:
  - no data yet
  - loading
  - actively processing
  - permission-limited visibility
  - failed backend call
- First-run checklist or embedded guidance for local dev operators
- Empty-state and in-progress copy must explain whether the system is waiting on upload, indexing, retrieval, or answer generation

**DoD**
- A clean install feels intentionally empty rather than misconfigured
- User and admin both have an obvious next step to make the product useful
- Empty-state copy reduces the feeling that functionality is missing when the issue is simply lack of data

**Re-run checks**
- clean DB UX pass
- first-upload UX pass
- first-admin-visit UX pass

---

### Milestone M11 — Admin Workspace Polish And Operational UX (Gate 11: non-dev operations)
**Deliverables**
- Follow-on admin improvements on top of the completed M10.1.x admin workspace:
  - follow-on UX polish on top of the completed truthful admin workspace
  - bulk-action refinement for already-existing admin workflows
  - filtering, saved views, and table ergonomics across jobs/sources/traces/audit
  - report comparison UX polish and operator quality-of-life improvements
  - operational quality-of-life improvements for non-developer operators
  - approval inbox remains summary/stub here and becomes a full workflow in M15

**DoD**
- Non-developer can operate daily workflows comfortably with less engineering assistance

---

### Milestone M11.1 — Ingestion Queue Visibility, ETA, And Priority Governance (Gate 11.1: enterprise indexing operations)
**Why now:** once the admin workspace is operational, indexing stops being just a background technical detail and becomes a shared enterprise workflow with fairness, urgency, and audit requirements.

**Deliverables**
- End-user upload/indexing visibility upgraded from raw status polling into a clearer job-progress contract:
  - current stage shown per file: queued, parsing, chunking, embedding, indexing/enrichment, completed, failed
  - estimated completion window shown when enough signal exists
  - queue-delay messaging shown when slower files or earlier jobs are ahead
  - completion-time expectation updates if enterprise-wide queue state changes materially
- ETA prediction framework for indexing jobs:
  - rough estimate available from file size and file type immediately after upload acceptance
  - improved estimate after parsing/chunk-count discovery
  - best estimate incorporates current queue depth and recent observed throughput
  - confidence band or estimate quality label exposed so low-confidence ETA is not presented as exact truth
- User-side priority/escalation request flow:
  - user can mark a newly uploaded file as urgent or submit a priority request with reason
  - request is routed into the admin workspace rather than directly bypassing queue policy
  - user can see request status: submitted, under review, approved, denied, expired
  - user-facing job status and ETA update if an admin takes action on the request
- Admin ingestion queue console upgraded from summary visibility into real queue operations:
  - queue visible at file, source, and user level
  - sortable/filterable by wait time, stage, priority, owner, corpus, file size, source type, and failure state
  - clear distinction between queued, actively running, retrying, blocked, and completed jobs
  - queue health summary: backlog, active workers, oldest waiting job, average chunks/minute, failure hotspots
- Admin queue controls with governance:
  - raise/lower priority for waiting jobs
  - approve/deny user priority requests with reason
  - pause, resume, cancel, retry, or requeue jobs where operationally safe
  - optional queue policies such as small-files-first, VIP override, or fairness guardrails by role/team
  - running-job behavior defined explicitly so unsafe mid-flight reordering is not implied if unsupported
- Enterprise-wide queue impact visibility:
  - when one job is expedited, downstream ETA/status for affected queued jobs is recalculated
  - affected users see truthful updated timing rather than stale original estimates
  - admin can preview estimated blast radius before confirming a reprioritization action
- Auditability for ingestion operations:
  - queue audit events extend the `M10.1.3.1` audit foundation rather than introducing a separate audit mechanism
  - append-only operational audit log for queue and priority actions
  - captures who requested priority, who approved/denied/reordered, when, why, what changed, and ETA impact
  - admin audit view supports filtering by user, file, job, action type, and time range
  - exportable audit artifact or log file available for enterprise review/compliance workflows

**DoD**
- Users can see more than a raw status poll and are no longer forced to guess whether indexing delay is normal
- ETA is present when reasonably inferable and degrades gracefully when confidence is low
- Users can submit a priority request without bypassing governance
- Admin can inspect the queue at both file and user level and take bounded, auditable action
- Reprioritization updates affected queued-job timing/status rather than leaving stale expectations in place
- Every queue-control and priority decision is audit-recorded with actor, reason, and impact

**Re-run checks**
- single-file upload ETA pass: upload accepted → stage progression → completion estimate narrows over time
- multi-file burst pass: queue depth changes are reflected in user-visible status/ETA
- priority-request pass: user submits request → admin approves/denies → user/job state updates correctly
- reprioritization pass: expedite one queued job and verify downstream queued-job ETA/status recompute
- audit pass: request, decision, reorder, cancel, retry, and completion-impact events are all recorded and filterable

---

### Milestone M12 — Cloud DB And Structured Source Connectors (Gate 12: multi-source)
**Deliverables**
- DB connector (read-only):
  - Postgres/MySQL source
  - row-to-document serialization
  - incremental ingestion by updated_at/id
- Metadata filters preserved (customer_id, region, etc.)
- Upgrade user/admin connector-related pages from request-flow or summary states into real connector configuration and visibility where the backend support exists
- Preserve the local-dev-first testing story while making connector-backed sources compatible with explicit corpus/ACL rules outside the dev bypass flow

**DoD**
- Can ingest DB data into a corpus and query it
- Filters work and are enforced alongside ACL trimming
- Connector-related screens are no longer just placeholders once DB connector support lands

---

### Milestone M13 — Enterprise Email And Attachment Ingestion (Gate 13: real email reality)
**Why now:** uploaded `.eml` is useful, but not enough for enterprise email workflows.

**Deliverables**
- Keep `eml` upload support
- Add enterprise email ingestion design/implementation path:
  - mailbox/archive connector abstraction
  - normalized email document model
  - attachment-as-child-source handling when attachment type is supported
- Attachment relationship model integrated with retrieval policy
- Extend source and connector pages to expose email/mailbox-style sources once these flows are implemented

**DoD**
- Email ingestion is no longer limited conceptually to uploaded `.eml`
- Attachments can be modeled as searchable child sources when enabled

**Re-run checks**
- email ingestion fixture cases
- attachment linkage checks

---

### Milestone M14 — Tool Actions With Policy Gate (Gate 14)
**Deliverables**
- Tool registry:
  - send_email
  - send_slack
  - create_calendar_event
  - generate_report (PDF/CSV placeholder)
- Policy gate:
  - which roles can trigger tools
  - which corpora allow which tools
- Audit every tool invocation (request + payload + status)

**DoD**
- Tool invocation works for allowed users
- Denied actions are blocked and logged

---

### Milestone M15 — Human Approval Workflow For Sensitive Outputs/Actions (Gate 15)
**Deliverables**
- Sensitive detection policy (rules-based first):
  - salary, compensation, personal identifiers, secrets
  - corpus sensitivity label influences behavior
- Approval queue:
  - pending approvals stored
  - approver can approve/deny with reason
- End-user sees: pending approval vs denied vs approved answer
- Admin approval-related overview cards or stub pages introduced earlier become a real interactive workflow here

**DoD**
- Sensitive query triggers approval path
- Nothing sensitive is released without approval
- Full audit trail exists

---

### Milestone M16 — Fallback, Clarification, And Feedback Loop (Gate 16)
**Deliverables**
- “No evidence found” behavior:
  - explicitly state insufficient evidence
  - ask user where the info should exist
  - capture suggested source link/upload request
- Clarification UX planning path:
  - ambiguous dates
  - likely spelling mismatch
  - entity ambiguity
  - quote/factoid clarification
- Feedback loop:
  - store successful/failed queries
  - “top failed queries” dashboard in admin UI
- User-facing feedback and missing-source affordances that were previously basic but functional in M10.1.2 become full closed-loop product behavior here
- Expand the basic no-context UX introduced in M10.1.2 into richer clarification flows for likely wrong wording, missing source visibility, or genuinely absent evidence

**DoD**
- Missing-evidence queries do not hallucinate
- Feedback captured and visible
- Clarification path has defined backend/product contract even if initially rules-based

---

### Milestone M16.1 — Access-Limited Retrieval, Routed Business Approval, And Time-Bound Access Grants (Gate 16.1)
**Why now:** extends M4 ACL trimming, M15 approval workflow, and M16 clarification/feedback into a full work-completion loop; should land before M17 so later retrieval policy work does not obscure access-limited failure handling.

**Deliverables**
- Preserve strict pre-retrieval ACL enforcement
- Add access-limited clarification state for insufficient accessible evidence
- Let user submit access request from failed query/search flow
- Let user provide business context plus optional suggested approver / owner email instead of requiring technical source identifiers
- Make it explicit in the request UX when lack of business context or owner/team detail may make routing difficult
- Let admin triage the request using question text, business context, source inventory, and ACL posture without always requiring explicit source ids up front
- Let admin route request to identified or suggested source owner / business approver
- Include ACL group manager and requester’s manager as copied observers
- Add approver inbox in normal user portal
- Allow approver decision options:
  - approve 24 hours
  - approve 7 days
  - approve 30 days
  - deny
- Allow approver return-to-admin outcomes for wrong-owner routing:
  - not real owner
  - does not concern me
  - suggest alternate approver
- Let approver identify or select source(s) during approval when admin could not confidently map the request to exact source ids at routing time
- Require admin confirmation before rerouting to an alternate approver suggested by a prior approver
- Require admin to execute final grant after business approval
- Use time-bound direct source grants, not group-membership mutation
- Add admin routing notes / coordinator comments visible to approvers
- Add in-app notifications for requester, approver, admin, and observers
- Persist email-ready notification payloads for later outbound email support
- Add audit trail for request, routing, rerouting, approval, return-to-admin, grant, expiry, and denial

**DoD**
- ACL remains enforced inside retrieval queries only
- No hidden source identity leaks in clarification state
- User can request access from failed-query flow
- User is not required to know source ids or exact filenames to submit a valid request
- Approver can act from normal login portal
- Wrong-owner routing can be returned to admin with reason and optional alternate approver suggestion
- Approver can complete source identification when admin routing context is insufficient
- Admin can complete only time-bound grants after approval
- Approved grant changes retrieval only for target user and only until expiry
- Expiry removes access automatically
- Notification and audit flows are visible to operators

**Re-run checks**
- M4 ACL leak tests still pass
- M15 approval workflow still passes
- M16 feedback and clarification tests still pass
- New request-routing and expiry-path tests pass once implemented

---

### Milestone M17 — Fast/Slow And Budget-Aware Query Policies (Gate 17)
**Deliverables**
- Fast policy:
  - smaller k
  - no rerank
  - smaller/cheaper LLM
- Slow policy:
  - bigger k
  - rerank on
  - optional query rewrite + deep lookup
- Budget-aware orchestration:
  - latency budget
  - token budget
  - rerank budget
  - retrieval depth budget
- Latency + cost metrics stored per request

**DoD**
- Slow improves hard questions measurably (eval deltas)
- User can choose mode; system can also auto-suggest mode
- Operators can explain latency/cost tradeoffs by policy

---

### Milestone M17.1 — Admin Retrieval Tuning Lab And Profile Rollout Controls (Gate 17.1: controlled admin customization)
**Why now:** real admin model and retrieval tuning should arrive only after traces, evals, queue governance, and operator auditability exist; otherwise configuration changes become hard to evaluate and risky to roll back.

**Deliverables**
- Upgrade admin profile controls from visibility/activation into real controlled tuning workflows:
  - embedding profile selection from registered embedding models
  - reranker profile selection and policy controls
  - LLM profile selection from approved registered models
  - retrieval-profile selection for mode, fusion, candidate caps, and budget posture
- Add an admin query workbench / tuning lab:
  - rerun a query against a chosen corpus/profile combination
  - compare current active profile vs candidate profile side by side
  - inspect trace deltas, citation differences, latency deltas, and eval implications
  - run controlled query-debug experiments without silently changing production defaults
- Add corpus-aware and source-type-aware tuning controls:
  - assign retrieval/rerank/profile defaults by corpus
  - allow policy by source or content shape where supported by corpus policy design
  - support testing different strategies for PDFs, transcripts, DB rows, email-style content, or other source classes through governed profile assignment rather than ad hoc switches
- Add safe embedding-model change workflow:
  - preview reindex impact before activation
  - show affected corpora/sources and estimated indexing blast radius
  - require explicit reindex workflow for embedding changes
  - preserve rollback path to prior active embedding profile
- Add safe rollout and auditability:
  - activation history and change provenance
  - audit records for every model/profile/policy change
  - optional compare-before-promote flow using eval reports or benchmark packs
  - no arbitrary freeform model strings in admin UI; only approved registry-backed profiles
- Extend admin console IA with a dedicated `Tuning Lab` route or equivalent routed surface once this milestone lands

**DoD**
- Admin can test and compare retrieval/model settings without code edits
- Embedding changes are treated as reindexing events, not casual toggles
- Rerank, LLM, and retrieval-profile changes are explainable, measurable, and auditable
- Customization by corpus/source type is supported through explicit policy/profile assignment
- Operators can promote or roll back settings with trace/eval evidence

**Re-run checks**
- profile compare pass: active vs candidate profile on benchmark queries
- rerank policy pass: off vs selective-on comparison
- LLM profile swap pass without answer-contract regression
- embedding profile change pass with reindex preview and audit trail
- corpus/source-type policy pass demonstrating different governed behavior across content classes

---

### Milestone M17.2 — Enterprise Test Environment Seed Pack, ACL Input Mapping, And Executive Access Baseline (Gate 17.2)
**Why now:** after core retrieval policy controls and before later retrieval sophistication, the system needs a realistic seeded enterprise test environment so ACL, routing, provenance, access requests, and admin workflows can be exercised against something closer to a real customer onboarding pack rather than ad hoc local setup.

**Deliverables**
- Add a full seeded enterprise test-environment specification and import path covering:
  - users
  - groups
  - memberships
  - managers
  - source owners
  - ACL managers
  - executive override roles
- Define a governed ACL input artifact format for onboarding, such as one or more text/CSV/TSV seed files that can be handed to the implementation team as the enterprise mapping pack:
  - users file
  - groups file
  - user-to-group membership file
  - source inventory file
  - source-to-group ACL mapping file
  - source owner / approver / ACL manager file
- Seed a complete set of representative test identities:
  - admin
  - standard requester
  - restricted requester
  - legal approver
  - finance approver
  - requester manager
  - ACL/governance observer
  - executive roles including `CEO` and `CFO`
  - blocked / misuse-test user reserved for later milestones
- Seed representative enterprise groups such as:
  - public users
  - legal
  - finance
  - HR
  - executive access
  - contract reviewers
  - compliance observers
- Seed a representative source inventory with:
  - open/public sources
  - protected but non-sensitive sources
  - protected and intrinsically sensitive sources
  - ambiguous/reroute-test sources
- Require every protected source in the test pack to carry:
  - sensitivity label
  - source owner
  - ACL manager
  - corpus/source-type classification
  - explicit group ACL mapping
- Define upload-time ACL mapping behavior for the seeded environment:
  - uploader identity can contribute default ownership metadata
  - corpus/source classification can determine candidate ACL templates
  - group mapping can be attached during upload or post-upload admin review
  - manager/superior visibility can be derived from the seeded enterprise hierarchy where appropriate
- Define executive access behavior:
  - `CEO` and `CFO` test roles exist in the seed pack
  - executive roles can be modeled as broad cross-functional access groups where intended by policy
  - executive access remains explicit and auditable, not implicit “see everything” magic outside the ACL model
- Add a ready-made test matrix that exercises:
  - open retrieval
  - denied retrieval
  - direct group-based access
  - time-bound direct grants
  - wrong-approver reroute
  - sensitive-answer hold
  - non-sensitive protected retrieval
  - executive cross-functional access

**DoD**
- The repo has a documented, reusable enterprise seed-pack specification rather than ad hoc local test setup
- Test users, groups, memberships, and source ACL mappings are complete enough to exercise the major security and workflow paths end to end
- Protected files are not relying on sensitivity labels alone; explicit ACL mappings exist in the seed design
- `CEO` and `CFO` roles are present in the seed design and behave through explicit policy/group mapping
- Upload-time mapping rules are documented clearly enough for onboarding and implementation teams to apply consistently
- The seeded environment is sufficient to test M4, M15, M16.1, M17, and later abuse-control milestones without inventing identities or ACL mappings from scratch each session

**Re-run checks**
- seeded-user access matrix pass across open, protected, and executive-access sources
- ACL leak regression pack still passes under the seeded environment
- access-request and reroute workflow pass using seeded users and owners
- sensitive-answer hold pass using seeded sensitive sources
- upload-to-ACL classification sanity pass for representative uploader/group scenarios

---

### Milestone M18 — Query Transformation Layer (Gate 18)
**Why now:** only after traces, rerank policy, and eval controls exist.

**Deliverables**
- Optional query transformation stack:
  - rewrite
  - expansion
  - HyDE
- All disabled by default initially
- Transformation decisions recorded in trace/report metadata
- Eval packs added for transform-sensitive queries

**DoD**
- Query transformation is operator-controlled and measurable
- No transform is forced on all traffic by default

**Re-run checks**
- transform-on vs transform-off eval comparison

---

### Milestone M19 — Semantic Cache (Gate 19)
**Deliverables**
- Semantic cache design and implementation:
  - similarity threshold
  - TTL / LRU cleanup
  - invalidation on reindex/re-enrichment
  - corpus-aware scope
- Admin visibility into cache health and usage

**DoD**
- Cache is optional and safe by default
- Invalidation behavior is documented and test-covered
- Latency savings are measurable

**Re-run checks**
- cache hit/miss benchmark
- invalidation regression checks

---

### Milestone M20 — Retrieval Eval Ops And Real User Query Mining (Gate 20)
**Deliverables**
- Real user query capture pipeline:
  - failed queries
  - retries
  - mode-switches
  - feedback outcomes
- Clustering + annotation flow for retrieval improvement
- Drift tracking and acceptance metrics
- Retrieval benchmark packs derived from real usage

**DoD**
- Retrieval improvement work is driven by real query evidence, not anecdote
- Admins can inspect failure clusters and acceptance trends
- Eval packs become a release gate for retrieval changes

**Re-run checks**
- offline eval on real-query-derived benchmark set
- latency/quality trend report

---

### Milestone M21 — Access Request Misuse Controls, User Blocking, And Governance Escalation (Gate 21)
**Why now:** only after access-request workflows, audit trails, and real user query mining exist; misuse controls should be evidence-driven rather than prematurely hard-coded.

**Deliverables**
- Add misuse heuristics for access-request workflows:
  - repeated near-identical requests
  - repeated approver swapping for the same or similar question
  - high-volume access probing across unrelated approvers or domains
  - repeated denied requests followed by re-submission without meaningful new context
- Add operator-visible risk signals in admin UI:
  - suspicious request badges
  - requester-level misuse history
  - same-question repeated-routing history
  - approver-bounce patterns
- Add governed response controls for admins:
  - warn-only
  - require extra review before future access requests
  - temporarily block new access requests
  - temporarily block user query submission in severe cases
  - unblock / restore access with reason
- Require full audit trail for:
  - risk flag creation
  - admin warning
  - request restriction
  - user block / unblock
  - escalation notes and reviewer identity
- Preserve clear operator distinction between:
  - honest routing mistake
  - ambiguous request needing more context
  - probable misuse / fishing behavior

**DoD**
- Suspicious repeated access-routing behavior is visible to admins with supporting history
- Admins can restrict or block abusive access-request behavior through governed controls
- Blocking and restriction actions are auditable and reversible
- Honest single-instance mistakes do not automatically trigger punitive controls

**Re-run checks**
- repeated-request flagging regression checks
- repeated-approver-swap misuse detection checks
- admin block / unblock audit trail checks
- false-positive sanity checks on legitimate multi-step request workflows

---

## 4) Definition of Done (global)

A milestone is “done” only if:
1. It includes tests/evals to prove nothing regressed.
2. It produces an artifact (report/log/UI capability) that an operator can use.
3. It updates `STATUS.md` and adds a short note in `docs/milestones/` describing the change.
4. It has a rollback story (config or git tag).
5. Retrieval-related changes include an observable trace and a measurable before/after comparison.

---

## 5) “How to start” (your first 48 hours)

1. Complete M0 baseline stability and tag it.
2. Do M1 profiles + retrieval controls and produce one comparison report.
3. Do M2 retrieval observability before making retrieval logic “smarter.”
4. Only then begin M3/M4 (SSO + ACL trimming).
5. Keep UI work (M10 through M10.1.x) after security and control-plane gates.

---

## 6) Risks and mitigation (brutal)

- **ACL leakage risk:** must be enforced inside retrieval queries; add leak tests early.
- **Schema drift risk:** change metadata contracts carefully; document them; rerun evals.
- **Retrieval tuning placebo risk:** without traces and eval packs, “improvements” are guesswork.
- **Overbuilding UI early risk:** UI hides core correctness problems; don’t do it first.
- **Tool actions risk:** never allow tools before auth+ACL+audit+approval policy exists.
- **Eval debt risk:** without benchmark packs and real query mining, tuning will drift into anecdote.
- **Cache invalidation risk:** semantic cache without freshness rules can silently lower trust.

---

## 7) End state (what you can honestly pitch)

An internal assistant that:
- answers from approved sources with citations
- respects SSO and per-document permissions
- supports multiple corpora and data connectors, including enterprise email realities
- lets admins inspect, test, compare, roll out, and audit models, fusion, rerankers, LLMs, and retrieval policies through governed workflows
- provides latency, trace, and eval visibility for operators
- supports tool actions with policy gates and approvals
- collects feedback and improves over time without breaking governance
