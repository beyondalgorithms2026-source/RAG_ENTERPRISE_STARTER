# STATUS.md — Operational Snapshot

**Last completed M-series milestone:** M33 — Governed Semantic Cache Policies, Scoped Enablement, And User Refresh  
**Active work track:** UX-series UI/UX audit remediation (`docs/05_Enterprise_RAG_UIUX_Audit_Remediation_Milestones.md`); M20–M30 manual verification closure also open
**Current AR milestone:** AR0–AR20 complete (audit remediation + post-audit console/UI). No open AR milestones.
**Current UX milestone:** UX7 complete (2026-06-17) — IA & control hygiene. Admin sidebar grouped into collapsible sections (Operate / Retrieval / Data / Governance) with Overview pinned (`lib/admin-nav.ts` `groupAdminNav`; pure module so the client shell can import it). Workspace nav vocabulary reconciled to one verb set — sidebar now Ask / Search / History (Search surfaced in the sidebar; "Chat"→"Ask", "Search History"→"History"); guide copy aligned. Fake/disabled controls are **marked "coming soon" (preserved, not removed)** with a consistent treatment (`title="Coming in a later release."`, `(coming soon)` accessible name, `.coming-soon-badge` "Soon" pill on labelled controls / `.is-coming-soon` accent dot on icon-only): ⌘K search, workspace search, Settings ×2, composer attach/image/mic, Export Findings. Pattern documented in `web/DESIGN.md`. `next build` 12/12 + `tsc --noEmit` green; no-external-deps invariant holds. Next: UX8 (accessibility baseline).

**Prior UX milestone:** UX6 complete (2026-06-17) — Search facets, sort, and labeled relevance. Added live client-side facet controls (source type, corpus, freshness, indexed-within) + a sort control to the Search surface, built on canonical `ui/Toggle` + `ui/Select`; they filter and reorder the returned result set without a refetch. Result summary now shows "X of Y results"; the relevance bar normalizes to the top *visible* result. Required a minimal additive backend field — `corpus_name` on `SearchResultItem` (`backend/app/core_rag/retrieval.py`), populated from source metadata via the already-imported `get_sources_by_ids` — to power the corpus facet (no retrieval-logic change). Backend: full suite **349/349 green** (isolated re-run; an earlier overlapping run showed 2 transient DB-state failures that did not reproduce). Frontend: `next build` 12/12 + `tsc --noEmit` green; no-external-deps invariant holds. Next: UX7 (IA & dead-control cleanup).

**Prior UX milestone:** UX5 complete (2026-06-17) — inline citation anchoring (claim → source). In-range `[n]` markers in the answer body render as keyboard-focusable superscript chips (`components/markdown.tsx`): click selects the citation (reusing the shared `selectCitation` helper → expands the section, scrolls it in, loads chunk context via the existing effect); hover/focus highlights the matching evidence card (`is-hovered`). Accessible names (`aria-label="Citation N: file"`), focus-visible ring. Out-of-range numbers and `[^n]` footnotes are left untouched. Citation pills + evidence-card clicks refactored onto the same helper. `next build` 12/12 + `tsc --noEmit` green; no-external-deps invariant holds. Next: UX6 (Search facets/sort/relevance).

**Prior UX milestone:** UX4 complete (2026-06-17) — grounded answers render as sanitized Markdown. Replaced the `message.content.split(/\n+/)` `<p>` rendering in `chat-workspace.tsx` with `AnswerMarkdown` (`components/markdown.tsx`: `react-markdown` + `remark-gfm`, bundled — no runtime external dep). Supports headings/lists/tables/code/emphasis with a constrained 72ch reading measure and `.chat-markdown` typography per DESIGN.md. Raw-HTML injection verified absent (react-markdown escapes raw HTML by default; `<script>`/`<img onerror>` render as escaped text). Citation pills + evidence rail untouched. `next build` 12/12 + `tsc --noEmit` green; no-external-deps invariant holds. Next: UX5 (inline citation anchoring).

**Prior UX milestone:** UX3 complete (2026-06-17) — Search surface repaired. `search-workspace.tsx` rebuilt off the undefined orphan classes (`workspace-panel`, `panel-toolbar`, `inventory-*`, `table-subtle`) onto the canonical `admin-data-table` with real column headers (Source/Type/Location/Relevance/Snippet), a labeled relevance indicator (bar + value + tooltip, relative to the top result) replacing the raw `score.toFixed(3)`, a result count + mode/latency summary, and toolbar controls routed through canonical `ui/TextInput` + `ui/Select` (+ Enter-to-search). Empty/loading/no-result states preserved. `next build` 12/12 + `tsc --noEmit` green; UX1 no-external-deps invariant holds. UI source of truth: `web/DESIGN.md`. Next: UX4 (Markdown answers). Earlier: UX2 (one button system + sectioned CSS), UX1 (no external UI deps), UX0 (design language) — all 2026-06-17. Tag `ux-foundation-2026-06-17` covers UX0–UX2.

## Independent Product Audit (2026-06-11)

An independent non-security product audit was conducted on 2026-06-11 against branch `RAG_Enterprise_Dev` @ `54feb95` (M33). Key measured results:
- **Test suite:** 222 tests: 158 passed, 7 failures, 57 errors
- **Root cause of 55/57 errors:** hardcoded 384-dim vectors in test harness vs 768-dim DB column
- **Configuration incoherence found:** wrong dimension metadata in registry (bge-small as 768), sandbox draft active as live (`draft-645-retrieval`), migration ledger mismatch (P012 vs P020)
- **Verdict:** strong PoC with genuine starter scaffolding; blocked from enterprise-starter status by broken regression gate, thin evaluation, and stub features behind governance UIs

Audit baseline: `docs/03_Enterprise_RAG_Independent_Product_Audit_2026_06_11.md`  
Remediation plan: `docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md`  
Git tag: `audit-baseline-2026-06-11`

## AR-Series Progress

| Milestone | Status | Notes |
|-----------|--------|-------|
| AR0 — Preserve Audit Baseline | **Complete (2026-06-12)** | Files committed + tagged, byte-stable vs tag; README/STATUS linked; `reader-clarity-check` green (21/21); note: `docs/milestones/AR0_preserve_audit_baseline.md` |
| AR1 — Green Regression Suite | **Complete (2026-06-12)** | 224/224 green on fresh 384-dim DB and tuned 768-dim dev DB; dimension derived from live column; posture/profiles pinned per test; active-profile snapshot/restore ends suite-induced live-config drift; real `schema_migration_ledger` with ledger==plan assertion; `make test`; note: `docs/milestones/AR1_green_environment_independent_suite.md` |
| AR2 — Configuration Coherence | **Complete (2026-06-12)** | Write-time guards (dimension validation, draft-activation block, promotion rename); `GET /admin/health/coherence`; startup enforcement (warn local, fail prod); dev DB repaired via `python -m app.db.repair_coherence` (deep check all-green); 232/232 suite; note: `docs/milestones/AR2_configuration_coherence_enforcement.md` |
| AR3 — Real Eval Packs | **Complete (2026-06-12)** | 400-case graded flagship pack; recall@k/MRR/nDCG/faithfulness metrics; baseline committed (recall@5 0.504, MRR 0.850 → pass) vs degraded control (recall@5 0.242 → fail); labeling runbook; dev DB re-embedded after finding suite-destroyed embeddings; note: `docs/milestones/AR3_eval_packs_and_promotion_grade_metrics.md` |
| AR4 — Eval Before Promotion | **Complete (2026-06-13)** | `POST /admin/tuning/eval-runs` runs AR3 packs under the candidate bundle; persisted `tuning_eval_runs` (MIG-P021); promotion blocked in `require` mode without a fresh passing run (degraded control unpromotable), loudly annotated in `warn`; promote/rollback events carry eval evidence + live-vs-candidate deltas; console shows gate/deltas; 249/249 suite; note: `docs/milestones/AR4_eval_before_promotion.md` |
| AR5 — Real Query Transform | **Complete (2026-06-13)** | LLM-backed rewrite/expansion/HyDE behind the existing flags; hardcoded synonym dict + literal HyDE prefix deleted; `transform_timeout_ms` enforced as a real total budget with graceful per-strategy fallback; `multi_query_enabled` fan-out (retrieve per variant, RRF-fuse); measured transform on/off delta = 0.0000 because the configured gpt-oss model returns empty content (honest finding — mechanism proven by 8 unit tests); 257/257 suite; note: `docs/milestones/AR5_real_query_transformation.md` |
| AR6 — Truthful Cache Naming | **Complete (2026-06-13)** | Implemented (not renamed) a real embedding-similarity tier: per-policy `match_mode`/`similarity_threshold` (MIG-P022), `_semantic_lookup` relaxes only the question dimension under identical ACL/profile/corpus/revision governance (shared `_finalize_hit`); dead `semantic_cache_similarity_threshold` removed from retrieval profile; `cache_health` splits exact vs similarity hits; truthful UI match-mode selector; measured calibration noted (bge-base paraphrases 0.70–0.83, so 0.92 is precision-first); 265/265 suite; note: `docs/milestones/AR6_semantic_cache_similarity.md` |
| AR7 — Embedding Lifecycle | **Complete (2026-06-13)** | Managed swap lifecycle (`app/embedding/lifecycle.py`, MIG-P023 `embedding_swap_runs`): plan→reindexing→verifying→completed, resumable batches, abort, sampled self-similarity + counts verification; vector search hard-blocks to keyword-only on dimension mismatch (`degraded_vector` trace + `vector_serving` coherence invariant); dimension-changing embedding activation blocked (422 `embedding_reindex_required`) — only the lifecycle may bring it live; `POST /admin/embedding/swap/*` endpoints; runbook `docs/runbooks/EMBEDDING_MODEL_SWAP.md`; 273/273 suite; note: `docs/milestones/AR7_embedding_index_lifecycle.md` |
| AR8 — Deployment Portability | **Complete (2026-06-13)** | docker-compose uses a portable named volume + env overrides (no host path); README/quickstart absolute `/Users/Work/...` paths made repo-relative; sandbox/candidate overrides moved from module-global monkeypatching to a `ContextVar` (`profile_overrides`) so candidate profiles never bleed into concurrent live requests; startup refuses `WEB_CONCURRENCY>1` unless `ALLOW_MULTI_WORKER=true` (single-process assumptions named, not hidden); 279/279 suite; note: `docs/milestones/AR8_deployment_portability_and_worker_safety.md` |
| AR9 — Provider Abstraction | **Complete (2026-06-13)** | Pluggable provider registry (`app/llm/providers.py`): OpenAI-compatible (OpenAI/Azure/vLLM/Ollama), Ollama-native (cloud), Anthropic; `client.py` delegates via one `_provider_generate` path; `verify_llm_ready` generalized; `structured_output_mode`/native-JSON honored per provider capability (GPT-OSS path unchanged); `GET /admin/llm/providers`; registry gating untouched; full answer contract proven against 2 provider shapes; 286/286 suite; note: `docs/milestones/AR9_provider_abstraction.md` |
| AR10 — Health Dashboard | **Complete (2026-06-13)** | `app/health.py` aggregates 8 tiles (5 P0 coherence invariants + reranker warm-up + cache state + eval gate) into one `{banner, p0_breached, tiles}` payload; `GET /admin/health/dashboard`; console Health page + P0 banner; injecting an AR2 state turns the tile red and breaches P0 (tested), healthy shows P0 green; 292/292 suite; note: `docs/milestones/AR10_operator_health_dashboard.md` |
| AR11 — Cost/Token Governance | **Complete (2026-06-13)** | Per-call token usage (provider-reported or documented char-heuristic estimate, flagged); configurable price table (`LLM_PRICE_TABLE_JSON`); request-scoped ContextVar accumulation into trace `generation_usage`; `generation_usage_events` (MIG-P024) + `GET /admin/cost/summary` (per mode/model/provider); `LLM_COST_ALERT_USD` budget alert → audit event; sandbox compare cost/token deltas; `/console/admin/cost` page; 302/302 suite; note: `docs/milestones/AR11_cost_token_latency_governance.md` |
| AR12 — Feedback→Eval Flywheel | **Complete (2026-06-13)** | `app/eval/feedback_flywheel.py`: failure cluster → quarantined (`unreviewed`) AR3 pack cases with trace-evidence prefill → human review/label → gating; quarantine guardrail (AR3 gate excludes unreviewed); pass-rate trend from AR4 `tuning_eval_runs`; `POST /admin/feedback-eval/{propose,append,review}` + `GET /{quarantine,trend}`; `/console/admin/flywheel` page; DoD full path tested (thumbs-down → pack → review → next eval gates it); 305/305 suite; note: `docs/milestones/AR12_feedback_to_eval_flywheel.md` |
| AR13 — Connector Operations | **Complete (2026-06-13)** | Postgres-backed interval schedules, atomic leases, durable sync-run history, degraded health + exponential retry, source lifecycle timestamps/freshness badges across admin/user/evidence views; email truthfully scoped to uploaded `.eml`; 310/310 suite; note: `docs/milestones/AR13_connector_operations_and_source_freshness.md` |
| AR14 — Retrieval Enhancements | **Complete (2026-06-13)** | Real MMR with ACL-trimmed vectors and traced fallback; weighted heading/body FTS (MIG-P026); ContextVar scoring ablations; demo `causal_terms` deleted; evidence API/console; 400-case AR3 control passed with recall@5 0.504167→0.505000, MRR unchanged 0.850086, nDCG@10 0.765736→0.765930; 315/315 suite; note: `docs/milestones/AR14_eval_proven_retrieval_enhancements.md` |

**AR0–AR14 audit remediation plan complete (tag `ar-remediation-complete-2026-06-13`).** AR15+ below extend the plan from a follow-up console/UI completeness review (not the original audit).

| AR15 — Operator Visibility & System Posture | **Complete (2026-06-15)** | `app/system_posture.py` + `GET /admin/system/posture` (7 sections, each with editable_via/restart); global `admin-health-banner` on every admin page when not healthy; health `semantic_cache` tile now warns "globally OFF" when no policy; read-only System Posture table in the health page; 321/321 suite; note: `docs/milestones/AR15_operator_visibility_system_posture.md` |
| AR16 — Embedding & Model-Swap Console | **Complete (2026-06-15)** | `/console/admin/embedding` drives the AR7 lifecycle (plan→begin→run batches with progress→verify→abort), serving-state header + keyword-only banner during reindex, swap history; web-only (no backend change); 321/321 suite; tsc clean; note: `docs/milestones/AR16_embedding_model_swap_console.md` |
| AR17 — Provider & Cost-Governance Console | **Complete (2026-06-15)** | `/console/admin/providers` creates/updates/tests/activates provider profiles; API keys are write-only and redacted from responses/audits; MIG-P027 runtime settings provide runtime→env→default budget, price-table, and eval-enforcement precedence; cost/tuning consoles edit governed values with approval-actor support; 333/333 suite; note: `docs/milestones/AR17_generation_provider_cost_governance_console.md` |
| AR18 — UI Modularity & Least-Privilege Gating | **Complete (2026-06-15)** | Health/cost/flywheel/embedding/providers are first-class modules; formerly ungated embedding/LLM/retrieval endpoint groups now return 403 when disabled; runtime→env→scenario precedence uses MIG-P027; `/console/admin/modules` manages the audited deployment-wide subset; 340/340 suite; note: `docs/milestones/AR18_admin_ui_modularity_and_least_privilege_gating.md` |
| AR19 — Console Component & Form-System Refactor | **Complete (2026-06-15)** | 1,403-line profiles mega-component replaced by a 36-line composer + four sub-400-line panels; shared form primitives adopted across active admin controls; endpoint behavior preserved; note: `docs/milestones/AR19_admin_console_component_and_form_system_refactor.md` |
| AR20 — UI Consistency & Alignment | **Complete (2026-06-15)** | Boxed white controls + select chevron (root-cause CSS fix across all panels); `.admin-data-table`/scroll on flywheel/posture/cost tables; sticky + reveal-on-select detail panes for Sources/Jobs/Audit Log; human-readable values; Visual Mode + retrieval-evidence tooltips; source download with size warning (`/admin/sources/{id}/download`); `UI_CONSISTENCY_CHECKLIST.md`; 349/349 suite; note: `docs/milestones/AR20_ui_consistency_and_alignment.md` |

## Current Repo Posture

- Active backend: `backend/`
- Active frontend: `web/`
- Legacy fallback UI: `frontend/` (flagged for removal — audit weakness #7)
- Strongest implemented runtime scenario: enterprise-style OIDC/dev identity with SQL-level access trimming, admin governance, and scenario packaging
- GPT-OSS answer handling uses deterministic prompt-only JSON mode, tolerant schema-validated extraction, and context-aware repair
- Semantic cache governance is independent from retrieval tuning, globally off by default, and activatable only for explicit scopes
- **Dev DB coherence:** repaired and enforced as of AR2 — registry dimensions corrected, draft-active profile re-pointed to a promoted name, ledger asserted against the plan; `GET /admin/health/coherence` reports per-invariant status

## M-Series Completed Milestones

- M0 through M17.b.2
- M17.b.3: Manual testing completed
- M18: Manual testing completed
- M19: Manual testing completed
- M31: Repository Hygiene, Canonical Paths, And Safe Source Control Workflow
- M32: Reader Clarity, Onboarding Contract, And Canonical Navigation Blueprint
- M33: Governed Semantic Cache Policies, Scoped Enablement, And User Refresh

## M-Series Pending DB-backed Re-run Checks

M20, M21, M22, M23, M24, M25, M26, M27, M28, M29, M30

## Current Verification Debt

- **Test suite is green:** AR19 final count pending release-gate run on the live vector(768) dev DB; AR18 baseline was 340/340; AR1 verified 224/224 on a freshly migrated empty DB as well
- AR19: form structure is unified, but visual spacing/alignment and native select polish remain explicitly deferred to AR20
- AR18: admin-module composition is deployment-wide, not tenant-scoped; arbitrary custom subsets may disable a module needed by another panel, so scenario presets remain the supported coherent defaults
- AR17: provider API keys are no longer returned or written to audit payloads, but remain stored in profile JSON; production deployments must provide database-at-rest encryption or an external secret manager
- AR17: OpenAI/Azure/vLLM/Anthropic provider flows are transport-mocked because no live cloud credentials are available; the console and provider-specific request contracts are tested
- AR14: graph/temporal verdicts use deterministic reviewed isolation fixtures because the dev DB contains smoke-test residue rather than a real reviewed graph/temporal corpus; production-corpus validation remains open
- AR13: connector scheduling remains an in-process poller under AR8's single-worker default; PostgreSQL leases prevent duplicate claims, but a dedicated external scheduler/worker is future production hardening
- AR13: live mailbox/archive connectors remain unimplemented; email ingestion is uploaded `.eml` with attachment handling
- AR12: feedback-derived eval cases land quarantined (`unreviewed`) and never gate until a human labels them; trend is per-eval-run, not yet per-corpus/profile
- AR11: cloud price-table values are illustrative defaults to tune; estimated token counts (no provider usage) are char-heuristic and flagged `est.`, directional not billing-grade; per-eval-report cost is future work
- AR10: the P0 health banner is on the `/console/admin/health` page; a global cross-page banner remains future polish (signal + endpoint exist)
- AR9: non-Ollama providers (OpenAI/Azure/vLLM/Anthropic) are validated against mocked transports only — no live keys in this environment; Ollama remains the sole end-to-end exercised path
- AR8: the app is single-process by design — it refuses `WEB_CONCURRENCY>1` unless `ALLOW_MULTI_WORKER=true`; making the queue/rate-limiter/model-singletons multi-worker safe remains future work (fenced, not yet solved)
- AR7: a dimension-changing embedding swap must go through `POST /admin/embedding/swap/*` (see `docs/runbooks/EMBEDDING_MODEL_SWAP.md`); direct activation is blocked and vector search degrades to keyword-only while a swap is mid-flight
- AR6 semantic cache: similarity matching is live but off unless a policy sets `match_mode=semantic`; default threshold 0.92 is precision-first and should be lowered (~0.80) for bge-base paraphrase recall — calibrate per corpus
- AR5 query transform calls the configured LLM; with `gpt-oss:20b-cloud` returning empty content for short prompts, transforms fall back to the original query (neutral eval delta) — a real generation model or AR9 provider abstraction is needed to realize a measurable gain
- AR4 enforcement defaults to `warn` in `APP_ENV=local` (set `TUNING_EVAL_ENFORCEMENT=require` to enforce locally); `require` is the default everywhere else
- M20–M30 DB-backed rerun closure is now covered by the green full suite; per-milestone manual closure notes remain open where flagged in `docs/milestones/`
- Rollback targets recorded before AR2 may reference legacy draft-named profiles; rolling back to them fails loudly by design (run `python -m app.db.repair_coherence`, then promote freshly)

## Canonical Reader Path

1. [README.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/README.md)
2. [docs/01_quickstart.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/01_quickstart.md)
3. [docs/04_repo_navigation_blueprint.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/04_repo_navigation_blueprint.md)
4. [docs/scenario_profiles_and_reuse_blueprint.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/scenario_profiles_and_reuse_blueprint.md)
5. [docs/03_Enterprise_RAG_Independent_Product_Audit_2026_06_11.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/03_Enterprise_RAG_Independent_Product_Audit_2026_06_11.md) — audit baseline
6. [docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md) — remediation plan

## Historical Detail

- Milestone history archive: [docs/project_state/milestone_history_archive.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/project_state/milestone_history_archive.md)
- Milestone implementation notes: `docs/milestones/`
- Imported baseline/reference docs: `docs/_master_docs/`, [docs/README_from_master.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/README_from_master.md)
