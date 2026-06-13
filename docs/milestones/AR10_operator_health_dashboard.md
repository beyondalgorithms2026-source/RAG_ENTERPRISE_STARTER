# AR10 — Operator Health And Trust Dashboard (Gate AR10: incoherence is visible at a glance)

**Date:** 2026-06-13 · **Plan:** `docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md` · **Gate:** AR10

## Audit finding remediated

"The admin console shows what is configured but never whether the configuration
is self-consistent — the exact blind spot that let the dev environment rot.
Three live incoherences (wrong registry dimensions, draft profile active,
migration ledger mismatch) were invisible in the console; an operator had to
inspect the DB to find them, as the audit did. Health information existed only
as scattered per-feature views with no invariant-level rollup."

## What was built

- **One health aggregator** (`app/health.py::health_dashboard`) composing eight
  tiles into a single `{banner, p0_breached, p0_failures, tiles}` payload:
  - the five AR2/AR7 coherence invariants (`embedding_dimension`,
    `embedding_registry_metadata`, `active_profiles_promoted`,
    `migration_ledger`, `vector_serving`) — the **P0** set that drives the
    banner;
  - `reranker_warmup` — last warm-up status + staleness from `model_warmup_runs`;
  - `semantic_cache` — active policy, match mode, exact-vs-similarity hit counts;
  - `eval_gate` — last AR3 live baseline run pass/fail + last AR4 promotion
    evidence.
  Each tile is `{tile, status: pass|warn|fail, reason, details}`. The banner is
  `fail` if any tile fails, `warn` if any warns, else `pass`; `p0_breached`
  flags when a coherence invariant is the failure.
- **Endpoint** `GET /admin/health/dashboard` (overview admin module).
- **Console page + banner** (`web/app/console/admin/health/page.tsx`,
  `components/admin-health-panel.tsx`): a colored P0 banner plus a tile grid
  with per-invariant status dots and actionable reasons; "Health" added to the
  admin navigation.

## DoD check

- Injecting an AR2 incoherent state turns the corresponding tile red and
  breaches P0 ✓ — a real draft-named profile made active flips
  `active_profiles_promoted` to `fail`, sets `banner = fail` and
  `p0_breached = true` (`tests/test_health_dashboard_ar10.py`); a failed
  reranker warm-up flips its tile to `fail`.
- Healthy dev DB shows all P0 tiles green ✓ (banner may be `warn` only from
  operational tiles such as a missing baseline eval — P0 stays green).
- Re-run checks: dashboard endpoint contract test; full suite **292/292**;
  `tsc --noEmit` clean; `reader-clarity-check` 21/21; `docs/02` untouched.

## Honest limits

- The console banner lives on the Health page, not yet globally injected across
  every admin page (a shared layout banner is future polish; the P0 signal and
  endpoint exist for any page to consume).
- Tiles are point-in-time on load with a manual Refresh; no push/auto-poll.

**Next:** AR11 — Cost, Token, And Latency Governance.
