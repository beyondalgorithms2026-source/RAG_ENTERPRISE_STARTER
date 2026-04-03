# Codex Project Snapshot: RAG_ENTERPRISE_STARTER

Generated: 2026-04-03T14:09:39.735602+05:30

## Purpose

This file preserves project-specific context so a future Codex session can restart work after a machine reset with minimal loss of continuity.

## Project Summary

- Project path: `/Users/Work/local_dev/RAG workflow/RAG_ENTERPRISE_STARTER`
- Estimated size: 1.9 GB
- Detected stack: Docker
- Git branch: `RAG_Enterprise_Dev`
- Uncommitted changes present: True

## Recovery Prompt For Codex

Use this project snapshot to restore working context. Reconstruct the local setup, verify required runtimes and tools, restore saved env/database files to the expected paths, review the current branch/remotes, and continue work without re-auditing the repo from scratch. Confirm any missing local dependencies or generated assets before making code changes.

## Git

- Remotes:
  - `origin	https://github.com/beyondalgorithms2026-source/RAG_ENTERPRISE_STARTER.git (fetch)`
  - `origin	https://github.com/beyondalgorithms2026-source/RAG_ENTERPRISE_STARTER.git (push)`
- Recent commits:
  - `f6e6d36c [M5] Add admin API control plane`
  - `d4306871 [M3][M4] Add OIDC auth and ACL security trimming`
  - `949a52dd [M2] Add retrieval observability and traceability`
  - `f411b70c Add project guidance and milestone docs`
  - `9206c3de feat(retrieval,docs): refresh project plan and add post-audit recommendations`
- Working tree snapshot:
  - `M .gitignore`
  - ` M 02_Enterprise_RAG_Project_Plan_Milestones.md`
  - ` M README.md`
  - ` M STATUS.md`
  - ` M backend/app/api/admin.py`
  - ` M backend/app/api/auth.py`
  - ` M backend/app/auth/service.py`
  - ` M backend/app/core/config.py`
  - ` M backend/app/core_rag/query_router.py`
  - ` M backend/app/core_rag/reranker.py`
  - ` M backend/app/core_rag/retrieval.py`
  - ` M backend/app/db/repo_search.py`
  - ` M backend/app/embedding/embedder.py`
  - ` M backend/app/eval/compare_eval.py`
  - ` M backend/app/eval/retrieval_eval.py`
  - ` M backend/app/ingestion/chunking.py`
  - ` M backend/app/ingestion/jobs.py`
  - ` M backend/app/llm/client.py`
  - ` M backend/app/main.py`
  - ` M backend/tests/fixtures/eval/README.md`
  - ` M backend/tests/fixtures/eval/benchmark_cases.json`
  - ` M backend/tests/test_smoke_baseline.py`
  - ` M backend/tests/test_smoke_router_compare_eval.py`
  - `?? AGENTS.md`
  - `?? "Codex prompt for each MIlestone"`
  - `?? Makefile`
  - `?? backend/app/corpus_policies.py`
  - `?? backend/app/db/repo_profiles.py`
  - `?? backend/app/profiles/`
  - `?? backend/tests/fixtures/eval/corpus_policy_cases.json`
  - `?? backend/tests/fixtures/eval/router_cases.json`
  - `?? backend/tests/test_auth_local_dev.py`
  - `?? docs/m10_1_polished_ui_with_test_users.md`
  - `?? docs/m10_nextjs_enterprise_console_ui.md`
  - `?? docs/m1_profiles_and_retrieval_controls.md`
  - `?? docs/m6_hybrid_fusion_upgrade.md`
  - `?? docs/m7_router_and_lexical_intent_expansion.md`
  - `?? docs/m8_reranking_policy_layer.md`
  - `?? docs/m9_per_corpus_indexing_and_adaptive_chunking_policies.md`
  - `?? web/`

## Environment Files

- `/Users/Work/local_dev/RAG workflow/RAG_ENTERPRISE_STARTER/backend/.env`
- `/Users/Work/local_dev/RAG workflow/RAG_ENTERPRISE_STARTER/backend/.env.example`
- `/Users/Work/local_dev/RAG workflow/RAG_ENTERPRISE_STARTER/web/.env.example`

## Database Files

- None found

## Key Project Files

- `/Users/Work/local_dev/RAG workflow/RAG_ENTERPRISE_STARTER/README.md`
- `/Users/Work/local_dev/RAG workflow/RAG_ENTERPRISE_STARTER/backend/requirements.txt`
- `/Users/Work/local_dev/RAG workflow/RAG_ENTERPRISE_STARTER/backend/tests/fixtures/eval/README.md`
- `/Users/Work/local_dev/RAG workflow/RAG_ENTERPRISE_STARTER/docker-compose.yml`
- `/Users/Work/local_dev/RAG workflow/RAG_ENTERPRISE_STARTER/docs/_master_docs/README.md`
- `/Users/Work/local_dev/RAG workflow/RAG_ENTERPRISE_STARTER/web/.next_stale_1775107799/package.json`
- `/Users/Work/local_dev/RAG workflow/RAG_ENTERPRISE_STARTER/web/.next_stale_1775107799/types/package.json`
- `/Users/Work/local_dev/RAG workflow/RAG_ENTERPRISE_STARTER/web/.next_stale_1775124395/package.json`
- `/Users/Work/local_dev/RAG workflow/RAG_ENTERPRISE_STARTER/web/.next_stale_1775124395/types/package.json`
- `/Users/Work/local_dev/RAG workflow/RAG_ENTERPRISE_STARTER/web/.next_stale_1775124484/package.json`
- `/Users/Work/local_dev/RAG workflow/RAG_ENTERPRISE_STARTER/web/.next_stale_1775124484/types/package.json`
- `/Users/Work/local_dev/RAG workflow/RAG_ENTERPRISE_STARTER/web/.next_stale_demo_fix_1775111309/package.json`
- `/Users/Work/local_dev/RAG workflow/RAG_ENTERPRISE_STARTER/web/.next_stale_demo_fix_1775111309/types/package.json`
- `/Users/Work/local_dev/RAG workflow/RAG_ENTERPRISE_STARTER/web/package.json`

## Package Scripts

- None found

## VS Code Recommendations

- None found

## Suggested Restore Steps

1. Clone or open `RAG_ENTERPRISE_STARTER` on the new Mac.
2. Restore the saved `.env` files into the same relative paths.
3. Restore the saved database files into the same relative paths.
4. Install the required runtimes and dependencies.
5. Install the recommended VS Code extensions if needed.
6. Open this snapshot file and give it to Codex as project context before resuming work.
