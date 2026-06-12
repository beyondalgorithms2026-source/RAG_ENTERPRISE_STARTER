# AR2 — Configuration Coherence Enforcement

**Date:** 2026-06-12 · **Plan:** `docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md` · **Gate:** AR2 (incoherent states are rejected or loudly visible)

## Audit states addressed

Live dev-DB inspection (re-verified at AR2 start) showed all three audit states still present — one had even regressed further:
1. **Wrong registry metadata:** `bge-small-en-v1_5` *and* `default` embedding profiles declared dimension 768; `BAAI/bge-small-en-v1.5` produces 384.
2. **Draft active as live:** active retrieval profile was `draft-1036-retrieval` (the audit had recorded `draft-645-retrieval`; the dev DB drifted twice more before AR1's harness snapshot/restore stopped suite-induced drift).
3. **Migration ledger:** already reconciled and asserted by AR1 (`schema_migration_ledger`, `verify_migration_ledger()`); AR2 adds it to the health surface.

## What was built

### Invariant module — `backend/app/coherence.py` (new)
- `check_embedding_dimension` — active profile's declared dimension vs the actual `chunks.embedding` column (and vs real model output in deep mode).
- `check_embedding_registry_metadata` — every embedding registry row's declared dimension vs its model's actual output (deep mode loads models; shallow mode checks already-probed models).
- `check_active_profiles_promoted` — no active profile may carry a `draft-` name.
- `check_migration_ledger` — ledger == plan.
- `run_coherence_checks(deep=...)` — per-invariant pass/fail with machine-readable reasons.
- `enforce_startup_coherence()` — warn in `local`/`dev`, **refuse to start** elsewhere.

### Write-time enforcement (states become impossible through the API)
- `POST/PATCH /admin/profiles` (embedding): declared dimension is validated against the loaded model's actual output; mismatch → 422 `embedding_dimension_mismatch` (`app/api/admin.py::_enforce_embedding_dimension_coherence`).
- `POST /admin/profiles/active`: `draft-*` names → 422 `draft_profile_activation_blocked`.
- `app/db/repo_profiles.py::set_active_profile`: raises on `draft-*` names — deep enforcement below the API, so no internal path can activate a draft either.
- **Promotion rename:** `promote_candidate_to_live` previously created live retrieval profiles named `{draft-label}-retrieval` — this was the exact mechanism that put draft-named profiles live. Promoted profiles are now named `promoted-{draft_id}-retrieval`.

### Visibility
- `GET /admin/health/coherence` (admin-gated, `?deep=true` for model-load verification) returning per-invariant pass/fail + reasons — the AR10 dashboard's data source.
- Startup hook in `app/main.py` after migrations: incoherence is logged loudly in local/dev and blocks boot in staging/prod.

### Data repair — `python -m app.db.repair_coherence` (new), executed on the dev DB
- `default` and `bge-small-en-v1_5` dimensions corrected 768 → 384 (audit-logged as `coherence.repair.embedding_dimension`).
- `draft-1036-retrieval` re-registered as `promoted-repair-1036-retrieval` and activated (audit-logged as `coherence.repair.draft_active_profile`); resolver cache invalidated; live configuration record re-synced.
- Post-repair deep check: **all four invariants pass** on the dev DB.

## DoD check
- Each audit state reproduced in `backend/tests/test_coherence_ar2.py` and (a) rejected at write time (422 / ValueError), and (b) flagged by `/admin/health/coherence` when injected directly into the DB — 8/8 tests green.
- Startup enforcement tested: warn-and-continue in `local`, RuntimeError in `prod`.
- Known limitation, stated plainly: rollback targets recorded *before* AR2 may reference legacy draft-named profiles; rolling back to them now fails loudly at `set_active_profile` instead of silently reinstating a draft — run the repair script, then promote freshly.

## Re-run checks
- New coherence module green (8/8).
- Full suite green (AR1 invariant) — recorded in STATUS.md at closure.
- Manual: deep health check all-green on the repaired dev DB.

**Next:** AR3 — Eval Packs And Promotion-Grade Metrics.
