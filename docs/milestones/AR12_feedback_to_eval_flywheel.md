# AR12 — Feedback-To-Eval Flywheel (Gate AR12: operational data becomes regression protection)

**Date:** 2026-06-13 · **Plan:** `docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md` · **Gate:** AR12

## Audit finding remediated

"423 traces, 176 query events, and 101 structured feedback rows existed in the
dev DB; `query_failure_clusters` and `derived_eval_packs` tables and endpoints
existed (M20/M22) — but there was no path from a thumbs-down cluster or
`missing_evidence` event to an eval case, and no trend reporting on pack pass
rates." The audit named this the repo's most credible path to durable
differentiation — open, with all ingredients present and none connected.

## What was built

- **Cluster → quarantined eval case** (`app/eval/feedback_flywheel.py`):
  - `propose_cases_from_cluster(cluster_id)` turns a failure cluster's questions
    into candidate AR3 cases, prefilling a graded relevance map from the
    question's recorded trace evidence (`cited_chunk_ids` → grade 2) and flagging
    `needs_label` when no evidence exists. Provenance `feedback_derived`,
    `review_status="unreviewed"`.
  - `append_cases_to_pack(pack_name, cases)` writes them into a real AR3 pack
    file (`backend/eval_packs/pack_*.json`), deduped by normalized question,
    always as **unreviewed** — the quarantine guardrail.
- **Human review → gating** (`review_pack_case`): labels a case's relevance map
  and flips it to `reviewed`; a reviewed case must carry a non-empty graded map.
  Reviewed cases gate the next run; the AR3 gate already excludes `unreviewed`,
  so noisy feedback cannot poison the gate before a human looks at it.
- **Pass-rate trend** (`pack_passrate_trend`): reads the AR4 eval-run history
  (`tuning_eval_runs`) into a time series with per-run gate status, headline
  metrics, and a cumulative pass rate.
- **Endpoints**: `POST /admin/feedback-eval/{propose,append,review}`,
  `GET /admin/feedback-eval/{quarantine,trend}` (governance module).
- **Console**: `/console/admin/flywheel` — propose from a cluster, append
  (quarantined), inspect quarantine, and read the pass-rate trend table.

## DoD check

- A real thumbs-down event travels the full path into a pack and is exercised by
  the next eval run ✓ — `tests/test_feedback_flywheel_ar12.py` seeds a
  `not_helpful` event + cited-chunk trace, builds the failure cluster, proposes a
  case (evidence prefilled), appends it (quarantined — `gating_case_count == 0`),
  reviews + labels it, and re-runs `run_pack_eval` where it now gates
  (`gating_case_count == 1`, the case id present in the gating set).
- Quarantine guardrail proven (a reviewed case without a relevance map is
  rejected); pass-rate trend reads the eval-run history.
- Re-run checks: full suite **305/305**; `tsc --noEmit` clean;
  `reader-clarity-check` 21/21; `docs/02` untouched. No new migration — reuses
  M20/M22 mining tables and AR4 `tuning_eval_runs`.

## Honest limits

- Evidence prefill is only as good as the recorded trace: `no_evidence` /
  not-found events have no cited chunks, so those cases land `needs_label=true`
  and require a human to read the sources and grade them — by design, not a gap.
- The trend is per-eval-run (gate status over time), not yet sliced per
  corpus/profile; the run records carry the active-profile snapshot for a future
  per-profile breakdown.
- The legacy `derived_eval_packs` table (M22) is left intact; AR12 writes to AR3
  pack files, which are what `pack_eval` actually gates on.

**Next:** AR13 — Connector Operations And Source Freshness.
