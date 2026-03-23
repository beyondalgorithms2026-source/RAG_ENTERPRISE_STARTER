# Enterprise RAG Starter — Milestone Project Plan (from stable baseline)

**Objective (one sentence)**  
Build an enterprise-usable RAG system based on `RAG_MM_MASTER_POC` that supports SSO + ACL security trimming, multi-source ingestion (including cloud DB), configurable models (embeddings/rerankers/LLMs), end-user chat UI + admin console, tool actions with approvals, feedback loops, and per-corpus indexing policies—without breaking baseline correctness.

**Core philosophy**
- Retrieval + governance are the hard parts.
- LLM is last-mile generation.
- Every milestone must preserve: correctness, citation provenance, and security boundaries.

---

## 0) What this system DOES

### End-user capabilities
- “Claude-like” chat UI
- Answers grounded in your org’s sources with citations
- Fast/Slow toggle
- Feedback loop (helpful/not, missing source prompts)

### Admin capabilities
- Corpus management (create, enable/disable, sensitivity labels)
- Run indexing/reindexing and connectors
- Configure profiles (embedding model / reranker / LLM)
- Run eval packs; compare reports
- Human approval queue for sensitive responses/actions
- Audit logs (who asked what, what was retrieved, what was answered)

### Engineering capabilities
- Pluggable ingestion connectors (uploads + DB; later drive/slack/email)
- Pluggable retrieval policies per corpus (legal vs transcripts)
- Observability (latency/cost traces, errors)
- Regression testing (eval pack as a gate)

---

## 1) What this system does NOT do (explicit non-goals initially)

These are intentionally out of scope until later (or ever):
- Multi-tenant SaaS platform (workspaces/quotas/billing)
- Full async distributed ingestion pipeline (we may add async jobs, but not a Kubernetes-grade pipeline)
- Full “data residency / sovereign” guarantees (depends on deployment)
- Perfect answers / “no hallucinations” claims
- Real-time transactional truth for ERP/CRM without explicit tool integration

---

## 2) Underlying architecture (high level)

Two planes:

### Ingestion Plane (build + refresh knowledge)
- Source connectors → parsing/adapters → chunking → embeddings → index storage → optional enrichment

### Query Plane (serve answers safely)
- Auth/SSO → policy/ACL trimming → retrieval (keyword/vector/hybrid) → rerank (optional) → answer generation → citations + logging → feedback/approval workflows

Key design rule:
> Security trimming must happen inside retrieval (DB query/filter), not just in UI.

---

## 3) Milestones (ordered to minimize rework)

### Milestone M0 — Baseline stable import (Gate 0)
**Goal:** replicate baseline upload→search→ask→eval in the new repo.

**DoD**
- `/upload`, `/search`, `/ask` work (mode `hybrid`)
- citations included in `/ask`
- eval harness runs + produces reports
- git tag: `baseline-import-stable`

**Re-run checks**
- baseline smoke tests
- at least one eval pack run

---

### Milestone M1 — Component “Profiles” (Gate 1: configurability without UI)
**Why now:** if you don’t do this early, model swaps become invasive refactors.

**Deliverables**
- `EmbeddingProfile` registry (name, model, dimension, batch settings)
- `RerankerProfile` registry (name, top_n, score threshold)
- `LLMProfile` registry (provider/model, max tokens, temperature, timeout)
- `EvalPack` registry (dataset name → questions + expected cues + corpus scope)
- Backend endpoints (admin-protected later):
  - `GET /admin/profiles`
  - `POST /admin/profiles/active`

**DoD**
- Switch embedding model by config and re-index successfully
- Switch reranker on/off by config and see report deltas
- Switch LLM model by config without breaking answer contract
- Eval reports stored with active profile metadata

**Re-run checks**
- baseline eval pack (A vs B compare)

---

### Milestone M2 — Identity + SSO auth (Gate 2: no anonymous access)
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

### Milestone M3 — Authorization + ACL security trimming (Gate 3: no data leakage)
**Deliverables**
- Data model:
  - users, groups, memberships
  - `document_acl` mapping (doc_id → group list)
  - corpus sensitivity label (public/internal/confidential)
- Retrieval filters enforce ACL at query time (SQL-level)
- “Citations list” is also trimmed (no leaked doc ids)

**DoD**
- Two test users with different groups get different retrieval results
- Forbidden content cannot appear in retrieved chunks nor citations
- Audit log records: user, groups, corpus, doc ids accessed

**Re-run checks**
- add ACL-specific eval pack (“leak tests”)

---

### Milestone M4 — Admin API surface (Gate 4: control plane basics)
**Deliverables**
- Admin-only endpoints:
  - corpora create/update/list
  - reindex trigger
  - profile switch
  - eval run trigger + report listing
  - retrieval trace for a query (debug)
- Basic job status surface (even if sync initially)

**DoD**
- Admin can reindex and run eval without code changes
- Reports visible + comparable

---

### Milestone M5 — End-user Chat UI (Gate 5: usable UX)
**Deliverables**
- Next.js (or similar) “Claude-like” UI:
  - SSO login flow
  - chat history (session-level)
  - citations panel (source + page/locator)
  - fast/slow toggle (wires into query policy)
  - feedback buttons (helpful/not)

**DoD**
- Users can chat and see citations reliably
- Feedback captured per Q/A

---

### Milestone M6 — Admin Console UI (Gate 6: non-dev operations)
**Deliverables**
- Admin UI pages:
  - corpora management
  - ingestion/indexing jobs
  - profile selection (embeddings/reranker/LLM)
  - eval packs + compare reports
  - approval inbox (stub until M9)
  - audit log viewer (basic)

**DoD**
- Non-developer can operate: reindex, switch profile, run eval, review logs

---

### Milestone M7 — Cloud DB ingestion connector (Gate 7: multi-source)
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

### Milestone M8 — Tool actions (email/slack/calendar/report) with policy gate (Gate 8)
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

### Milestone M9 — Human approval workflow for sensitive outputs/actions (Gate 9)
**Deliverables**
- Sensitive detection policy (rules-based first):
  - salary, compensation, personal identifiers, secrets
  - corpus sensitivity label influences behavior
- Approval queue:
  - pending approvals stored
  - approver can approve/deny with reason
- End-user sees: “pending approval” vs “denied” vs “approved answer”

**DoD**
- Sensitive query triggers approval path
- Nothing sensitive is released without approval
- Full audit trail exists

---

### Milestone M10 — Fallback + feedback loop (Gate 10)
**Deliverables**
- “No evidence found” behavior:
  - explicitly state insufficient evidence
  - ask user where the info should exist
  - capture suggested source link/upload request
- Feedback loop:
  - store successful/failed queries
  - “top failed queries” dashboard in admin UI

**DoD**
- Missing-evidence queries do not hallucinate
- Feedback captured and visible

---

### Milestone M11 — Fast vs Slow mode (Gate 11)
**Deliverables**
- Fast policy:
  - smaller k
  - no rerank
  - smaller/cheaper LLM
- Slow policy:
  - bigger k
  - rerank on
  - optional query rewrite + deep lookup
- Latency + cost metrics stored per request

**DoD**
- Slow improves hard questions measurably (eval deltas)
- User can choose mode; system can also auto-suggest mode

---

### Milestone M12 — Per-corpus indexing policies (Gate 12)
**Deliverables**
- Corpus policies:
  - Legal: keyword+hybrid default, heading chunking, smaller chunks, strict citations
  - Transcripts: semantic-first, overlap windows, speaker/time metadata
  - DB rows: structured metadata filters
- Parser routing by file type (pdf/docx/pptx/xlsx/eml/txt/md) and corpus policy

**DoD**
- Different corpora behave differently by policy
- Policies are explicit and test-covered

---

## 4) Definition of Done (global)

A milestone is “done” only if:
1. It includes tests/evals to prove nothing regressed.
2. It produces an artifact (report/log/UI capability) that an operator can use.
3. It updates `STATUS.md` and adds a short note in `docs/` describing the change.
4. It has a rollback story (config or git tag).

---

## 5) “How to start” (your first 48 hours)

1. Complete M0 baseline stability and tag it.
2. Do M1 profiles (configurable models) and produce one comparison report.
3. Only then begin M2/M3 (SSO + ACL trimming).
4. Keep UI work (M5/M6) after security gates.

---

## 6) Risks and mitigation (brutal)

- **ACL leakage risk:** must be enforced inside retrieval queries; add “leak tests” early.
- **Schema drift risk:** change metadata contracts carefully; document it; rerun evals.
- **Overbuilding UI early risk:** UI hides core correctness problems; don’t do it first.
- **Tool actions risk:** never allow tools before auth+ACL+audit+approval policy exists.
- **Eval debt risk:** without eval packs, “improvements” are placebo. Treat eval as a gate.

---

## 7) End state (what you can honestly pitch)

An internal assistant that:
- answers from approved sources with citations
- respects SSO and per-document permissions
- supports multiple corpora and data connectors
- lets admins tune models/rerankers and run eval packs
- supports tool actions with policy gates and approvals
- collects feedback and improves over time without breaking governance
