# Eval Pack Labeling Workflow (AR3)

This is the workflow that keeps eval packs growing and trustworthy. It exists
because the audit found evaluation "structurally thin" (~28 keyword-containment
cases) — and because auto-generated cases alone cannot measure paraphrase
robustness.

## Pack anatomy

Packs live in `backend/eval_packs/pack_<name>.json`. Each case:

```json
{
  "id": "syn-1234-lead_sentence",
  "question": "…",
  "provenance": "synthetic_chunk_grounded | mined_query_event | human_labeled",
  "review_status": "auto_labeled | unreviewed | reviewed",
  "relevant": {"<chunk_id>": 3, "<neighbor_chunk_id>": 1}
}
```

Grades: 3 = directly answers, 2 = strong supporting evidence, 1 = related
context, 0/absent = irrelevant.

## How cases are born

1. **Synthetic chunk-grounded** (`python -m app.eval.pack_builder`): question
   variants derived from real chunks; the source chunk is graded 3, neighbors 1.
   These are `auto_labeled` and gate immediately. Known bias, stated plainly:
   they share vocabulary with their chunk, so they catch ranking/candidate-pool
   regressions but **not** paraphrase weaknesses.
2. **Mined query events**: real user questions joined to their trace's
   `cited_chunk_ids` (recorded since AR3). Born `unreviewed` — they are
   reported but NEVER gate until a human reviews them, because trace-derived
   labels are circular (they reflect what retrieval already did).
3. **Human labeled**: the only source of paraphrase-robust cases. Write the
   question as a user would ask it, then label relevant chunks found by
   reading the source documents — not by running retrieval.

## Review procedure (mined → reviewed)

1. Open the pack file; find cases with `"review_status": "unreviewed"`.
2. For each: read the question, locate the actual evidence chunks (admin
   trace viewer or source browser), correct the `relevant` map and grades.
3. Set `review_status: "reviewed"`. Reviewed cases gate from the next run.
4. Commit the pack change with a note naming who reviewed it.

## Running evaluation

- Baseline: `python -m app.eval.pack_eval --out backend/eval_packs/AR3_baseline_report.json`
- Negative control: `python -m app.eval.pack_eval --degraded` — must FAIL the
  gate; if it passes, the pack has lost discriminative power: add cases.
- Gate thresholds live in `app/eval/pack_eval.py::DEFAULT_THRESHOLDS`, set
  from the committed baseline minus a regression margin. Raise them as the
  baseline improves; never lower them to make a candidate pass.

## Honest limitations (current dev DB)

- The named demo corpora (legal/db_rows/transcripts) contain 4–22-word test
  fragments, not documents; packs for them are skipped until real content
  exists. The flagship pack is `general` (real uploaded documents).
- The 443 mined query events are almost entirely smoke-test pollution and
  yield no usable cases after junk filtering. Mined seeding becomes useful
  once real users generate traffic (and traces now record `cited_chunk_ids`).
- Case `chunk_id` labels are database-specific; packs must be rebuilt (or
  re-labeled) after re-ingestion that changes chunk identity.
