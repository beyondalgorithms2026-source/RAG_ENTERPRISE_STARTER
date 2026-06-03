## M31: Repository Hygiene, Canonical Paths, And Safe Source Control Workflow

- Stopped tracking local-only and transient repo noise by de-tracking `web/.env.local`, `web/tsconfig.tsbuildinfo`, and the root-level retrieval eval report.
- Moved default eval and benchmark report outputs under ignored `data/reports/` so local runs no longer inflate branch diffs.
- Documented canonical active paths: `backend/` and `web/` are active, `frontend/` is legacy fallback only, and imported baseline docs under `docs/_master_docs/` plus `docs/README_from_master.md` are reference-only.
- Added a dedicated source-control workflow runbook covering branch naming, tag naming, PR base expectations, and rules for generated artifacts versus intentionally committed audit proof.
- Added focused M31 regression coverage and a lightweight `make repo-hygiene-check` command.
