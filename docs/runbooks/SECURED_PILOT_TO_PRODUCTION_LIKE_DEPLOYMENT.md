# Promote Secured Pilot To Production-Like Deployment

1. Use `APP_ENV=staging` or `prod`.
2. Use HTTPS frontend/API origins.
3. Use `AUTH_MODE=oidc`.
4. Use strong database, OIDC, auth state, and JWT secrets.
5. Use `ACCESS_STRATEGY=document_acl_with_time_bound_grants` for enterprise-sensitive data.
6. Set `SCENARIO_PROFILE=enterprise_oidc_acl` only when governance, actions, audit, tuning, and connectors are operationally owned.
7. Run M23-M30 regression checks before launch.

Production-like rollout should include audit integrity review and retention policy review.
