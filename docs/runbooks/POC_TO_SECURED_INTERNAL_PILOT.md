# Promote PoC To Secured Internal Pilot

1. Move from `AUTH_MODE=none` or `dev` to `oidc` when real identity is available.
2. Choose `ACCESS_STRATEGY=employee_all` for equal access or `corpus_level` for simple segmented access.
3. Set `SCENARIO_PROFILE=employee_wide_rag` or `small_enterprise_corpus_acl`.
4. Replace default secrets and configure explicit CORS origins.
5. Run security posture, baseline smoke, citation, access strategy, and admin module tests.

Keep governance/tuning disabled until operators are trained to use those workflows.
