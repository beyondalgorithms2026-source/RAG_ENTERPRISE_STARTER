# Repo Navigation Blueprint

This is the canonical repo map for Enterprise RAG Starter after M32.

If you only read one navigation document, read this one.

## Start Here

- `README.md`: canonical first-contact entrypoint
- `docs/01_quickstart.md`: local run path
- `STATUS.md`: current operational posture
- `docs/project_state/milestone_history_archive.md`: preserved milestone history

## Active Product Code

| Area | Canonical path | Why it matters |
|---|---|---|
| Backend entrypoint | `backend/app/main.py` | FastAPI app, middleware, startup wiring |
| Backend APIs | `backend/app/api/` | User/admin/control-plane routes |
| Retrieval core | `backend/app/core_rag/` | Search, answer, router, transform, compare |
| Auth + access | `backend/app/auth/`, `backend/app/db/repo_acl.py` | Identity, role, access strategy, SQL trimming |
| Frontend entrypoint | `web/app/` | Active Next.js UI |
| Frontend components | `web/components/` | Workspace/admin/public screens |

## Runbooks And Operator Docs

| Need | Canonical path |
|---|---|
| Local run flow | `docs/01_quickstart.md` |
| Deep local run/troubleshooting | `docs/runbooks/LOCALHOST_DEV_RUNBOOK.md` |
| Repo workflow | `docs/runbooks/SOURCE_CONTROL_WORKFLOW.md` |
| Safe extension path | `docs/runbooks/SAFE_EXTENSION_BLUEPRINT.md` |
| Subset product creation | `docs/runbooks/CREATE_SUBSET_PRODUCT_FROM_STARTER.md` |

## Scenario And Reuse Docs

| Need | Canonical path |
|---|---|
| Scenario selection | `docs/scenario_profiles_and_reuse_blueprint.md` |
| Scenario env/build packs | `scenarios/` |
| Access replacement | `docs/runbooks/REPLACE_ACCESS_STRATEGY.md` |
| Auth replacement | `docs/runbooks/REPLACE_AUTH_IMPLEMENTATION.md` |
| Admin module packaging | `docs/runbooks/DISABLE_ADVANCED_ADMIN_MODULES.md` |

## Current State And History

| Need | Canonical path |
|---|---|
| Current milestone snapshot | `STATUS.md` |
| Per-milestone implementation notes | `docs/milestones/` |
| Preserved historical archive | `docs/project_state/milestone_history_archive.md` |
| Project milestone plan | `docs/02_Enterprise_RAG_Project_Plan_Milestones.md` |

## Legacy And Reference-Only Areas

| Area | Path | Use it when |
|---|---|---|
| Legacy fallback UI | `frontend/` | You are explicitly validating `/frontend` compatibility |
| Imported baseline docs | `docs/_master_docs/` | You need provenance or deep baseline comparison |
| Imported baseline README | `docs/README_from_master.md` | You need copied-source historical context |
| Stitch design references | the original design reference (removed from this repository) | You are checking visual/source design provenance |

Do not start normal product work in those areas unless the task is explicitly about legacy compatibility or provenance.

## Reading Paths By Persona

### Engineer extending the product

1. `README.md`
2. `docs/04_repo_navigation_blueprint.md`
3. `docs/runbooks/SAFE_EXTENSION_BLUEPRINT.md`
4. `docs/scenario_profiles_and_reuse_blueprint.md`
5. `docs/02_architecture.md`

### Operator/admin running the product

1. `README.md`
2. `docs/01_quickstart.md`
3. `docs/runbooks/LOCALHOST_DEV_RUNBOOK.md`
4. `STATUS.md`

### Reviewer/auditor

1. `README.md`
2. `STATUS.md`
3. `docs/project_state/milestone_history_archive.md`
4. `docs/milestones/`

### Reuse team building a subset

1. `README.md`
2. `docs/scenario_profiles_and_reuse_blueprint.md`
3. `docs/runbooks/SAFE_EXTENSION_BLUEPRINT.md`
4. `scenarios/`

## Canonical Rule

If two docs appear to disagree:

1. `README.md` defines the first-contact path
2. `STATUS.md` defines current posture
3. `docs/04_repo_navigation_blueprint.md` defines canonical locations
4. runbooks define operational procedure
5. imported/reference-only docs are not authoritative for current repo behavior
