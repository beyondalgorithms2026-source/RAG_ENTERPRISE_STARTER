# Safe Extension Blueprint

This is the canonical extension path for teams building on Enterprise RAG Starter.

## Extend In This Order

1. Pick a scenario in `docs/scenario_profiles_and_reuse_blueprint.md`
2. Replace auth only if required
3. Replace access strategy only if required
4. Package or disable admin modules by scenario
5. Replace storage/connectors/providers
6. Change retrieval internals only after traces and evals are green

## Replace Points

### Auth

- Runtime/auth policy: `backend/app/auth/`
- API entrypoints: `backend/app/api/auth.py`
- Frontend auth-aware screens: `web/app/login/`, `web/components/`

Use:
- `docs/runbooks/REPLACE_AUTH_IMPLEMENTATION.md`

### Access

- Access strategies: `backend/app/auth/access_strategy.py`
- Access enforcement: `backend/app/auth/dependencies.py`
- SQL-level ACL and grants: `backend/app/db/repo_acl.py`

Use:
- `docs/runbooks/REPLACE_ACCESS_STRATEGY.md`

### Admin packaging

- Scenario-aware module rules: `backend/app/auth/admin_modules.py`
- Admin console routes/components: `web/app/console/admin/`, `web/components/admin-*.tsx`

Use:
- `docs/runbooks/DISABLE_ADVANCED_ADMIN_MODULES.md`

### Retrieval internals

- Search/answer/router/compare: `backend/app/core_rag/`
- SQL retrieval implementation: `backend/app/db/repo_search.py`
- Eval harnesses: `backend/app/eval/`

Do not change retrieval internals before:

- confirming the scenario path
- keeping citation behavior intact
- keeping SQL-level access trimming intact
- running scenario validation and retrieval smoke tests

## Rules

- Replace providers and packaging before replacing retrieval.
- Keep citations and SQL-level access checks green through every extension step.
- Treat `web/` as the active UI and `frontend/` as legacy fallback only.
- Use `README.md` and `docs/04_repo_navigation_blueprint.md` as the canonical navigation path while extending.
