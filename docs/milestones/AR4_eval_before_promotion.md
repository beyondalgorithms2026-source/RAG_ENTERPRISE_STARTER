# AR4 — Close The Governance Loop: Eval Before Promotion

**Date:** 2026-06-13 · **Plan:** `docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md` · **Gate:** AR4 (promotion requires evidence)

## Audit finding remediated

"The single biggest missed integration in the product": sandbox compare and the
eval harness both existed, but `POST /admin/tuning/promote` accepted a
candidate with no eval result attached and promotion records stored no quality
evidence. Observed consequence: `draft-645-retrieval` live with no record of why.

## What was built

- **Persisted eval evidence** (`MIG-P021`): `tuning_eval_runs` table
  (`app/db/repo_eval_runs.py`) storing gate status, aggregates, thresholds,
  config fingerprint, selected profiles, and the slim report per run;
  `tuning_promotion_events.eval_evidence_json` column carries the evidence on
  every promote/rollback event.
- **"Run eval pack against candidate"** — `POST /admin/tuning/eval-runs`
  (rate-limited as expensive) executes AR3 packs under the draft's profile
  bundle via the sandbox-compare temporary-profile contexts and persists the
  run; `draft_id: null` evaluates the live configuration (the baseline runs
  candidate deltas are computed against). `GET /admin/tuning/eval-runs` lists
  runs. Pack addressing is by name inside `backend/eval_packs/` only — no
  caller-supplied paths. `gate_mode_sample` added to `run_pack_eval` so
  in-request evals stay affordable; committed baselines still run full packs.
- **Enforcement** (`app/eval/promotion_evidence.py`): `TUNING_EVAL_ENFORCEMENT`
  setting; default `require` outside local, `warn` in local. In `require`,
  promotion is rejected (422) when evidence is missing
  (`eval_evidence_required`), the gate failed (`eval_gate_failed`), the run is
  from another draft (`eval_run_draft_mismatch`), or the draft changed after
  the run (`stale_eval_run`). In `warn`, the promotion proceeds but the
  evidence object is annotated loudly (`promoted_without_eval`,
  `promoted_with_failed_eval_gate`, `promoted_with_stale_eval_run`) in the
  response, the promotion event, and the admin audit log.
- **Deltas:** candidate runs and promotion evidence carry
  `deltas_vs_live_baseline` (recall@5/10, MRR, nDCG@10) against the most
  recent persisted live baseline run.
- **Rollback:** never blocked on eval (it is the escape hatch), but accepts
  `eval_run_id` and links the justifying evidence into the rollback event.
- **Console** (`web/components/admin-profiles-panel.tsx`): "Run Eval Pack"
  action on the saved draft; gate status + live-vs-candidate deltas shown
  before promotion; promote button disabled on a failed gate; version-history
  detail shows the eval evidence recorded for each promotion; eval evidence is
  invalidated client-side when the draft changes.

## Honest limits

- Candidate-bundle application reuses the sandbox-compare module-level
  resolver monkeypatching — concurrency-unsafe (audit finding, AR8 scope).
- Candidates selecting a **different embedding profile** cannot be evaluated
  against the current index (different vector space); the eval-run endpoint
  rejects them (`blocked_embedding_scope`) — the AR7 lifecycle owns that path.
- Default candidate-eval sampling is 150 gate-mode cases; the committed AR3
  baselines remain full-pack runs.
- The live baseline used for deltas is the *latest* persisted live run; if the
  live config changed since, deltas are against a stale baseline (re-run the
  live eval to refresh; the report embeds the profile snapshot for audit).

## DoD check

- Promoting without an eval run is blocked in `require` mode and loudly
  annotated in `warn` mode ✓ (`tests/test_eval_promotion_ar4.py`).
- The AR3 degraded-profile control cannot be promoted in `require` mode ✓
  (gate fail on the seeded corpus → `eval_gate_failed`).
- Re-run checks: draft → eval → promote → rollback round-trip with persisted
  deltas ✓; full suite **249/249 OK**; `reader-clarity-check` 21/21;
  `docs/02_Enterprise_RAG_Project_Plan_Milestones.md` untouched.

**Next:** AR5 — Replace Placeholder Query Transformation With A Real Implementation.
