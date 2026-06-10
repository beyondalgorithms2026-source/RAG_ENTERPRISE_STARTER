# M33: Governed Semantic Cache Policies, Scoped Enablement, And User Refresh

- Added independent semantic-cache policy, version, event, and revision storage.
- Kept global cache posture off unless an approved policy with an explicit corpus, ACL-group, or exact-question scope is activated.
- Added deterministic allow/deny eligibility, citation/access reauthorization, versioned namespaces, capacity and TTL controls, and revision-based invalidation.
- Added separate draft, scoped check, activation, disable, rollback, metrics, and active-entry clearing APIs.
- Kept cache policy outside retrieval profiles, sandbox candidates, compare, save, promotion, and retrieval rollback.
- Added a dedicated admin cache-governance route and a read-only cache posture summary on the Profiles page.
- Added cached-answer age, source/access validation, and explicit user refresh with answer/citation difference recording.
- Updated `/ask/stream` to use the same governed cache path as `/ask`.
- Added M33 policy, scope precedence, namespace isolation, revision invalidation, and tuning-independence tests.

## Verification

- `cd backend && .venv/bin/python -m app.db.migrate`
- `cd backend && .venv/bin/python -m unittest tests.test_semantic_cache_governance_m33`
- Relevant M17-M19 promotion, rollback, sandbox compare, and semantic-cache regression tests
- `cd web && pnpm exec tsc --noEmit`
- Python compile checks and `git diff --check`

`pnpm run lint` remains unavailable because the repository has no committed ESLint configuration and Next.js opens an interactive setup prompt.

The full historical `tests.test_smoke_baseline` pack was also rerun. Its focused M33-adjacent paths pass, while the aggregate pack retains pre-existing cross-test database state failures and stale assertions, including a migration-plan expectation that stops at `MIG-P012`.
