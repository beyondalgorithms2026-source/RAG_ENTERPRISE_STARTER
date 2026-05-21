# M17.2 — Enterprise Seed Pack, ACL Mapping, And Executive Access Baseline

- Added a reusable enterprise ACL seed pack under `backend/tests/fixtures/enterprise_acl/` covering users, groups, memberships, source inventory, ACL mappings, and source contacts.
- Added `python -m app.seed.enterprise_acl` plus `make seed-enterprise-acl` for idempotent local import of the seeded access environment.
- Expanded `/admin/access` from a read-only summary into a richer seeded-environment contract including source contacts, org edges, direct grants, and seed-pack readiness.
- Added admin ACL management endpoints for seed import, membership updates, source ACL updates, source contact updates, bulk assignment flows, and access explainability by user or source.
- Upgraded the admin Access page into a working operator surface for seeded ACL management while preserving the existing access-request routing and direct-grant workflow.
- Reused the existing local-dev identities where possible and extended the preset catalog with only the missing M17.2 roles (`restricted`, `observer`, `CEO`, `CFO`, and misuse-test user).
