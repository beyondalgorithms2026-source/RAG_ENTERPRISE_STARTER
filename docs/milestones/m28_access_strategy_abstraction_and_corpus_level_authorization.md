# M28 - Access Strategy Abstraction And Corpus-Level Authorization

## Summary
- Added `ACCESS_STRATEGY` with explicit strategy options: `none`, `employee_all`, `corpus_level`, `document_acl`, and `document_acl_with_time_bound_grants`.
- Preserved the existing enterprise ACL behavior as the default strategy.
- Added `corpus_access_grants` for SQL-level corpus authorization.
- Centralized source access SQL in `app/auth/access_strategy.py`.
- Applied the shared strategy to retrieval, chunk-id materialization, source listing, file/context access, and semantic cache reauthorization.
- Updated the M27 reuse blueprint to mark corpus-level and employee-wide access strategies as implemented while keeping password login as future work.

## Verification
- Added focused coverage in `backend/tests/test_access_strategy_m28.py`.
- Re-run baseline, M23-M27, ACL leak, and direct-grant checks before marking complete.

