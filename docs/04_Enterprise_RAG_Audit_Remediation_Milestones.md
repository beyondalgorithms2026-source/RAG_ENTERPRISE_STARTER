# Enterprise RAG Starter — Audit Remediation Milestone Plan

**Objective (one sentence)**
Convert the findings of the independent 2026-06-11 product audit into a focused sequence of corrective milestones that make the repo regression-testable, configuration-coherent, evaluation-gated, portable, operator-trustworthy, and credibly closer to an enterprise starter — without adding new product surface before the existing core is verified.

**Source audit**
`docs/03_Enterprise_RAG_Independent_Product_Audit_2026_06_11.md` (audit baseline, 2026-06-11, branch `RAG_Enterprise_Dev` @ `54feb95`). Every milestone below traces to a specific audit finding. If a milestone and the audit disagree, the audit is the source of truth until re-verified.

**Planning principle**
The audit's central conclusion: the product has a strong governance *architecture* (drafts, promotion, rollback, audit, traces) but a gap between governance **workflow** and governance **enforcement** — the system's own dev environment reached exactly the incoherent states the workflows exist to prevent, and the regression suite could not catch it. This plan closes that gap first. New retrieval features come last, and only with eval-proven gains.

**Core rules for this plan**
- No new product surface before AR1–AR3 are closed.
- Every milestone must leave the full suite green (`python -m unittest discover -s backend/tests`).
- Findings are not softened: where a capability was a stub, the milestone names it a stub.
- This plan does not modify or supersede `docs/02_Enterprise_RAG_Project_Plan_Milestones.md`; AR numbering is deliberately disjoint from M0–M33.

---

## Milestones

### Milestone AR0 — Preserve Audit Baseline And Link It Into Repo Navigation (Gate AR0: audit is canonical)

**Why this is required**
The audit is the evidence base for this entire plan. If it is not preserved verbatim and linked from the canonical reader path, future milestones will drift toward re-describing the system optimistically instead of remediating measured findings.

**What was not working in the earlier implementation**
- The repo had milestone notes and STATUS.md self-reports, but no independent baseline. STATUS.md understated the problem: it listed "DB-backed reruns from M20 onward" as the open debt, while the audit's actual suite run showed even M2–M19 paths erroring (222 tests: 158 passed, 7 failures, 57 errors).
- There was no single document an engineer could read to learn which capabilities are real, placeholder, or unverified.

**Goal**
Make the audit a first-class, linked, immutable reference baseline.

**Deliverables**
- `docs/03_Enterprise_RAG_Independent_Product_Audit_2026_06_11.md` committed unmodified (this gate).
- README.md "Reader Paths" and STATUS.md gain a link to the audit and to this remediation plan, labeled explicitly as an audit baseline, not a marketing document.
- STATUS.md "Current Verification Debt" updated to reflect the audit's measured suite result instead of the milder M20+ phrasing.

**DoD**
- Audit file present and byte-stable after review.
- README/STATUS link to both new docs.
- No edits to `docs/02_Enterprise_RAG_Project_Plan_Milestones.md`.

**Re-run checks**
- `make reader-clarity-check` (M31/M32 doc hygiene suites) passes with the new links.

**Priority:** P0 · **Effort:** S · **Depends on:** none

---

### Milestone AR1 — Restore Green, Environment-Independent Regression Suite (Gate AR1: the gate works again)

**Why this is required**
Every milestone in M0–M33 claims "re-run checks" as its closure mechanism. The audit demonstrated that this mechanism is currently broken: the suite cannot run green, so no claim downstream of it is verifiable. Nothing else in this plan can be honestly gated until this is fixed.

**What was not working in the earlier implementation**
- Full suite result on 2026-06-11: **222 tests, 158 passed, 7 failures, 57 errors**.
- **55 of the 57 errors had a single root cause:** the test harness hardcodes 384-dimensional synthetic vectors (`backend/tests/smoke_test_base.py:348`, `[similarity, ...] + [0.0] * 382`), while the live dev DB's `chunks.embedding` column is `vector(768)` after a `bge-base-en-v1_5` profile promotion. Every insert failed with `expected 768 dimensions, not 384`. The suite is environment-coupled: it tests "the dev DB as currently tuned," not the system, and fails whenever an admin legitimately promotes a different embedding profile.
- Four genuine contract breaks independent of the environment:
  1. `create_access_request()` caller/signature drift — a caller still uses the pre-M16.1 signature (`TypeError: missing 3 required keyword-only arguments: 'source_hint', 'request_id', 'answer_path'`).
  2. `KeyError: 'query_transform_enabled'` — retrieval profile config rows created before M18 are read without defaulting the M18 keys.
  3. `SELECT DISTINCT` / `ORDER BY` SQL error (`InvalidColumnReference`) in a repo query.
  4. Stale test reference to `app.api.ask._perform_ask_internal`, which the M33 refactor moved to `app.core_rag.answering`.
- Migration ledger mismatch: the applied-steps test expected MIG-P001..MIG-P020 but the DB ledger recorded only through MIG-P012, even though most M20–M33 tables physically exist — ledger and schema state disagree.

**Goal**
A suite that passes on a fresh DB **and** on a DB with any validly promoted embedding profile, with all contract breaks fixed and the migration ledger reconciled.

**Deliverables**
- Test harness derives vector dimension from the effective embedding profile (or pins its own test profiles via the existing temporary-profile context managers in `backend/app/tuning/sandbox_compare.py` patterns) instead of hardcoding 384.
- Option (preferred): tests run against an isolated schema/database so dev-DB tuning state cannot affect results.
- Fixes for the four contract breaks above, each with a regression test.
- Migration ledger reconciliation: ledger rows match the plan steps actually applied; a check asserts ledger == plan at startup or in the suite.
- A documented `make test` (or equivalent) target; suite status recorded in STATUS.md.

**DoD**
- `python -m unittest discover -s tests` is fully green twice: once against a freshly migrated empty DB, once against a DB with an active 768-dim embedding profile.
- Zero environment-caused errors remain; the 7 failures and 57 errors from the audit run are each accounted for (fixed or explicitly retired with rationale).

**Re-run checks**
- Full suite, both environments.
- `test_migration_plan_exposes_ordered_patch_steps` passes.
- The four contract-break regression tests pass.

**Priority:** P0 · **Effort:** M · **Depends on:** AR0 (baseline reference)

---

### Milestone AR2 — Configuration Coherence Enforcement (Gate AR2: incoherent states are rejected or loudly visible)

**Why this is required**
The audit's largest strategic finding is that governance is procedural, not mechanical: the workflows (promotion, registries, rollback) exist, but nothing enforces their invariants. The system must validate its own configuration instead of trusting that operators followed the workflow.

**What was not working in the earlier implementation**
Live dev DB inspection during the audit found three incoherent states the governance layer silently allowed:
- **Wrong profile metadata:** the embedding registry recorded `BAAI/bge-small-en-v1.5` with dimension **768**; the model actually produces 384-dim vectors. The `default` profile carried the same wrong value.
- **Sandbox draft active as live:** the active retrieval profile was `draft-645-retrieval` — an unpromoted tuning draft serving production-path queries.
- **Migration ledger mismatch:** ledger recorded MIG-P012 while the code's plan defines through MIG-P020 (schema partly present anyway).
The M17.b.3 "embedding safety" workflow did not prevent any of this, and no health surface reported it.

**Goal**
Make the three observed incoherent states impossible to create through the API, and detectable at startup and in the admin console when they exist anyway.

**Deliverables**
- Profile save/activation validates declared embedding dimension against the actual loaded model's output dimension; mismatch is rejected with a clear error.
- Activation guard: profiles named/flagged as drafts cannot become live except through the promotion endpoint; promotion renames/flags them accordingly.
- Startup coherence check (warn or fail by env): embedding profile dimension == `chunks.embedding` column dimension == model output; migration ledger == plan; active profiles are promoted ones.
- `GET /admin/health/coherence` endpoint returning per-invariant pass/fail with reasons (consumed later by AR10).
- Data repair migration/script for the existing wrong registry rows and draft-active state, with audit-log entries.

**DoD**
- Each of the three audit-observed states is reproduced in a test and is (a) rejected at write time, and (b) flagged by the health endpoint if injected directly into the DB.

**Re-run checks**
- New coherence test module green.
- Full suite green (AR1 invariant).
- Manual: health endpoint shows all-green on the repaired dev DB.

**Priority:** P0 · **Effort:** M · **Depends on:** AR1 (tests must be able to assert this)

---

### Milestone AR3 — Eval Packs And Promotion-Grade Metrics (Gate AR3: "measurable" becomes true)

**Why this is required**
The project's stated philosophy is that retrieval changes must be *measurable*. The audit found measurement is aspirational: the harnesses are real but the data and metrics cannot support any serious tuning decision. Until this milestone, no retrieval change in this repo can claim a measured improvement.

**What was not working in the earlier implementation**
- Eval fixtures totaled ~28 cases across 7 files (retrieval: 7, router: 4, ACL leak: 2, answer: 3, compare: 3, corpus policy: 3, benchmark: 6).
- Pass criteria were keyword/heading containment only — no graded relevance, no recall@k / MRR / nDCG, no answer-faithfulness scoring, no statistical comparison between configurations.
- Promotion decisions in the tuning lab rested on a single question's side-by-side output plus operator judgment.
- 176 real query events and 101 structured feedback rows existed in the dev DB but were not used to build eval cases.
- Score-fusion constants (anchor/graph/temporal boosts, `causal_terms` vocabulary in `backend/app/core_rag/retrieval.py:649`) were unfalsifiable — some visibly overfit to demo-corpus vocabulary.

**Goal**
Eval packs large and rigorous enough that a degraded retrieval configuration reliably fails, and an improved one measurably wins.

**Deliverables**
- 100+ labeled cases per flagship corpus, seeded substantially from mined `query_events` (the M20 mining tables already exist).
- Metrics: recall@k, MRR (nDCG optional), citation-faithfulness checks on answer-level cases; per-mode and per-profile breakdowns.
- Eval reports persist metric summaries alongside the existing active-profile snapshot.
- Documented labeling workflow so packs keep growing (feeds AR12).
- A negative-control case set proving the gate can fail: a deliberately degraded profile (e.g. `hybrid_alpha=0`, rerank off) must score measurably worse.

**DoD**
- Eval run on the current live profile produces metric baselines committed as a reference report.
- The degraded-profile control demonstrably fails the thresholds.

**Re-run checks**
- `app.eval.retrieval_eval` and enriched eval runs on the new packs complete and emit metrics.
- Full suite green.

**Priority:** P0 · **Effort:** L · **Depends on:** AR1

---

### Milestone AR4 — Close The Governance Loop: Eval Before Promotion (Gate AR4: promotion requires evidence)

**Why this is required**
The audit called this "the single biggest missed integration in the product": sandbox compare and the eval harness both exist, but the promotion path never invokes evaluation. Governance without evidence is ceremony.

**What was not working in the earlier implementation**
- The tuning lab's compare ran exactly one question through live vs. candidate (`backend/app/tuning/sandbox_compare.py`) and surfaced latency/citation-count deltas only.
- `POST /admin/tuning/promote` accepted a candidate with no eval result attached; promotion records stored no quality evidence.
- Consequence observed in the wild: the dev environment ended up with a draft profile live and no record of why (see AR2).

**Goal**
Promotion requires (or at minimum prominently records and surfaces) an eval-pack run on the candidate, and promotion history carries the eval deltas.

**Deliverables**
- "Run eval pack against candidate" action inside the tuning lab, executing AR3 packs under the candidate profile bundle.
- Promotion endpoint accepts/stores the eval run id and metric deltas; configurable enforcement mode (`require` / `warn`) with `require` as the default outside local.
- Console: promotion confirmation displays live-vs-candidate metric deltas; tuning history lists them.
- Rollback records likewise link the eval evidence that justified the rollback.

**DoD**
- Promoting without an eval run is blocked in `require` mode and loudly annotated in `warn` mode.
- The AR3 degraded-profile control cannot be promoted in `require` mode.

**Re-run checks**
- Tuning smoke tests extended: draft → eval → promote → rollback round-trip with persisted deltas.
- Full suite green.

**Priority:** P0 · **Effort:** M · **Depends on:** AR3

---

### Milestone AR5 — Replace Placeholder Query Transformation With A Real Implementation (Gate AR5: the flags do what they say)

**Why this is required**
M18 shipped governed admin controls, profile flags, sandbox visibility, and trace fields for query transformation — but the capability behind them is a stub. The audit classified this as "scaffolding wearing governance clothing"; the governance around the feature is more code than the feature.

**What was not working in the earlier implementation**
- `backend/app/core_rag/query_transform.py:9-43`: "expansion" was a hardcoded 5-entry synonym dictionary (`q4`, `liability`, `subcontracting`, `budget`, `compensation`); "rewrite" was whitespace normalization; "HyDE" was the literal prefix string `"Hypothetical relevant passage answering: {question}"`. No LLM was involved anywhere.
- Variants were string-concatenated into a single effective query rather than retrieved separately and fused.
- The `transform_timeout_ms` budget existed but guarded nothing that could take time.

**Goal**
LLM-backed rewrite/expansion/HyDE behind the *existing* profile flags, timeout budget, and trace fields — measured by AR3 packs.

**Deliverables**
- Real rewrite and HyDE generation via the configured LLM profile, honoring `transform_timeout_ms` with graceful fallback to the original query (trace `fallback_reason` already plumbed).
- Expansion sourced from corpus-aware signals (or LLM) instead of the hardcoded dictionary; the dictionary is deleted.
- Optional multi-query retrieval fan-out for variants (retrieve per variant, fuse), kept behind a profile flag.
- Eval comparison: transform-on vs transform-off deltas on AR3 packs, recorded in the milestone note.

**DoD**
- With flags enabled, traces show genuinely generated variants; with the LLM unreachable, answers still complete via fallback within budget.
- Measured eval delta documented (positive, neutral, or negative — honestly).

**Re-run checks**
- M18 smoke tests updated and green; transform timeout/fallback test; AR3 pack run with flags on/off.

**Priority:** P1 · **Effort:** M · **Depends on:** AR3 (measurement), AR9 (helpful, not required)

---

### Milestone AR6 — Rename Or Properly Implement The Semantic Cache (Gate AR6: cache naming is truthful)

**Why this is required**
The audit found a naming/capability mismatch in a flagship M19/M33 feature. Either the name must match the mechanism, or the mechanism must match the name. Shipping an "enterprise" cache whose headline adjective is wrong erodes trust in every other label in the product.

**What was not working in the earlier implementation**
- The "semantic cache" matched on an exact normalized-question hash (`backend/app/db/repo_semantic_cache.py`, `cache_scope` → `_stable_hash`). Paraphrases never hit.
- `semantic_cache_similarity_threshold: float = 0.92` existed in `RetrievalProfileConfig` (`backend/app/profiles/models.py:58`) and was never read by any lookup path — a config field implying a capability that did not exist.
- The governance around the cache (policy scoping, ACL/profile/revision validation, user refresh with material-change detection) was genuinely good — the audit's criticism is strictly the "semantic" claim.

**Goal**
Truthful cache: either (a) rename to "governed exact-answer cache" everywhere and remove the dead threshold field, or (b) implement a real similarity tier safely.

**Deliverables**
- Decision recorded in the milestone note (rename vs implement), with rationale.
- If rename: all UI/docs/config/field names updated; dead `semantic_cache_similarity_threshold` removed or clearly marked reserved; migration note for existing policies.
- If implement: embedding-based similarity lookup over cached questions using the existing embedder, gated by the threshold field, and validated through the *same* ACL-fingerprint/profile-revision/version-namespace checks as exact hits; paraphrase hit/miss test cases; false-hit guard cases (similar question, different intent).
- Cache metrics distinguish exact hits from similarity hits.

**DoD**
- No user-visible label, config field, or doc claims semantic matching unless similarity lookup is actually live and tested.

**Re-run checks**
- M33 cache governance suite green; new paraphrase/false-hit tests (if implemented); full suite green.

**Priority:** P1 · **Effort:** S (rename) / M (implement) · **Depends on:** AR2 (validation surfaces), AR3 if implementing (to measure hit quality)

---

### Milestone AR7 — Embedding And Index Lifecycle Management (Gate AR7: model swaps cannot corrupt the index)

**Why this is required**
The single failure that disabled the regression suite (AR1) was an embedding/index dimension drift — proof that the lifecycle between "promote embedding profile" and "index actually re-embedded" is unmanaged. An enterprise starter must make this transition safe, observable, and blocking.

**What was not working in the earlier implementation**
- A 768-dim profile was activated against an index that the test harness (and earlier code) assumed was 384-dim; nothing blocked the activation, surfaced the mismatch, or orchestrated the reindex. The result broke 55 tests and left the system silently incoherent.
- The only embedding-swap guard lived inside sandbox compare (`blocked_embedding_scope` warning) — not in the activation path actually used.
- Reindex existed only as a per-source admin action and script; no corpus-wide guided flow, progress reporting, or completion verification.

**Goal**
A guided, verifiable embedding-change lifecycle with hard blocks on mismatched states everywhere, not just in the sandbox.

**Deliverables**
- Activation of an embedding profile with a different dimension requires an explicit reindex plan: target column/dimension handling (versioned column or rebuild), progress (counts, ETA via existing queue metrics), abort/resume.
- Hard block (shared with AR2 health checks) on serving vector search while profile dimension ≠ index dimension; keyword-only degraded mode with operator banner as the fallback.
- Post-reindex verification step: sampled re-embedding distance check + counts reconciliation.
- Runbook: `docs/runbooks/EMBEDDING_MODEL_SWAP.md`.

**DoD**
- End-to-end model swap on a ≥1k-chunk corpus completes through the console without manual SQL; suite green before and after; mismatch states unreachable through the API.

**Re-run checks**
- New lifecycle test (swap on synthetic corpus); AR2 coherence tests; full suite green on both dimensions.

**Priority:** P1 · **Effort:** L · **Depends on:** AR2

---

### Milestone AR8 — Deployment Portability And Multi-Worker Safety (Gate AR8: someone else can run it)

**Why this is required**
A "starter" that only runs on the author's machine and only under one process is not adoptable. The audit flagged fork blockers in the repo itself and correctness assumptions that silently break under standard deployment shapes.

**What was not working in the earlier implementation**
- `docker-compose.yml` hardcoded a personal volume path (`/Users/Work/Projects/Backup/Database/rag-enterprise-pgdata`); docs and README used absolute `/Users/Work/...` paths throughout — a fresh-machine fork fails immediately.
- Single-process assumptions: in-process threaded ingestion worker poked by an in-memory event, in-memory rate limiting (acknowledged in a code comment), module-global embedding/reranker singletons. Running `uvicorn --workers 2` silently breaks queue wakeups and rate limits.
- Sandbox compare monkeypatched module-level resolver functions (`backend/app/tuning/sandbox_compare.py:28-76`); a concurrent live request during a compare could be served with candidate profiles — a correctness (and tuning-integrity) hazard.

**Goal**
Fresh-machine quickstart works; concurrency hazards are removed or explicitly fenced.

**Deliverables**
- Relative/parameterized paths in compose and docs; quickstart verified on a clean checkout by someone/something other than the original machine.
- Sandbox compare passes profile bundles explicitly down the call chain (request-scoped overrides) instead of monkeypatching globals; concurrency test proves no profile bleed.
- Queue wakeup and rate limiting either moved to Postgres-backed mechanisms or the single-worker constraint enforced/documented at startup (refuse `--workers > 1` unless explicitly overridden).
- Deployment notes updated in the relevant runbooks.

**DoD**
- Clean-machine `docker compose up -d` + quickstart succeeds.
- Concurrent sandbox+live request test shows live requests always use live profiles.

**Re-run checks**
- New concurrency test; quickstart walkthrough recorded in the milestone note; full suite green.

**Priority:** P1 · **Effort:** M · **Depends on:** AR1

---

### Milestone AR9 — Provider Abstraction For Generation (Gate AR9: bring-your-own-model)

**Why this is required**
Enterprise adopters arrive with a sanctioned model endpoint (Azure OpenAI, OpenAI, Anthropic, vLLM, Bedrock). The audit identified Ollama-only support as an adoption blocker that no amount of governance offsets.

**What was not working in the earlier implementation**
- `backend/app/llm/client.py` supported exactly two providers: `ollama` and `ollama_cloud`, with provider-specific payload shapes inlined in `generate_answer`. Any other provider required editing the client.
- The `LLMProfileConfig.provider` field implied pluggability that did not exist.

**Goal**
A generic OpenAI-compatible client interface plus a pluggable provider registry, preserving the strict-JSON answer contract, repair passes, and approved-model governance unchanged.

**Deliverables**
- Provider interface with implementations: OpenAI-compatible (covers Ollama, vLLM, Azure OpenAI, OpenAI), optional Anthropic; provider selected purely by profile config.
- Preflight (`verify_llm_ready`) generalized per provider.
- `structured_output_mode` handling (native JSON vs prompt-only) expressed per provider/model capability, keeping the GPT-OSS deterministic path.
- Approved-model registry continues to gate which provider/model combinations are selectable.

**DoD**
- Switching to a non-Ollama endpoint requires only a profile change; answer-contract tests (JSON parse, citations, repair, second pass) pass unchanged against at least two providers (one may be a mock).

**Re-run checks**
- Answer-contract suite against two providers; GPT-OSS compatibility tests green; full suite green.

**Priority:** P1 · **Effort:** M · **Depends on:** AR1

---

### Milestone AR10 — Operator Health And Trust Dashboard (Gate AR10: incoherence is visible at a glance)

**Why this is required**
The audit found that the admin console shows what is configured but never whether the configuration is self-consistent — the exact blind spot that let the dev environment rot. Operators need one page that answers "is this system coherent right now?"

**What was not working in the earlier implementation**
- Three live incoherences (wrong registry dimensions, draft profile active, migration ledger mismatch) were invisible in the console; an operator had to inspect the DB to find them, as the audit did.
- Health information existed only as scattered per-feature views (jobs, traces, cache metrics) with no invariant-level rollup.

**Goal**
A single admin health/coherence page backed by the AR2 endpoint, suitable as the first screen an operator checks.

**Deliverables**
Admin page (module-flag-gated like other admin modules) showing pass/fail with reasons for:
- active embedding profile dimension vs DB `chunks.embedding` dimension vs actual model output;
- active profile statuses (promoted vs draft, last promotion/rollback event);
- migration ledger vs plan;
- reranker model loadability (warm-up record freshness);
- cache namespace/revision health and policy state;
- eval gate status (last AR3 baseline run, last AR4 promotion evidence).
Plus a console banner when any P0 invariant fails.

**DoD**
- Injecting each AR2 incoherent state turns the corresponding tile red with an actionable reason; healthy dev DB shows all green.

**Re-run checks**
- Endpoint contract tests; UI smoke for the page; full suite green.

**Priority:** P1 · **Effort:** M · **Depends on:** AR2 (endpoint), AR4 (eval status tile)

---

### Milestone AR11 — Cost, Token, And Latency Governance (Gate AR11: the cost half of "latency/cost traces")

**Why this is required**
The original plan promised "latency/cost traces"; the audit found latency delivered and cost entirely absent. Tuning decisions (rerank budgets, deep research, transform fan-out, provider choice after AR9) have real cost consequences operators currently cannot see.

**What was not working in the earlier implementation**
- No token counting, no per-request cost estimate, no per-profile cost rollups, no budget alerts anywhere in traces, eval reports, or the console. The only budget mechanism was the reranker latency budget.

**Goal**
Token and cost visibility threaded through the existing trace lattice, plus simple budget alerting.

**Deliverables**
- Prompt/completion token counts per generation call recorded into retrieval traces and eval reports (provider-reported where available, estimated otherwise — estimation method documented).
- Per-profile/per-model cost summaries (configurable price table) in the admin console.
- Budget thresholds with alert events into the existing notification/audit stream.
- Sandbox compare and AR4 promotion records include token/cost deltas alongside latency deltas.

**DoD**
- An operator can answer "what does deep research cost vs fast mode on this corpus" from the console.

**Re-run checks**
- Trace schema tests updated; compare/promotion payload tests include cost fields; full suite green.

**Priority:** P2 · **Effort:** M · **Depends on:** AR9 (provider-reported usage), AR4 (promotion records)

---

### Milestone AR12 — Feedback-To-Eval Flywheel (Gate AR12: operational data becomes regression protection)

**Why this is required**
The audit identified the query-mining → eval-pack loop as the repo's most credible path to durable differentiation — and found it open: all the ingredients exist, none are connected. Closing it converts accumulating usage data into a growing, proprietary regression asset.

**What was not working in the earlier implementation**
- 423 traces, 176 query events, and 101 structured feedback rows existed in the dev DB; `query_failure_clusters` and `derived_eval_packs` tables and endpoints existed (M20/M22) — but there was no path from a thumbs-down cluster or `missing_evidence` event to an eval case, and no trend reporting on pack pass rates.

**Goal**
One-click (or one-action) conversion of negative-feedback/failure clusters into reviewed eval cases, with pass-rate trends visible over time.

**Deliverables**
- Admin flow: select failure cluster → propose eval cases (question + expected cues prefilled from trace evidence) → human review/label → append to an AR3 pack with provenance metadata.
- Pack pass-rate trend view per corpus/profile in the console.
- Guardrail: derived cases are quarantined until reviewed, so noisy feedback cannot poison the gate.

**DoD**
- A real thumbs-down event from the dev DB travels the full path into a pack and is exercised by the next eval run.

**Re-run checks**
- M20/M22 smoke tests extended for the derivation flow; AR3 eval run includes derived cases; full suite green.

**Priority:** P2 · **Effort:** M · **Depends on:** AR3

---

### Milestone AR13 — Connector Operations And Source Freshness (Gate AR13: knowledge staleness is visible and managed)

**Why this is required**
The audit found ingestion breadth (uploads, DB rows, `.eml`) ahead of ingestion *operations*: nothing keeps connected sources fresh or tells anyone they are stale. Enterprise trust in answers depends on knowing how old the evidence is.

**What was not working in the earlier implementation**
- The DB connector (`backend/app/connectors/db.py`) synced incrementally only when manually triggered; no scheduling, no retry/backoff, no sync-health surface.
- "Enterprise email ingestion" was `.eml` file upload (with good attachment handling) — no live mailbox sync, and the docs' phrasing overstated this.
- Sources carried no staleness indication anywhere in the user or admin UI; re-ingest/re-enrich were purely manual operator actions.

**Goal**
Operated connectors: scheduled syncs with health/retry, and freshness visibility on every source.

**Deliverables**
- Connector scheduling (interval-based is sufficient) with sync run history, failure retry/backoff, and per-connector health status in the admin console.
- Source freshness metadata (last synced/ingested/enriched) with staleness badges in admin sources and user-facing evidence views.
- Docs corrected to state plainly that email ingestion is `.eml`-file based; live mailbox connectors remain explicitly out of scope until after this gate.

**DoD**
- A connector with an unreachable upstream shows degraded health and retries with backoff; stale sources are visibly badged.

**Re-run checks**
- Connector sync/retry tests; M12 connector smoke updated; full suite green.

**Priority:** P2 · **Effort:** M · **Depends on:** AR1, AR8 (worker model affects scheduling)

---

### Milestone AR14 — Retrieval Enhancements, Only With Eval-Proven Gains (Gate AR14: no unfalsifiable tuning)

**Why this is required**
The audit found the existing advanced retrieval layers (anchor boosts, graph/temporal signals, deep research) already carry unmeasured, ad hoc constants — some overfit to demo-corpus vocabulary. Adding more retrieval machinery before measurement exists would compound the problem. This milestone is deliberately last.

**What was not working in the earlier implementation**
- MMR was an explicit no-op placeholder (`apply_mmr_placeholder`, reason `placeholder_reserved_for_future_milestone`, `backend/app/core_rag/reranker.py:89-95`) despite `mmr_enabled`/`mmr_lambda` profile fields.
- Keyword indexing used a single `search_tsv` with no field weighting (heading vs body), despite "field-weighted keyword indexing" appearing in roadmap language.
- Graph/temporal boosts and deep-research recall had zero eval cases isolating their effect; their score constants (0.35 graph blend, 0.12/0.08 temporal, `causal_terms` set at `retrieval.py:649`) were unfalsifiable.

**Goal**
Implement or retire each enhancement based on AR3 evidence — never on plausibility.

**Deliverables (each item ships only with an eval verdict)**
- Real MMR diversity behind the existing flags, with measured effect; otherwise remove the placeholder flags.
- Field-weighted FTS (`setweight` heading vs body in the tsv trigger), measured.
- Eval cases isolating graph, temporal, and deep-research contributions; retune or remove magic constants accordingly; delete demo-overfit vocabulary (`causal_terms`) unless it survives measurement on real corpora.
- Each change recorded with before/after metrics in its milestone note.

**DoD**
- No retrieval flag in profiles corresponds to a no-op; every boost constant either has eval evidence or is removed.

**Re-run checks**
- AR3 packs before/after per enhancement; full suite green.

**Priority:** P2 · **Effort:** M (aggregate; S per item) · **Depends on:** AR3 (hard dependency — do not start without it), AR4

---

## Recommended 30/60/90-Day Execution

- **30 days:** AR0, AR1, AR2 — baseline preserved, regression gate green and environment-independent, coherence enforced and repaired. Nothing else starts until these close.
- **60 days:** AR3, AR4, AR8 — real eval packs and metrics, eval-gated promotion, fresh-machine portability and concurrency safety.
- **90 days:** AR5, AR6, AR7, AR9 — real query transformation, truthful cache, embedding/index lifecycle, provider abstraction.
- **Beyond 90 days:** AR10–AR13 as operator-trust and flywheel work; AR14 strictly last and strictly evidence-gated.

## Do Not Pursue Yet

Per the audit's "do not pursue" list, the following are explicitly out of scope for this remediation plan and should be rejected if proposed before the gates above close:

- **Agent frameworks / multi-step agentic retrieval** — adds surface to an unverified core; contradicts the plan's non-goals.
- **Multi-tenant SaaS features** (workspaces, quotas, billing) — original plan non-goal; nothing in the audit motivates it.
- **Exotic retrieval algorithms** (ColBERT/multi-vector, learned fusion) — unfalsifiable until AR3 exists, and likely unnecessary after it.
- **More governance UI surface** before enforcement (AR2) and evaluation (AR3/AR4) exist — the audit's core criticism is precisely workflow-without-enforcement.
- **Live mailbox/Slack/Drive connectors** before connector operations and source freshness (AR13) are handled — breadth before operability repeats the email-ingestion overstatement.

---

**Status discipline for this plan:** each completed AR milestone gets a note in `docs/milestones/` and a STATUS.md update, same as M-series milestones. An AR milestone is not "complete" with pending DB-backed verification — that pattern is what this plan exists to end.
