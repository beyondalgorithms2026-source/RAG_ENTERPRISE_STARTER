# M29 - Modular Admin Console And Feature Flag Packaging

## Summary
- Added scenario-aware admin module presets for `research_no_auth`, `employee_wide_rag`, `small_enterprise_corpus_acl`, and `enterprise_oidc_acl`.
- Added backend module inventory and enforcement through `/admin/modules` and direct API module gates.
- Added frontend admin navigation filtering and direct route guards so disabled modules do not appear as usable console features.
- Preserved full enterprise admin behavior as the default.

## Verification
- Added focused coverage in `backend/tests/test_admin_modules_m29.py`.
- Re-run scenario module inventory, disabled direct API access, and enterprise full-surface checks before marking complete.
