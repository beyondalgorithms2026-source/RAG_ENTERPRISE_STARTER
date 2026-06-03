# Create A Subset Product From Enterprise RAG Starter

1. Pick one scenario under `scenarios/`.
2. Copy its `backend.env.example` into `backend/.env` and adapt secrets/URLs.
3. Copy its `web.env.example` into `web/.env.local` if needed.
4. Run migrations and start the app with `make dev-web`.
5. Run the scenario validation suite with `make scenario-validate`.
6. Keep retrieval, citations, and SQL-level access tests green before removing any modules.

Do not delete code first. Disable modules with `SCENARIO_PROFILE` or `ADMIN_MODULES_ENABLED`, validate behavior, then remove unused modules only after the subset is stable.
