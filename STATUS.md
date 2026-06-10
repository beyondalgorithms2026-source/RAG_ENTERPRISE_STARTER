# STATUS.md — Operational Snapshot

**Current Milestone:** M33 — Governed Semantic Cache Policies, Scoped Enablement, And User Refresh

## Current Repo Posture

- Active backend: `backend/`
- Active frontend: `web/`
- Legacy fallback UI: `frontend/`
- Strongest implemented runtime scenario: enterprise-style OIDC/dev identity with SQL-level access trimming, admin governance, and scenario packaging
- M18 operability now includes admin retrieval-profile transform controls plus sandbox compare visibility for retrieval transform posture
- Sandbox tuning now supports inline query-transform overrides that promote into explicit live retrieval-profile settings
- Semantic cache governance is independent from retrieval tuning, globally off by default, and activatable only for explicit corpus, ACL-group, or exact-question scopes
- Cached answers are exact-query, ACL/profile/revision validated, version-namespaced, and user-refreshable

## Completed Milestones

- M0 through M17.b.2
- M17.b.3: Manual testing completed
- M18: Manual testing completed
- M19: Manual testing completed
- M31: Repository Hygiene, Canonical Paths, And Safe Source Control Workflow
- M32: Reader Clarity, Onboarding Contract, And Canonical Navigation Blueprint
- M33: Governed Semantic Cache Policies, Scoped Enablement, And User Refresh

## Implemented / Pending DB-backed Re-run Checks

- M20
- M21
- M22
- M23
- M24
- M25
- M26
- M27
- M28
- M29
- M30

## Current Verification Debt

- DB-backed reruns and manual closure from M20 onward are still pending
- Local Postgres-backed validation remains the main open closure item for M20 through M30
- Full historical-suite reruns remain broader than the focused M33 and M17-M19 regression checks completed for Gate 33

## Canonical Reader Path

Start here in this order:

1. [README.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/README.md)
2. [docs/01_quickstart.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/01_quickstart.md)
3. [docs/04_repo_navigation_blueprint.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/04_repo_navigation_blueprint.md)
4. [docs/scenario_profiles_and_reuse_blueprint.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/scenario_profiles_and_reuse_blueprint.md)

## Historical Detail

- Milestone history archive: [docs/project_state/milestone_history_archive.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/project_state/milestone_history_archive.md)
- Milestone implementation notes: `docs/milestones/`
- Imported baseline/reference docs: `docs/_master_docs/`, [docs/README_from_master.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/README_from_master.md)
