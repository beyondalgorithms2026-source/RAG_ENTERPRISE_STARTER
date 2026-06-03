# Scenario Pack: enterprise_oidc_acl

Full enterprise mode with OIDC identity, document ACL trimming, time-bound grants, governance, actions, audit, observability, and tuning.

## Build Choices
- `AUTH_MODE=oidc`
- `ACCESS_STRATEGY=document_acl_with_time_bound_grants`
- `SCENARIO_PROFILE=enterprise_oidc_acl`
- All admin modules are enabled.
- Non-local deployments must replace secrets and use HTTPS endpoints.
