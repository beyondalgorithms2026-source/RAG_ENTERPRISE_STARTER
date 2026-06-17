# Enterprise RAG Starter — Independent Non-Security Product Audit

> **Reference note:** This document captures the independent non-security product audit performed on 2026-06-11 for future reference. It should be treated as an audit baseline for the follow-up remediation milestone plan (`docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md`). It is not a marketing document. Findings are preserved as delivered, including critical ones.

**Date:** 2026-06-11 · **Branch:** `RAG_Enterprise_Dev` @ `54feb95` (M33) · **Method:** code tracing of all major runtime paths, full test-suite execution against the live dev database, fixture and documentation inspection. Security posture is described only as product architecture, per the audit's security exclusion.

---

## 1. Executive Summary

This repository is substantially more real than a typical RAG demo and substantially less verified than its own documentation implies. The retrieval engine, citation discipline, access-trimmed SQL retrieval, admin control plane (~80 endpoints), trace observability, and governed tuning/cache workflows are genuine, integrated implementations — not stubs. The codebase honestly self-reports placeholders (MMR, password auth) and verification debt, which is rare and commendable.

The headline findings:

1. **The verification debt is real and worse than claimed.** Running the full suite produced **222 tests: 158 passed, 7 failures, 57 errors**. 55 of the 57 errors share one root cause: the live dev DB's `chunks.embedding` column is `vector(768)` (a promoted `bge-base` profile) while the test harness hardcodes 384-dim synthetic vectors (`backend/tests/smoke_test_base.py:348`). The regression suite cannot currently regression-test the system.
2. **The flagship governance story is undermined by its own dev environment.** The profile registry contains factually wrong metadata (`BAAI/bge-small-en-v1.5` registered with dimension 768 — it is 384), the active retrieval profile is a sandbox draft (`draft-645-retrieval`), and the migration ledger disagrees with the schema (MIG-P012 recorded vs. MIG-P020 expected). The "embedding safety" promotion workflow (M17.b.3) did not prevent exactly the incoherence it exists to prevent.
3. **Several differentiating features are scaffolding wearing governance clothing.** Query transformation ("rewrite/expansion/HyDE") is a 5-entry hardcoded synonym dictionary plus a prefix string — no LLM is involved (`backend/app/core_rag/query_transform.py:9-43`). The "semantic" cache is exact-string-match, not semantic. MMR is an explicit placeholder. Eval packs contain 2–7 cases each.
4. **What is genuinely strong** is the *integration*: trace-everything observability, citation provenance enforcement, SQL-level access trimming threaded through every retrieval path including supplemental scans, and reversible, auditable configuration change — these compose into a coherent "governed retrieval" architecture that generic RAG stacks do not have.

**Verdict in one line:** a strong, honest PoC-to-starter with an unusually good governance skeleton, currently blocked from "credible enterprise starter" status by a broken regression gate, thin evaluation data, and several differentiation claims that are interfaces rather than capabilities.

---

## 2. Intended Product and Value Proposition

From `CONTEXT.md`, `README.md`, and the 1,800-line milestone plan (`docs/02_Enterprise_RAG_Project_Plan_Milestones.md`):

- **Product:** a reusable internal-assistant foundation ("Enterprise RAG Starter") that teams fork and reshape into one of four deployment scenarios (no-auth research, employee-wide, corpus-level ACL, full OIDC + document ACL + governance).
- **Thesis:** *retrieval + governance are the hard parts; the LLM is last-mile generation.* Every retrieval change must be "measurable, reversible, and explainable."
- **Value proposition:** not better answers per se, but **operable, auditable, access-trimmed grounded answering** — admin-governed tuning instead of config-file archaeology, citations that cannot be fabricated, and scenario packaging so a team adopts a subset rather than the whole.

This is a coherent and defensible positioning. It deliberately avoids competing on retrieval algorithms and competes on the operational envelope around retrieval.

---

## 3. Current System: How It Actually Works (from code)

**Ingestion plane.** Uploads (`pdf/docx/pptx/xlsx/eml/txt/md`, per-type adapters under `backend/app/adapters/`) are hashed, persisted, and queued. A **single in-process daemon thread** (`backend/app/ingestion/queue_runtime.py:22-51`) claims jobs from a DB-backed queue, parses, sanitizes (NUL stripping, prompt-injection signal logging), chunks via word-window chunking parameterized by **corpus policy** (`backend/app/corpus_policies.py:36-73` — five hardcoded policies: default/legal/transcripts/db_rows/email_casework), embeds with sentence-transformers, and optionally runs **regex-heuristic** graph/temporal enrichment (`backend/app/graph/extractor.py` — capitalization patterns, not NLP or LLM extraction). Email ingestion parses `.eml` files and recursively ingests attachments as child sources; the DB connector (`backend/app/connectors/db.py`) does incremental row sync from Postgres/MySQL with row-to-document serialization. There is **no live mailbox connector** (IMAP/Graph) — "enterprise email ingestion" means `.eml` upload.

**Query plane.** `/ask` (`backend/app/api/ask.py:25`) → governance restriction check → LLM preflight → `perform_ask` (`backend/app/core_rag/answering.py:774`):

1. **Cache check** — governed cache policies (M33): exact normalized-question key, scoped to corpus/group/question lists, validated against ACL fingerprints, profile revision, and version namespaces; user-refreshable with material-change detection (`answering.py:899-932`).
2. **Query transform** — heuristic only (see §12).
3. **Routing** — `backend/app/core_rag/query_router.py:197-361`: regex/keyword signals (quotes, identifiers, dates, relationship phrases) select keyword/hybrid/graph_hybrid/full, with artifact-readiness checks and explicit fallback reasons. Every decision is traced.
4. **Retrieval** — `backend/app/core_rag/retrieval.py:968`: vector (pgvector cosine), keyword (Postgres FTS with `websearch_to_tsquery` → `plainto_tsquery` → OR-anchor soft fallback), hybrid fusion (linear α or RRF), anchor-term co-occurrence boosts, optional deep-research path (wider candidates, rare-anchor window scan, neighbor expansion). **Access trimming is injected as SQL into every retrieval query** — including the soft-keyword fallback and `fetch_chunks_by_ids` (`backend/app/db/repo_search.py:159,295,352`) — via a strategy abstraction supporting `none / employee_all / corpus_level / document_acl / document_acl_with_time_bound_grants` (`backend/app/auth/access_strategy.py:106-141`).
5. **Rerank** — cross-encoder, gated by a real policy evaluator (modes, corpora, candidate count bounds, latency budget) with traced eligibility reasons (`backend/app/core_rag/reranker.py:23-86`). MMR is a no-op placeholder.
6. **Generation** — Ollama-only client (local or Ollama-cloud) (`backend/app/llm/client.py:88`), strict-JSON contract with fenced/balanced-JSON tolerant parsing, a repair pass, and a second-pass answer regeneration when quality heuristics fail.
7. **Citation enforcement** — model-claimed citations are whitelisted against actual context blocks; inline fake `[Sn]` tokens are stripped; an answer with zero valid citations is forced to "Not found in provided sources," which also auto-records a `missing_evidence` feedback event (`answering.py:667-719`).
8. **Persistence** — full retrieval trace + answer path + latency stages into `retrieval_traces`; query event into mining tables; structured feedback taxonomy from the UI.

**Admin plane.** ~80 endpoints in `backend/app/api/admin.py`: corpora/sources/ACL/seeds, job queue with priority governance, profile CRUD + activation, tuning drafts → sandbox compare → promotion → rollback → warm-up, semantic-cache policy lifecycle (create/check/activate/disable/rollback/metrics/clear), query mining + derived eval packs, eval run/report, traces, audit log with export and integrity check, governance restrictions. Admin modules are feature-flag-gated per scenario (`backend/app/auth/admin_modules.py`, `scenarios/*/admin_modules.json`).

**Frontend.** A substantive Next.js console (~25 routes): chat with citation context viewer, deep-research toggle, approval polling, structured negative feedback (taxonomy includes "citation does not support answer"), uploads, sources, history, access requests; admin dashboards for all the above (`web/components/chat-workspace.tsx`, `web/components/admin-panels.tsx` — ~4,500 lines combined). A legacy static UI remains mounted at `/frontend`.

---

## 4. Architecture and Major Runtime Flows

The two-plane architecture in the docs matches the code. Notable structural properties:

- **Layering is clean at the retrieval boundary**: API → `core_rag` → `db/repo_*` → SQL; profiles resolved through a 5-second-TTL cached resolver (`backend/app/profiles/resolver.py:13`) so admin changes propagate without restart.
- **Cross-cutting trace object** is built once per request and enriched by every stage — router, fusion, rerank policy, ACL context, cache decision — then persisted and joined to the answer path. This is the system's best architectural idea.
- **Fragile spots:** sandbox compare works by **monkeypatching module-level resolver functions** with temporary lambdas (`backend/app/tuning/sandbox_compare.py:28-76`) — correct in a single-threaded request but unsafe under concurrency (a concurrent live request during a sandbox run would see candidate profiles). The ingestion worker, rate limiter, and model caches are all single-process state; multi-worker deployment silently breaks them (the rate-limit comment acknowledges this).
- **Startup** runs migrations and security-posture validation (`backend/app/main.py:144-148`), which is good operability — but also means the test/dev DB drift found below implies the backend hasn't been booted against this DB since the latest schema steps were renumbered.

---

## 5. Objective-to-Implementation Traceability Matrix

| Intended capability | Status | Evidence |
|---|---|---|
| Multi-source ingestion (uploads, DB, email) | **Partially implemented** | 7 file adapters + attachments verified; DB connector real (`connectors/db.py:262`); email = `.eml` parsing only, no live mailbox sync |
| Corpus-specific parsing/chunking/indexing policies | **Partially implemented** | 5 hardcoded policies (`corpus_policies.py:36`); affect chunk sizing, default mode, metadata; not admin-editable; "parser_route" names mostly label standard adapter paths |
| Hybrid + configurable retrieval | **Implemented and verified** | Linear + RRF fusion (`retrieval.py:218-298`), profile-driven candidates/alpha; exercised by passing baseline tests and fixtures |
| Query routing | **Implemented and verified** | Heuristic router with fallback reasons (`query_router.py`); router fixture cases exist; router tests currently error on env, not logic |
| Query transformation (rewrite/expansion/HyDE) | **Placeholder behind real governance** | `query_transform.py:9-43`: static 5-token synonym dict; "rewrite" = whitespace normalization; "HyDE" = literal prefix string, no LLM |
| Reranking + policy gating | **Implemented, insufficiently verified** | Real cross-encoder + policy evaluator; rerank disabled in default env; no eval evidence that reranking improves quality |
| MMR / diversity | **Planned, explicit placeholder** | `apply_mmr_placeholder`, reason `placeholder_reserved_for_future_milestone` (`reranker.py:89-95`) |
| Graph / temporal retrieval | **Partially implemented** | Regex entity/relation extraction; artifact versioning + freshness checks are solid; retrieval value of the graph signal is unmeasured |
| Grounded answers + citation provenance | **Implemented and verified** | Citation whitelist, fake-citation stripping, forced not-found, second-pass repair (`answering.py:208-265,667-719`); strongest subsystem |
| No-evidence behavior | **Implemented** | `not_found` path + clarification contract + automatic `missing_evidence` feedback (`answering.py:564-590`) |
| Retrieval traces / observability | **Implemented and verified** | 423 traces in dev DB; per-stage latency; admin trace inspection endpoints |
| Eval packs + regression gates | **Implemented but inadequate** | Harnesses real (retrieval/enriched/compare/ACL-leak), but fixtures total ~28 cases across 7 files; no CI; suite currently red |
| Admin profiles + model registry | **Implemented; data-integrity bug observed** | Registry rows carry wrong dimension metadata (bge-small marked 768) — live DB inspection |
| Governed tuning: sandbox/promote/rollback | **Implemented, insufficiently verified** | Full draft→compare→promote→rollback→warmup chain (`repo_tuning_configs.py`); concurrency-unsafe compare; the dev env itself ended up incoherent |
| Governed semantic cache | **Implemented, misnamed** | Exact-match only; policy scoping, revision bumps on grant changes (`access_strategy.py:254-264`), user refresh with change detection — genuinely thoughtful, but not semantic |
| Chat + evidence inspection UX | **Implemented** | Citation context viewer, retrieval-path surfacing, approval status polling |
| Feedback + approval workflows | **Implemented** | Structured negative taxonomy, sensitive-answer approval gating (`answering.py:376-401`), access requests with routed approval and time-bound grants |
| Scenario reuse packs | **Implemented (docs+env+flags)** | `scenarios/` ×4 with env files, module flags, validation checklists; static tests pass |

---

## 6. Current Strengths

1. **Citation provenance is enforced, not requested.** The model cannot mint a citation that reaches the user; zero-valid-citation answers are converted to not-found. This is implemented twice (ask + compare) and is the system's clearest correctness invariant.
2. **Access trimming is genuinely inside retrieval SQL**, uniformly, including fallback and by-id paths, behind a swappable strategy enum. As an architectural boundary (per the audit's security exclusion, described only as such), it is the right design and consistently applied.
3. **Explainability-first retrieval.** Every mode decision, fusion score component, rerank eligibility verdict, fallback, and cache decision carries a machine-readable reason and lands in a persisted trace. An operator can answer "why did this query do that?" — the milestone plan's stated goal — and the code delivers it.
4. **Reversible configuration as a first-class workflow**: drafts, side-by-side compare, promotion events, rollback, model warm-up records, approved-model registry. The shape of the governance loop is complete.
5. **Failure-path engineering in generation**: tolerant JSON extraction (fenced/balanced-object scanning), repair prompt, second-pass regeneration with quality heuristics, deterministic prompt-only JSON mode for GPT-OSS. This is unglamorous work most starters skip.
6. **Honest self-labeling.** Placeholders are named placeholders; STATUS.md lists verification debt; scenario docs state "reserved until implemented" for password auth. Documentation accuracy is unusually high (with exceptions noted in §12).
7. **Operational data already accumulating**: 307 sources, 1,720 chunks, 423 traces, 176 query events, 101 feedback rows in the dev DB — the raw material for the query-mining → eval-pack loop exists.

---

## 7. Current Weaknesses

1. **The regression gate is broken** — 64/222 tests red. The single dominant cause (embedding-dimension drift between the promoted live profile and the harness's hardcoded 384-dim vectors) means the suite is **environment-coupled**: it tests "the dev DB as currently tuned" rather than "the system." A regression gate that fails when an admin legitimately promotes a profile is not a gate.
2. **Governance didn't protect its own environment.** Wrong dimension metadata in the registry, an active retrieval profile named `draft-645-retrieval`, and a migration ledger 8 steps behind the code's plan are precisely the states M17.b.3/M31 claim to prevent. The workflows exist; their invariants are not enforced by the system (no validation that registry dimension matches the actual model, no guard against activating a draft-named profile as live, no startup assertion that ledger == plan).
3. **Evaluation is structurally thin.** ~28 fixture cases; pass criteria are keyword/heading containment; no graded relevance, no recall/MRR/nDCG, no answer-faithfulness scoring, no statistical comparison. The promotion workflow therefore promotes on *one question's* side-by-side output plus operator judgment — "measurable" is aspirational.
4. **Single-process runtime ceiling**: threaded ingestion worker, in-memory rate limiting, module-global model singletons, monkeypatch-based sandbox. Any multi-worker/multi-node deployment breaks correctness assumptions silently.
5. **Provider lock-in to Ollama.** The LLM client supports exactly `ollama` and `ollama_cloud`. No OpenAI-compatible generic endpoint abstraction, no Anthropic/Azure/Bedrock path — limiting for an "enterprise starter" whose buyers mostly have a sanctioned cloud model.
6. **Score-fusion arithmetic is ad hoc.** Anchor boosts, graph boosts, temporal boosts, window candidates, and neighbor bonuses are additive magic constants (0.18, 0.24, 0.35, 0.05…) layered on top of normalized fusion scores (`retrieval.py:181-215,326-431`). Some constants encode test-specific vocabulary — `causal_terms = {"because", "challenging", "dominated", …}` (`retrieval.py:649`) is overfit to a particular demo corpus. Without eval coverage, these are unfalsifiable.
7. **Two frontends are maintained**; the legacy `frontend/` is still mounted and tested (M3 OIDC redirect test failed against it), a standing source of drift.

---

## 8. Implementation and Verification Gaps

Classified per the audit protocol:

- **Implemented and verified** (passing tests + code): baseline upload→chunk→embed→search, hybrid fusion, citation discipline, routing logic, ACL-strategy static checks, scenario/doc hygiene suites (M27–M32 tests all pass), GPT-OSS JSON tolerance (`backend/tests/test_gpt_oss_json_compatibility.py`).
- **Implemented but insufficiently verified**: everything DB-backed from M17.b.3 onward — tuning promotion/rollback, query mining, governance restrictions, retention, cache policies. STATUS.md admits M20–M30 rerun debt; the audit run confirms the debt and adds that **even M2–M19 paths now error** under the current env. Notable specific failures beyond the dimension cascade: `create_access_request()` caller/signature drift (a *contract* break, not env), `KeyError: 'query_transform_enabled'` (profile config rows predating M18 keys are read without defaulting somewhere), a `SELECT DISTINCT/ORDER BY` SQL error in one repo function, and a stale test referencing `app.api.ask._perform_ask_internal` after the M33 refactor moved it to `answering`.
- **Documentation/configuration only**: password auth mode, MMR, per-corpus *editable* policies (admin can label corpora but policy parameters are code constants), "field-weighted keyword indexing" (single `search_tsv`, no field weights).
- **Planned but not implemented**: real LLM query rewriting/HyDE, similarity-threshold cache matching (the `semantic_cache_similarity_threshold` profile field exists and is unused by lookup), multi-step/agentic retrieval.
- **Unclear due to insufficient evidence**: whether graph/temporal boosts ever improve outcomes (no eval case isolates them); reranker quality impact; deep-research recall gains.

---

## 9. Product and User-Experience Gaps

- **Operator cannot see that the system is incoherent.** There is no health surface that says "active embedding profile ≠ index dimension," "active retrieval profile is an unpromoted draft," or "migration ledger behind plan." The admin console shows what is configured, not whether the configuration is *self-consistent* — the exact failure mode the dev DB exhibits.
- **Eval is not in the operator's promotion path.** Sandbox compare shows one question; nothing forces or even offers "run the eval pack against the candidate" before promotion, despite both subsystems existing. This is the single biggest missed integration in the product.
- **Chunk-level citations, document-level grants.** Access requests grant whole sources; there is no sensitivity below document granularity — fine for now, worth stating as a product boundary.
- **No conversational memory**: each ask is independent; threads are a UI grouping (client-side localStorage), not server-side context. "Claude-like chat" overstates this.
- **Knowledge freshness is manual**: re-ingest/re-enrich are operator actions; connectors have no scheduling; there's no staleness surfacing on sources.
- **Cost is invisible**: no token counting, no per-request model cost, no budget views — only latency. The plan's "latency/cost traces" is half-delivered.
- **Onboarding is good but Mac-specific**: docs use absolute `/Users/Work/...` paths; docker-compose hardcodes a personal backup volume path (`docker-compose.yml`) — a fork blocker for any other machine.

---

## 10. Differentiation From Generic RAG Systems

**(1) Commonly available elsewhere:** hybrid search with RRF, cross-encoder reranking, citation rendering, chunking per document type, basic eval harnesses, traces. Any LlamaIndex/LangChain/Haystack assembly reaches parity in days.

**(2) Uncommon but reproducible:** heuristic query router with traced fallback reasons; rerank *policy* gating (corpus/mode/latency-budget eligibility rather than on/off); deep-research rare-anchor window scan; answer second-pass repair contract; not-found auto-feedback.

**(3) Integrated implementations that create meaningful differentiation today:**
- **Access-strategy-parameterized retrieval SQL** threaded through every candidate source path, with grant changes bumping cache revisions — the cache, ACL, and retrieval layers actually know about each other.
- **End-to-end decision provenance**: one trace object spanning route → transform → fusion → rerank policy → answer path → cache decision, persisted and inspectable in the console.
- **The governed change loop as a product surface**: drafts, approved registries, promotion/rollback events, warm-up records, audit log — config change is a *workflow with history*, not an env edit.

**(4) Could become hard to replicate** (not yet realized): the query-mining → derived-eval-pack → regression-gate flywheel (tables and endpoints exist, 176 events captured, but no closed loop); accumulated per-corpus retrieval policies learned from feedback; an institutional library of scenario packs with validated runbooks.

**(5) Claimed but unsubstantiated:** see §12.

**Source of defensibility:** not algorithms (deliberately ordinary) and not any single integration — it is the **co-design of governance workflows, trace provenance, and retrieval**, plus (potentially) accumulated evaluation and feedback data. That is an architecture-and-operations moat, which is real but only materializes if the evaluation loop closes.

---

## 11. Defensibility: What Is Hard to Replicate and Why

1. **The trace/explainability lattice.** Retrofitting "every decision has a persisted reason" into an existing RAG stack touches every module; here it was built in from M2. Hard to copy cheaply because it is pervasive, not a feature.
2. **Coherence between access control, caching, and retrieval.** Grant changes invalidating cache namespaces, ACL fingerprints validating cache hits, trimming inside supplemental scans — the cross-component invariants are the work, and they're easy to get subtly wrong (as this repo's *own tests* demonstrate by failing).
3. **Operational assets, prospectively**: 423 traces, 176 mined queries, 101 structured feedback events in dev already; at enterprise scale this becomes a proprietary eval corpus no framework ships with. **Today this is potential, not moat.**

What is *not* defensible: the retrieval math, the router heuristics, the cache, the UI — all reproducible by a competent team in weeks.

---

## 12. Differentiation Claims Not Yet Proven

| Claim | Reality |
|---|---|
| "Query rewriting/HyDE" (M18, profile flags, sandbox controls, trace fields) | Heuristic stub: 5 hardcoded synonyms, normalization-as-rewrite, prefix-string HyDE. The governance around it (admin controls, traces, promotion) is more code than the feature itself |
| "Semantic cache" | Exact-match cache with governance. `semantic_cache_similarity_threshold` exists in the profile model but no similarity lookup uses it |
| "Retrieval changes are measurable" | Harness exists; datasets (2–7 cases/pack) cannot detect regressions smaller than catastrophic; suite currently cannot run green at all |
| "Reversible/governed promotion prevents unsafe states" | The dev environment reached exactly the unsafe state (dimension drift, draft live, wrong registry metadata) the workflow targets |
| "Per-corpus indexing policies" | Real but five hardcoded dataclasses; "policy" implies operator-configurable, which it isn't |
| "Multi-source ingestion incl. enterprise email" | Email = `.eml` file parsing (good attachment handling), not a mailbox connector |
| "MMR diversity" | Self-admitted placeholder |

---

## 13. Capabilities Worth Incorporating (aligned with the stated objective)

From mature RAG practice, in order of fit:

1. **Retrieval evaluation with real metrics** — graded relevance labels, recall@k / MRR / nDCG, answer faithfulness checks, paired comparison across profiles; gate promotions on eval deltas. This is *the* missing piece that makes "measurable, reversible, explainable" true.
2. **Configuration coherence checks** — startup + admin health endpoint validating: embedding profile dimension == index column dimension == model's actual output; active profiles are promoted (not drafts); migration ledger == plan; reranker model loadable. Turns the governance promise into enforcement.
3. **LLM-backed query transformation behind the existing flags** — the governance shell is already built; put a real rewrite/HyDE call (with the existing timeout budget) inside it. Cheap win because the hard (governed) part exists.
4. **Provider abstraction for generation** — one OpenAI-compatible client interface (covers Ollama, vLLM, Azure, OpenAI) + optional Anthropic. Enterprise adoption blocker otherwise.
5. **Experiment tracking** — persist sandbox compares and eval runs as linked experiment records (tables partially exist via `embedding_experiment_runs`); show history per profile.
6. **Cost/latency governance** — token counts per request into traces; per-profile cost summaries; budget alerts. Extends the existing latency-budget pattern.
7. **Index lifecycle management** — explicit reindex-on-embedding-change orchestration with progress, dual-write or versioned index columns, and a hard block on activating a mismatched embedding profile (today the block exists only inside sandbox compare).
8. **Human feedback → eval flywheel** — the `derived_eval_packs` endpoint exists; close the loop: one-click "convert this thumbs-down cluster into eval cases," then surface pack pass-rate trends.
9. **Connector operations** — scheduling, sync status, failure retry/backoff for DB connectors; staleness badges on sources (knowledge freshness).
10. **Later, if evidence demands:** real MMR, metadata-field-weighted FTS (`setweight` on heading vs body — small change to the tsv trigger), multi-query retrieval fan-out (the transform plumbing already passes variants).

**Avoid importing:** agent frameworks, multi-vector/ColBERT exotica, knowledge-graph expansion beyond current heuristics, multi-tenant SaaS scaffolding — all contradict the starter's focus and the plan's own non-goals.

---

## 14. Recommended Way Forward

**Strategic thesis:** this repo's winning move is to become *the RAG starter where every retrieval change is provably safe* — the governed-tuning loop closed by real evaluation. Everything else (more retrieval features, more connectors) is secondary until the loop closes, because the loop is the differentiation and it is currently open at both ends (thin evals in, unenforced invariants out).

Concretely: (a) make the regression suite environment-independent and green; (b) make configuration incoherence impossible or loudly visible; (c) grow eval packs to meaningful size partly from mined real queries; (d) wire eval results into promotion; (e) replace the transform stub with a real implementation inside the existing governance; (f) then pursue provider abstraction and deployment hardening for pilots.

---

## 15. Prioritized Roadmap

### Immediate (correctness/verification blockers)

**R1 — Restore a green, environment-independent test suite** · **P0 · Effort M**
- *Problem:* 64/222 tests red; harness hardcodes 384-dim vectors; tests depend on live-DB active profiles.
- *Evidence:* test run this audit; `backend/tests/smoke_test_base.py:348`; migration-plan test diff (P012 vs P020).
- *Impact:* no regression protection; every claim of "re-run checks" is currently unexecutable.
- *Change:* tests pin their own profiles (use the existing temporary-profile context managers), derive vector dimension from the active embedding, or run against an isolated schema; fix the 4 genuine contract breaks (`create_access_request` signature, `query_transform_enabled` KeyError, DISTINCT/ORDER BY SQL, stale `_perform_ask_internal` reference); reconcile migration ledger.
- *Acceptance:* `python -m unittest discover` green on a fresh DB **and** on a DB with a 768-dim promoted profile; CI or make target documented in STATUS.md.

**R2 — Configuration coherence validation** · **P0 · Effort S/M** · *Depends: none*
- *Problem:* registry rows with wrong dimensions; draft profile active as live; no system self-check.
- *Evidence:* live DB inspection (bge-small registered as 768; active retrieval = `draft-645-retrieval`).
- *Change:* validate dimension against the loaded model at profile save/activation; forbid activating `draft-*` profiles outside promotion; add `/admin/health/coherence` + console banner.
- *Acceptance:* the three observed incoherent states are each rejected or flagged; smoke test per state.

### Near term (credible enterprise use)

**R3 — Real evaluation packs + promotion gating** · **P0 · Effort L** · *Depends: R1*
- *Problem:* ~28 keyword-containment cases; promotion is judgment-only.
- *Change:* 100+ labeled cases per flagship corpus (seeded from `query_events`), recall@k/MRR + citation-faithfulness metrics, "run eval pack on candidate" inside the tuning lab, promotion records store eval deltas.
- *Acceptance:* a deliberately degraded candidate (α=0, rerank off) fails the gate; eval trend visible in console.

**R4 — LLM provider abstraction** · **P1 · Effort M**
- *Change:* generic OpenAI-compatible client + pluggable provider registry; keep approved-model governance.
- *Acceptance:* swap to a non-Ollama endpoint via profile only; answer contract tests pass unchanged.

**R5 — Real query transformation behind existing flags** · **P1 · Effort M** · *Depends: R3 (to measure it), R4 (helpful)*
- *Acceptance:* rewrite/HyDE produce LLM-generated variants within `transform_timeout_ms`; eval pack shows measured delta; trace records variants (already plumbed).

**R6 — Embedding/index lifecycle** · **P1 · Effort L** · *Depends: R2*
- *Change:* guided reindex flow on embedding change (progress, counts, abort), block mixed-dimension states everywhere (not just sandbox).
- *Acceptance:* end-to-end model swap on a 1k-chunk corpus without manual SQL; suite green before/after.

**R7 — Deployment portability + multi-worker safety** · **P1 · Effort M**
- *Change:* remove machine-specific paths from compose/docs; document single-worker constraint or move queue poke/rate-limit to Postgres; make sandbox compare concurrency-safe (pass profiles explicitly through the call chain instead of monkeypatching resolvers).
- *Acceptance:* fresh-machine quickstart succeeds; concurrent sandbox+live request test shows no profile bleed.

### Medium term (differentiation/defensibility)

**R8 — Feedback→eval flywheel UI** (cluster → derived pack → gate) · **P2 · Effort M** · *Depends: R3*
**R9 — Cost/token accounting in traces + per-profile cost views** · **P2 · Effort S/M**
**R10 — Connector ops: scheduling, sync health, source staleness** · **P2 · Effort M**
**R11 — Field-weighted FTS + real MMR, adopted only with eval-proven gains** · **P2 · Effort S each** · *Depends: R3*
**R12 — Optional similarity-threshold cache tier** (make "semantic" true, reusing embedding + existing safety validation) · **P2 · Effort M**

### Later (premature now)

- Live mailbox/Drive/Slack connectors; multi-step agentic retrieval; conversational memory; structured-data NL2SQL answering; password auth module (or delete the mode from docs).

### Do not pursue

- Multi-tenant SaaS features, Kubernetes-grade async pipelines, exotic retrieval research (ColBERT/learned fusion), building a generic agent framework, more governance surface area before existing governance is enforced (R2) and measured (R3). Each contradicts the plan's own non-goals or adds surface to an unverified core.

---

## 16. Final Verdict

**Demo / PoC / starter / enterprise-ready?** A **strong PoC with genuine starter scaffolding**. It exceeds "demo" decisively (real ACL-in-SQL retrieval, real admin plane, real traces). It misses "enterprise starter" because the regression gate is red, the environment violates its own governance invariants, and a fork currently inherits Mac-specific paths and a single-process runtime.

**Does the implementation deliver the stated objective?** ~70%. "Grounded answers with provenance, access-trimmed retrieval, admin operability, scenario reuse" — delivered. "Measurable, reversible, explainable retrieval change" — explainable yes, reversible yes, **measurable no** (eval data too thin, suite broken).

**Three strongest differentiators:** (1) enforced citation provenance with repair/fallback contract; (2) pervasive decision-provenance tracing from router to cache; (3) the integrated governed-change loop (drafts → compare → promote → rollback → audit) wrapped around retrieval config.

**Genuinely hard to replicate:** the cross-component invariants (ACL ↔ cache ↔ retrieval coherence) and, prospectively, accumulated trace/feedback/eval data. The individual features are not.

**Largest strategic weakness:** the gap between governance *workflow* and governance *enforcement*, proven by the repo's own dev environment — combined with an evaluation layer too weak to make any tuning claim falsifiable. The product's thesis is "safe retrieval change"; today the safety is procedural, not mechanical.

**Missing evidence:** any quantitative proof that the advanced retrieval layers (rerank, graph, temporal, deep research, anchor boosts) improve outcomes; a green full-suite run on a fresh and on a tuned DB; a successful fork-and-deploy by someone other than the author.

**Next 30 days:** R1 + R2 (green env-independent suite; coherence enforcement; fix the four contract breaks; reconcile the migration ledger). **60 days:** R3 (real eval packs mined from the 176 captured queries; eval-gated promotion) + R7 portability fixes. **90 days:** R4 + R5 (provider abstraction; real query transforms measured by the new evals) and begin R6 index lifecycle.

**What it should deliberately avoid becoming:** a generic RAG feature buffet, an agent platform, or a multi-tenant SaaS. Its identity — and only durable moat — is the *governed, explainable, provably-safe retrieval operations layer*. Every new feature should be forced through the question the repo itself poses: can this change be measured, reversed, and explained? Right now the codebase asks that question of its operators; the next phase is making the system able to answer it about itself.
