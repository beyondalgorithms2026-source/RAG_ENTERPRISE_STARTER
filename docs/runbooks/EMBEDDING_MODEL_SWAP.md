# Embedding Model / Index Swap Runbook (AR7)

Swapping the embedding model changes the vector space. If the new model's
dimension differs from `chunks.embedding`, the old index is incompatible and
vector search must not run against it. This runbook covers the managed,
resumable, verifiable swap path. **No manual SQL is required.**

## Why this exists

The single failure that disabled the regression suite (AR1) was an
embedding/index dimension drift: a 768-dim profile was activated against a
column the code assumed was 384-dim. Nothing blocked the activation, surfaced
the mismatch, or orchestrated the reindex. AR7 makes the transition a guided
state machine and hard-blocks vector search whenever the dimensions diverge.

## Guardrails now enforced

- **Direct activation is blocked.** `POST /admin/profiles/active` for an
  embedding profile whose declared dimension differs from the live index column
  returns `422 embedding_reindex_required`. Use the swap lifecycle instead.
- **Vector search degrades, never corrupts.** While the active embedding
  dimension ≠ the index dimension, `perform_search` forces keyword-only and
  records `degraded_vector` in the trace; deep research is suppressed. See
  `GET /admin/health/coherence` (`vector_serving` invariant) and
  `GET /admin/embedding/serving`.

## Swap procedure

1. **Plan** — `POST /admin/embedding/swap/plan {"target_profile_name": "..."}`.
   Validates the target profile declares its model's real output dimension and
   reports `requires_reindex`, `requires_column_resize`, and chunk counts.
2. **Begin** — `POST /admin/embedding/swap/begin {"target_profile_name": "..."}`
   (high-impact approval required). Creates a `planned` run. Only one swap may
   be in flight at a time.
3. **Run** — `POST /admin/embedding/swap/run {"run_id": N, "batch_limit": M}`.
   First call activates the target model, resizes the column if the dimension
   changed (dropping the old index and clearing now-incompatible vectors), then
   re-embeds pending chunks. **Resumable:** call repeatedly with a `batch_limit`
   to advance in increments and watch `embedded_chunks` climb toward
   `total_chunks`. When all chunks are embedded the vector index is rebuilt and
   the run moves to `verifying`.
4. **Verify** — `POST /admin/embedding/swap/verify {"run_id": N}`. Reconciles
   counts (every non-empty chunk embedded) and runs a sampled self-similarity
   check (re-embedding a chunk's own text must score ~1.0 cosine against its
   stored vector). On success the run is `completed`; otherwise `failed` with a
   reason (`counts_reconciliation_failed` / `sample_distance_check_failed`).
5. **Abort** — `POST /admin/embedding/swap/abort {"run_id": N, "reason": "..."}`
   marks an in-flight run `aborted`. (Re-run a fresh swap to recover; vector
   search stays degraded until a swap completes.)

Status and history: `GET /admin/embedding/swaps`, `GET /admin/embedding/serving`.

## State machine

```
planned ──run──> reindexing ──(all embedded)──> verifying ──verify──> completed
   │                  │                              │
   └──abort──> aborted└──abort──> aborted            └──verify(fail)──> failed
```

## Operational notes

- During `reindexing` the system answers in keyword-only mode with an operator
  banner — expected, not an outage. Communicate the window before starting on a
  large corpus.
- Re-embedding a large corpus is the slow step; use `batch_limit` to pace it and
  to keep each request bounded. On Apple Silicon, prefer CPU inference for long
  batches (sustained MPS runs were observed to hang — see the AR3 note).
- A same-dimension model swap still re-embeds every chunk (the old vectors came
  from the old model) but skips the column resize.
- The lifecycle uses `set_active_profile` directly; it is the *only* sanctioned
  way to bring a dimension-changing embedding profile live.
