# STATUS.md — Operational Snapshot

**Last completed M-series milestone:** M33 — Governed Semantic Cache Policies, Scoped Enablement, And User Refresh  
**Active work track:** AR-series (Audit Remediation)  
**Current AR milestone:** AR4 — Close The Governance Loop: Eval Before Promotion (AR0–AR3 closed 2026-06-12)

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
| AR4 — Eval Before Promotion | Not started | P0 — wire eval into promotion path |
| AR5 — Real Query Transform | Not started | P1 — LLM-backed rewrite/HyDE behind existing flags |
| AR6 — Truthful Cache Naming | Not started | P1 — rename or implement semantic matching |
| AR7 — Embedding Lifecycle | Not started | P1 — guided reindex, block mismatched states |
| AR8 — Deployment Portability | Not started | P1 — fresh-machine quickstart, concurrency safety |
| AR9 — Provider Abstraction | Not started | P1 — OpenAI-compatible client interface |
| AR10 — Health Dashboard | Not started | P1 — operator coherence page |
| AR11 — Cost/Token Governance | Not started | P2 |
| AR12 — Feedback→Eval Flywheel | Not started | P2 |
| AR13 — Connector Operations | Not started | P2 |
| AR14 — Retrieval Enhancements | Not started | P2 — only with eval-proven gains |

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

- **Test suite is green (AR1/AR2):** `make test` — 232/232 on the dev DB; AR1 verified 224/224 on a freshly migrated empty DB as well
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
