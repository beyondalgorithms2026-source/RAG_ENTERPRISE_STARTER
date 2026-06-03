# Enterprise RAG Starter

Enterprise RAG Starter is a reusable internal-assistant foundation built around grounded retrieval, citations, access control, admin operations, and scenario-based reuse. It is strongest today as a PoC-grade but security-aware hybrid retrieval system that teams can extend into employee-wide, corpus-level, trusted no-auth, or enterprise OIDC + ACL deployments.

## Start Here

If you are new to this repo, read in this order:

1. [docs/01_quickstart.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/01_quickstart.md)
2. [STATUS.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/STATUS.md)
3. [docs/04_repo_navigation_blueprint.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/04_repo_navigation_blueprint.md)
4. [docs/scenario_profiles_and_reuse_blueprint.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/scenario_profiles_and_reuse_blueprint.md)
5. [docs/runbooks/SAFE_EXTENSION_BLUEPRINT.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/runbooks/SAFE_EXTENSION_BLUEPRINT.md)

Those five documents answer the four core onboarding questions:

- What is this repo?
- How do I run it?
- What is the current status?
- Which areas are canonical?

## What This Repo Is

- A backend-and-console starter for grounded RAG with citations, admin control, feedback capture, governance, and scenario reuse.
- A modular codebase where auth, access strategy, admin packaging, and scenario setup can be changed without rewriting the full retrieval engine first.
- A repo intended for internal assistants and controlled enterprise pilots, not a browser-only demo or turnkey SaaS product.

## How To Run It

Use the canonical local run path in [docs/01_quickstart.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/01_quickstart.md).

Short version:

```bash
cd /Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER
docker compose up -d
make dev-web
```

Use `docs/01_quickstart.md` for env setup, Ollama, local accounts, and troubleshooting.

## Current Status

- Current milestone: M32 reader clarity and onboarding reshaping
- Strongest implemented runtime scenario: enterprise-style OIDC/dev identity plus SQL-level access trimming and admin governance
- Pending verification debt: DB-backed reruns from M17.b.3 onward remain open

Read the operational snapshot in [STATUS.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/STATUS.md).
Read preserved historical detail in [docs/project_state/milestone_history_archive.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/project_state/milestone_history_archive.md).

## Canonical Paths

- Active backend: `backend/`
- Active frontend: `web/`
- Legacy fallback UI: `frontend/`
- Generated local reports: `data/reports/`
- Scenario packs: `scenarios/`
- Runbooks: `docs/runbooks/`
- Milestone notes: `docs/milestones/`
- Historical archive: `docs/project_state/`
- Imported/reference-only baseline docs: `docs/_master_docs/`, `docs/README_from_master.md`

`web/` is the active product UI. `frontend/` remains mounted at `/frontend` only as a legacy compatibility fallback.

## Reader Paths By Persona

- Engineer extending the product: start with [docs/04_repo_navigation_blueprint.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/04_repo_navigation_blueprint.md) and [docs/runbooks/SAFE_EXTENSION_BLUEPRINT.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/runbooks/SAFE_EXTENSION_BLUEPRINT.md)
- Operator/admin running the product: start with [docs/01_quickstart.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/01_quickstart.md) and [docs/runbooks/LOCALHOST_DEV_RUNBOOK.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/runbooks/LOCALHOST_DEV_RUNBOOK.md)
- Reviewer/auditor: start with [STATUS.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/STATUS.md), [docs/project_state/milestone_history_archive.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/project_state/milestone_history_archive.md), and `docs/milestones/`
- Team reusing the starter for a subset scenario: start with [docs/scenario_profiles_and_reuse_blueprint.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/scenario_profiles_and_reuse_blueprint.md) and `scenarios/`

## Safe Extension Guidance

Do not change retrieval internals first. Replace in this order unless you have a strong reason not to:

1. auth/provider setup
2. access strategy
3. admin module packaging
4. scenario env/build pack
5. connectors/storage/runtime providers
6. retrieval internals

Use [docs/runbooks/SAFE_EXTENSION_BLUEPRINT.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/runbooks/SAFE_EXTENSION_BLUEPRINT.md) for the extension path and replacement points.

## Repo Workflow

Canonical git workflow guidance lives in [docs/runbooks/SOURCE_CONTROL_WORKFLOW.md](/Users/Work/Projects/repos/RAG_ENTERPRISE_STARTER/docs/runbooks/SOURCE_CONTROL_WORKFLOW.md).

Key rules:

- Use the intended long-lived dev branch for milestone continuation.
- Compare branches against the correct base branch before interpreting diff counts.
- Keep sample env and curated proof artifacts only; local env/build/report noise stays out of git.
