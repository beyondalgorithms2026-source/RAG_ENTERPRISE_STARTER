# M17.b.3 — Draft Promotion, Rollback, Embedding Safety, And Warm-Up

Implemented governed tuning rollout controls for candidate drafts.

- Added promotion history, rollback events, and audited promote/rollback APIs.
- Added explicit embedding experiment safety gates with locked `selected_5_files` scope or full-corpus reindex job creation for `all_files`.
- Added model warm-up recording for embedding and reranker candidates.
- Updated the tuning lab UI with promotion note, real promote action, version history, rollback controls, and operator guardrails.
- Added smoke coverage for promotion, rollback, embedding warning/scope locking, full reindex job creation, and warm-up records.

