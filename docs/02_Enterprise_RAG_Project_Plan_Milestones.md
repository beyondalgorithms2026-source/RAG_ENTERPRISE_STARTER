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
- Configure profiles (embedding model / reranker / LLM / retrieval policy)
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

### Milestone M10.1 — Truthful Console IA And Surface Consolidation (Gate 10.1: no misleading UX)
**Why now:** the first console shell exists, but before M11 polish the product surface must stop advertising routes and actions that are redirects, placeholders, or dashboard-only summaries.

**Deliverables**
- Reconcile visible information architecture with what is actually implemented today
- User workspace labels/routes match the real supported surfaces:
  - grounded chat
  - session history
  - source listing + upload flow
  - connector request stub only where explicitly intentional
- Admin workspace labels/routes match real operable surfaces rather than aspirational destinations
- Route map review:
  - no nav destination should silently collapse into an unrelated page unless the label says so
  - remove, rename, merge, or properly implement routes that currently only redirect
- UX contract document for what is intentionally consolidated vs intentionally deferred

**DoD**
- No primary nav item implies standalone functionality that does not exist
- User can predict where each workspace link goes from its label alone
- Admin nav does not advertise pages that are only dashboard redirects
- Route structure is truthful enough that operators do not feel bait-and-switched on first exploration

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
- Resolve the user workspace contract in one truthful direction:
  - either implement distinct search/uploads/connectors views
  - or intentionally consolidate them and rename the IA to match
- Evidence panel minimum interaction contract:
  - citation click behavior
  - source/context drill-in behavior
  - retrieval-path and latency visibility rules
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
  - removed from the surface until backed

**DoD**
- User-facing actions no longer feel decorative or mismatched
- Citation/evidence interactions increase trust instead of acting like static display chrome
- Workspace behavior around history and persistence is predictable to non-technical users
- The console no longer suggests capabilities that disappear into unrelated routes

**Re-run checks**
- authenticated user journey: login → ask → inspect evidence → view history → upload source
- citation/evidence interaction pass
- empty-history and populated-history UX pass

---

### Milestone M10.1.3 — Admin Workspace Route Wiring And Operator Completeness (Gate 10.1.3: routed control plane)
**Why now:** backend admin APIs and even richer frontend panels may already exist, but the product is not operator-complete until routed pages expose them honestly.

**Deliverables**
- Wire the admin sidebar to real, distinct pages for:
  - corpora
  - jobs
  - profiles
  - evals
  - traces
  - policies
- Preserve the dashboard as a summary page instead of using it as a proxy for every workflow
- Expose current backend control-plane capabilities through the routed admin UI where already supported:
  - corpus inspection and management
  - indexing/reindex/job visibility
  - profile selection
  - eval trigger/report review
  - trace inspection
  - retrieval/rerank/corpus policy metadata inspection
- Define any truly future admin surfaces as deferred rather than half-routed

**DoD**
- Every advertised admin destination is a real page, not a redirect back to the dashboard
- Admins can operate current control-plane capabilities from the UI without code edits
- The admin console feels like an operator workspace rather than a pretty summary shell

**Re-run checks**
- admin route smoke across all sidebar destinations
- operator journey: corpus review → profile switch → eval trigger → trace review

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
  - hidden until backed by behavior
- Align `/register`, demo, free-trial, and video-tour flows with the actual product/business motion
- Footer and header navigation either point somewhere real or are intentionally removed

**DoD**
- No primary CTA appears clickable while doing nothing
- Demo and trial flows set the right expectation for enterprise/private-beta reality
- Placeholder actions are intentional and legible rather than feeling broken

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
  - permission-limited visibility
  - failed backend call
- First-run checklist or embedded guidance for local dev operators

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
  - approval inbox (stub until M15)
  - audit log viewer
  - bulk-action and filtering refinement for corpora/jobs/traces
  - report comparison UX polish
  - operational quality-of-life improvements for non-developer operators

**DoD**
- Non-developer can operate daily workflows comfortably with less engineering assistance

---

### Milestone M12 — Cloud DB And Structured Source Connectors (Gate 12: multi-source)
**Deliverables**
- DB connector (read-only):
  - Postgres/MySQL source
  - row-to-document serialization
  - incremental ingestion by updated_at/id
- Metadata filters preserved (customer_id, region, etc.)

**DoD**
- Can ingest DB data into a corpus and query it
- Filters work and are enforced alongside ACL trimming

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

**DoD**
- Missing-evidence queries do not hallucinate
- Feedback captured and visible
- Clarification path has defined backend/product contract even if initially rules-based

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

## 4) Definition of Done (global)

A milestone is “done” only if:
1. It includes tests/evals to prove nothing regressed.
2. It produces an artifact (report/log/UI capability) that an operator can use.
3. It updates `STATUS.md` and adds a short note in `docs/` describing the change.
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
- lets admins tune models, fusion, rerankers, and retrieval policies
- provides latency, trace, and eval visibility for operators
- supports tool actions with policy gates and approvals
- collects feedback and improves over time without breaking governance
