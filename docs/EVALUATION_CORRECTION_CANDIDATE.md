# Evaluation correction candidate — not released

Both `ANSWER_CONTEXT_SELECTION_ENABLED` and `ANSWER_PROMPT_CANDIDATE` default
to false. Existing active prompt history, total context budget, model, embeddings,
SQL authorization and public API shapes are preserved. Candidate prompt 1.2.1
is immutable and hash-checked, separately from active 1.1.

Candidate changes select diverse authorized evidence, suppress duplicates,
preserve complete bounded excerpt units, continue after oversized candidates,
and record context inclusion/exclusion decisions. Compound/definition questions
may search ten authorized candidates but select at most six context blocks.
No evaluation case ID or expected answer is used in production.

The real STARTER-only runner is `backend/app/eval/correction_candidate.py`.
It refuses shared or hosted databases and requires a localhost `b004_eval_*`
database before provisioning. Do not point it at Supabase. Reports contain
synthetic evidence and context but exclude credentials, raw prompts and paths.
The APP offline evaluator can regrade these reports without database credentials.

On 2026-09-15, 90 real candidate answers and matched 36-case current/candidate
diagnostics completed. Separate real SQL ACL controls passed both employee denial
and HR authorized retrieval. Offline tests discovered 93 cases: 57 passed and
36 skipped. Reader-clarity tests passed 21; repository hygiene passed.

Measured 36-case p95 decreased 29.95%; average input tokens increased 5.26%.
These are diagnostic measurements, not production guarantees or full-stack proof.

The preceding candidate remains blocked: OM-044 could miscompare four minutes with a trigger of
more than five, despite correct evidence in context. OM-089 can omit Section
5.5.1 despite its presence in context. OM-046 has not met every-run completeness
requirements. Do not enable these flags in deployed visitor traffic or promote
a revised baseline yet.

Canonical source-contract ledger, progress and proposed separately reviewed
numeric repair design are in the APP repository's `docs/EVALUATION_CORRECTION_*`
and `docs/NUMERIC_CLAIM_REPAIR_REVIEW.md`. The approved v1 gate is unchanged;
MCP is unchanged. Calibration is intentionally not repeated while a known
safety blocker exists.

The approved bounded numeric repair is now implemented as a separate disabled
candidate; see `NUMERIC_CLAIM_REPAIR.md` for current targeted results and remaining
performance/calibration requirements. This does not resolve OM-089 or approve v2.
