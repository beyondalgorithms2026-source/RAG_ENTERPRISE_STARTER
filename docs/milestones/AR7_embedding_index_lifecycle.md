# AR7 — Embedding And Index Lifecycle Management (Gate AR7: model swaps cannot corrupt the index)

**Date:** 2026-06-13 · **Plan:** `docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md` · **Gate:** AR7

## Audit finding remediated

The single failure that disabled the regression suite (AR1) was an
embedding/index dimension drift: "A 768-dim profile was activated against an
index that the test harness (and earlier code) assumed was 384-dim; nothing
blocked the activation, surfaced the mismatch, or orchestrated the reindex …
The only embedding-swap guard lived inside sandbox compare
(`blocked_embedding_scope` warning) — not in the activation path actually used.
Reindex existed only as a per-source admin action and script; no corpus-wide
guided flow, progress reporting, or completion verification."

## What was built

- **Managed swap lifecycle** (`app/embedding/lifecycle.py`, `MIG-P023`
  `embedding_swap_runs`): a persisted state machine
  `planned → reindexing → verifying → completed` (+ `aborted`/`failed`).
  - `plan_embedding_swap` validates the target profile declares its model's
    real output dimension and reports `requires_reindex` /
    `requires_column_resize` / chunk counts (pure read).
  - `begin_embedding_swap` creates a run and refuses a second concurrent swap.
  - `run_embedding_swap` activates the target model, resizes the column when the
    dimension changes (drops the old index, clears incompatible vectors),
    re-embeds pending chunks, and is **resumable** via `batch_limit` (progress
    tracked in `embedded_chunks`/`total_chunks`); rebuilds the index and moves
    to `verifying` once every chunk is embedded.
  - `verify_embedding_swap` does counts reconciliation **plus** a sampled
    self-similarity check (a chunk re-embedded from its own text must score
    ~1.0 cosine vs its stored vector) before declaring `completed`.
  - `abort_embedding_swap` stops an in-flight run.
- **Hard block on serving vector search under mismatch**
  (`app/coherence.py::vector_serving_state` + retrieval): when the active
  embedding dimension ≠ the index column, `perform_search` forces keyword-only,
  records `degraded_vector` in the trace, and suppresses deep research — instead
  of erroring or returning corrupt neighbours. Exposed as the new
  `vector_serving` coherence invariant and `GET /admin/embedding/serving`.
- **Activation guard** (`POST /admin/profiles/active`): a dimension-changing
  embedding activation is rejected with `422 embedding_reindex_required` and
  pointed at the swap lifecycle, which is the only sanctioned path to bring such
  a profile live.
- **Endpoints**: `POST /admin/embedding/swap/{plan,begin,run,verify,abort}`,
  `GET /admin/embedding/swaps`, `GET /admin/embedding/serving`.
- **Runbook**: `docs/runbooks/EMBEDDING_MODEL_SWAP.md`.

## DoD check

- Mismatch states are unreachable through the API ✓ — direct dimension-changing
  activation is blocked; vector search degrades rather than corrupts
  (`tests/test_embedding_lifecycle_ar7.py`: serving-state detection, keyword
  downgrade with deep-research suppression, activation 422).
- End-to-end swap completes without manual SQL ✓ — plan → begin → run
  (resumable batches) → verify → completed, proven via the state-machine tests
  (heavy steps stubbed so no real corpus is re-embedded in CI) and documented
  for live ≥1k-chunk operation in the runbook.
- Re-run checks: AR2 coherence still green with the added invariant; full suite
  **273/273**; `docs/02` untouched; ledger `MIG-P001..P023` reconciled.

## Honest limits

- The automated tests drive the state machine with the column-resize,
  re-embed, and index-rebuild steps stubbed — re-embedding a real ≥1k corpus in
  CI is impractical and would mutate the shared dev DB (the AR3 incident). The
  real heavy steps are exercised manually per the runbook; the *contract*
  (transitions, resumability, verification, guards) is covered automatically.
- Abort does not auto-revert a partially resized column; recovery is a fresh
  swap, and vector search stays correctly degraded until one completes.

**Next:** AR8 — Deployment Portability And Multi-Worker Safety.
