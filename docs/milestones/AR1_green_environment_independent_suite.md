# AR1 — Restore Green, Environment-Independent Regression Suite

**Date:** 2026-06-12 · **Plan:** `docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md` · **Gate:** AR1 (the gate works again)

## Starting state (re-measured 2026-06-12, matching the audit)

`python -m unittest discover -s tests`: **222 tests, 158 passed, 7 failures (later 6), 57 errors (later 59).**
- 55 errors: harness hardcoded 384-dim synthetic vectors vs `chunks.embedding vector(768)` (`expected 768 dimensions, not 384`).
- 4 contract breaks: `create_access_request()` signature drift; `KeyError: 'query_transform_enabled'` in tuning-draft lineage; `SELECT DISTINCT`/`ORDER BY` `InvalidColumnReference` in `repo_acl`; stale `app.api.ask._perform_ask_internal` reference (moved by M33).
- 6 failures: stale migration-plan list (P012 vs P020); env-coupled logger name; ACL-trimmed keyword searches returning empty; un-run queued reindex job; dev-mode login shadowing the OIDC redirect test; an eval fixture below the answer-quality threshold.
- The live retrieval profile was found to be `draft-965-retrieval` — the dev DB had drifted **again** since the audit recorded `draft-645-retrieval`, confirming AR2's premise.

## Root causes and fixes

### 1. Environment coupling removed from the harness (`backend/tests/smoke_test_base.py`)
- **Vector dimension** is now derived from the live `chunks.embedding` column (`expected_vector_dim()`/`basis_vector()`); all 52 hardcoded 384-dim vector constructions across 5 test files were replaced. The suite passes against any validly promoted embedding profile.
- **Runtime posture pinned per test**: `APP_ENV=local`, `AUTH_MODE=dev`, `ACCESS_STRATEGY=document_acl_with_time_bound_grants`, `AUTH_ENABLED=False`, and a dev-admin user context. Results no longer depend on the developer's `.env`.
- **Profiles pinned per test**: retrieval/reranker/LLM resolution is pinned to code-default profiles (embedding stays live to match the index). Tests exercising DB-backed activation opt out via `_unpin_test_profiles()`.
- **Active-profile snapshot/restore in tearDown**: tests that activate or promote profiles previously left the dev DB live configuration mutated — this is the mechanism that produced the audit's "unpromoted draft active as live" state. The harness now restores the pre-test active profiles unconditionally.
- **Connection-leak fix**: an unclosed `engine.connect()` in `test_smoke_baseline.py` held an idle-in-transaction lock that deadlocked mid-suite migrations (observed as a 30-minute hang against `CREATE TRIGGER`).

### 2. Genuine product fixes
- `app/db/repo_access_requests.py`: `source_hint`/`request_id`/`answer_path` default to `None`, restoring the pre-M16.1-compatible call contract.
- `app/db/repo_acl.py`: `ORDER BY` now uses the `granting_group` select alias (fixes `InvalidColumnReference` under `SELECT DISTINCT`).
- `app/api/admin.py` `_validated_retrieval_override`: lineage records exactly the keys the operator requested instead of a diff against the live profile's current values (was env-dependent and dropped `query_transform_enabled`).
- `app/api/admin.py` `set_active`: returns the normalized `get_live_configuration()` shape (`selected_profiles`) instead of raw `*_json` row keys.
- `app/core_rag/retrieval.py`: query transform now operates on the resolved query text — a caller-supplied `custom_query` is no longer clobbered by a transform of the original question.
- `app/core_rag/retrieval.py` `_resolve_mode`: only a *named* corpus policy owns the default mode; unlabeled sources respect the operator's `RETRIEVAL_MODE`.
- `app/core_rag/answering.py`: the documented `k_chunks` contract is enforced — rerank-enabled retrieval returning more than k candidates no longer inflates the answer context.
- `app/core/logging.py`: stable logger name (`rag_mm_master_poc`); was `getLogger(os.getenv("DATABASE_NAME"))`, i.e. the root logger when unset.

### 3. Migration ledger (now real)
- New `schema_migration_ledger` table; `run_migrations()` records every applied step and `verify_migration_ledger()` asserts ledger == plan at the end of every migration run, raising on drift.
- `test_migration_plan_exposes_ordered_patch_steps` updated to the full P001–P020 plan; new `test_migration_ledger_matches_plan_after_migrations` regression test.

### 4. Test corrections (stale expectations)
- `test_auth_local_dev`: patches `perform_ask` via the ask module (M33 moved `_perform_ask_internal` to `app.core_rag.answering`).
- m21 reindex test runs the queued job synchronously (`run_queued_ingestion_job`) — reindex returns `queued` by design; the in-process worker is not running under the test runner.
- m3 OIDC test pins `AUTH_MODE="oidc"` for the redirect assertion.
- m2 trace test authenticates as admin (admin endpoints correctly require auth since M23).
- m16.1 searches scoped to the test's own source (stale public leftovers from old aborted runs also matched the token) plus `addCleanup`.
- m17.b.2 pins a native-sampling LLM (`llama3_2_3b`) for the temperature-override assertion — `prompt_json_only` models force temperature 0.0 by design.
- m18 profile test opts out of profile pinning and no longer overwrites the `default` retrieval profile on exit.
- `ask_citation_sanitization` fixture mock answer lengthened above the 30-char `answer_too_short` quality threshold (was failing on any machine).

## Result

- Tuned dev DB (768-dim bge-base promoted, draft retrieval profile active): **224 tests, OK**.
- Fresh DB (`rag_ar1_fresh_check`, migrated from empty, 384-dim default profile): **224 tests, OK**.
- `make test` target added; M31/M32 doc hygiene suites green (21/21).
- Verified post-suite that the dev DB's active profiles are byte-identical to the pre-suite state even though tuning tests promoted drafts mid-run (harness snapshot/restore).
- Known remaining dev-DB incoherence (wrong registry dimension metadata; a pre-existing draft retrieval profile active as live) is **deliberately not repaired here** — that is AR2's data-repair deliverable with its own audit trail.

## DoD check
- Suite green on a freshly migrated empty DB **and** on a DB with an active 768-dim embedding profile: **both pass, 224/224**.
- Zero environment-caused errors; all 65 audit-run red tests accounted for above (fixed in product code, harness, tests, or fixtures — none retired).
- Migration ledger reconciled and asserted ledger == plan on every run.

**Next:** AR2 — Configuration Coherence Enforcement.
