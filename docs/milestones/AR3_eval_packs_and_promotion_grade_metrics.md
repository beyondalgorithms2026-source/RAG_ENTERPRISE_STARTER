# AR3 — Eval Packs And Promotion-Grade Metrics

**Date:** 2026-06-12 · **Plan:** `docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md` · **Gate:** AR3 ("measurable" becomes true)

## What was built

- **Graded metrics** (`app/eval/metrics.py`): recall@k, MRR, nDCG@k over graded
  relevance maps ({chunk_id: grade 0–3}), citation-faithfulness for answer-level
  cases (truthful not-found scores 1.0 only when no labeled evidence exists),
  None-safe aggregation. Exact-value unit tests.
- **Pack builder** (`app/eval/pack_builder.py`, `python -m app.eval.pack_builder`):
  - *Synthetic chunk-grounded cases*: deterministic question variants
    (lead-sentence / heading-topic / salient-terms) from real corpus chunks;
    source chunk grade 3, same-source neighbors grade 1. `auto_labeled`, gate
    immediately. Lexical bias stated plainly: these catch ranking and
    candidate-pool regressions, not paraphrase weaknesses.
  - *Mined query-event cases*: junk-filtered real questions joined to trace
    `cited_chunk_ids`; born `unreviewed` and **never gate** until human review
    (labels derived from retrieval are circular).
- **Runner** (`app/eval/pack_eval.py`, `python -m app.eval.pack_eval`):
  per-mode (keyword/vector/hybrid) and per-provenance breakdowns, threshold
  gate over reviewed/auto-labeled hybrid-mode cases, report carrying the
  active-profile snapshot and effective retrieval config — the evidence object
  AR4 attaches to promotions. `--degraded` runs the negative control
  (hybrid_alpha 0, candidate pools of 1). `--cpu` forces CPU inference.
  Deterministic even-stride sampling keeps non-gate-mode breakdowns affordable.
- **Trace evidence for future mining**: `perform_ask` now records
  `cited_chunk_ids` into the retrieval trace (`app/core_rag/answering.py`).
- **Labeling workflow**: `docs/runbooks/EVAL_PACK_LABELING.md` (grades, review
  procedure for mined cases, threshold policy, honest limitations).

## Committed evidence (`backend/eval_packs/`)

- `pack_general.json` — **400 graded cases** over the flagship corpus (real
  uploaded documents, 2,025 chunks).
- `AR3_baseline_report.json` — live profile: **recall@5 0.504, recall@10 0.539,
  MRR 0.850, nDCG@10 0.766** → gate **pass**.
- `AR3_degraded_control_report.json` — degraded profile: **recall@5 0.242,
  MRR 0.718, nDCG@10 0.469** → gate **fail on both thresholds**.
- Gate thresholds calibrated from this first measured baseline minus a
  regression margin (recall@5 ≥ 0.45, MRR ≥ 0.78); the original a-priori guess
  (recall@5 ≥ 0.60) was wrong about this corpus and was replaced by the
  measured calibration, per the runbook's threshold policy.

## Findings made along the way (not softened)

- **The dev DB had zero embeddings.** `test_db_checks_report_index_and_keyword_readiness`
  ran migrations with a faked dimension (3) against the shared dev DB; MIG-P003's
  column realignment destroyed every stored embedding on each run. Fixed the
  test (no fake-dimension migrations) and re-embedded all 2,105 chunks.
- **The mined query data is test pollution.** All 443 `query_events` rows are
  smoke-test questions (`missing payroll policy <uuid>`, retention-redacted
  strings); after junk filtering, zero usable mined cases today. The audit's
  "176 events… raw material" framing was optimistic — the *mechanism* now
  exists, the *data* does not yet.
- **The named demo corpora are not evaluable.** legal/db_rows/transcripts
  contain 4–22-word test fragments; the builder skips them (packs appear
  automatically once real content exists). "100+ labeled cases per flagship
  corpus" is delivered for the one real corpus (400 cases); claiming packs for
  the fragment corpora would have been theater.
- **Sustained MPS (Metal) inference hangs.** The first baseline run stalled
  ~8.7 s/search and finally wedged in an uninterruptible GPU sync
  (`THPVariable_cpu`, metal gpu stream). On CPU the same searches run
  0.35–0.88 s. `--cpu` is the documented default recommendation for long eval
  runs on this hardware; the HNSW index was verified present (the slowness was
  GPU sync overhead, not a missing index).

## DoD check

- Baseline metric report on the current live profile committed ✓.
- Degraded-profile control demonstrably fails the gate the baseline passes ✓
  (also proven deterministically on a seeded corpus in
  `tests/test_eval_packs_ar3.py`, independent of dev-DB state).
- Re-run checks: AR3 module 10/10; full suite green (recorded in STATUS.md).

**Next:** AR4 — Close The Governance Loop: Eval Before Promotion.
