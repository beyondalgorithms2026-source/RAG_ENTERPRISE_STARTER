# M27 - Scenario Profiles And Reuse Blueprint Documentation

## Summary
- Added a scenario-first reuse blueprint so new teams can identify which repo modules to keep, disable, or replace for common RAG starter products.
- Documented four target profiles: small enterprise corpus access, employee-wide authenticated RAG, trusted no-auth research RAG, and full enterprise OIDC + ACL + governance mode.
- Added a Mermaid module-selection map that shows how scenario choice maps to auth, access, ingestion, retrieval, admin, eval, and governance blocks.
- Linked the blueprint from the main README, master guide, and module map.
- Added a documentation validation test that checks required scenarios, key security language, diagram presence, and referenced repo paths.

## Verification
- Added `backend/tests/test_m27_reuse_blueprint_docs.py`.
- Run with `cd backend && .venv/bin/python -m unittest tests.test_m27_reuse_blueprint_docs`.

