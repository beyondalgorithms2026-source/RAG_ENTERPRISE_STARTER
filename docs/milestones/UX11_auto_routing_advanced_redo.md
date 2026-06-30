# UX11 — Auto Routing, Safe Structured Answers, And Advanced Redo

Completed 2026-06-30.

Implemented Auto as the default Ask/Search behavior by omitting explicit retrieval mode until a user selects an override. Returned methodology metadata now identifies mode source, selected route, strategy, and answer safety; the Ask top bar and Search summary show the selected methodology after results render.

Added a deterministic structured-answer strategy for spreadsheet aggregation questions. Simple complete-sheet `sum X by Y` questions compute from stored XLSX sheet parts with citation provenance; unsupported or partial spreadsheet evidence refuses safely instead of answering from retrieved snippets.

Separated answer feedback from retry. Thumbs-down now opens only the feedback issue form, while a separate three-dot answer action menu provides Try again and Add details in the same thread. Quick retry defaults to Fast recovery search; advanced Keyword retry is forced to Fast so it cannot silently run Strict/deep-research behavior. Redo attempts rerun Ask with selected mode/depth settings and log retry metadata for admin review without weakening the existing feedback-to-eval quarantine workflow.

Improved no-answer clarity and recovery. The Ask top bar now separates retrieved chunks from final citations, no-answer copy distinguishes "retrieved but uncited" from "no evidence retrieved", and retrieved-but-uncited false negatives get a conservative top-chunk repair pass that is accepted only when a valid citation is produced.

Verification:
- `cd backend && . .venv/bin/activate && python -m unittest tests.test_answer_strategy_auto_redo`
- `cd backend && . .venv/bin/activate && python -m compileall app tests/test_answer_strategy_auto_redo.py`
- `cd backend && . .venv/bin/activate && python -m unittest tests.test_smoke_admin_ops.SmokeTestAdminOps.test_m22_structured_negative_feedback_persists_and_lists_for_admin`
- `cd backend && . .venv/bin/activate && python -m unittest discover tests` — 354/354 green
- `cd web && ./node_modules/.bin/tsc --noEmit`
- `cd web && ./node_modules/.bin/next build`
