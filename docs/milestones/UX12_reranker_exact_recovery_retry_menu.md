# UX12 — Reranker-Aware Exact Recovery And Retry Menu Polish

Completed on 2026-06-30.

Implemented additive retry search instructions, exact/numeric evidence boosting, and bounded cited repair so answer-bearing chunks below rerank position #1 can still recover safely. `custom_query` remains an override, while chat `Add details` sends `search_instruction`.

The answer action menu now appears below the action row, uses smaller controls, closes on outside click/Escape, and auto-dismisses after 4 seconds unless hovered or focused.

Verification:
- `PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_answer_strategy_auto_redo`
- `backend/.venv/bin/python -m compileall -q backend/app/core_rag backend/tests/test_answer_strategy_auto_redo.py`
- `npx tsc --noEmit`
- `npm run build`
- Full backend suite was run against local Postgres; 357 tests ran with 2 access-request failures that passed in isolated rerun, consistent with local suite-order/DB-state flake.
