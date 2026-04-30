# M10.1.1 — Local Dev Auth And First-Run Entry Path Coherence

- Login now adapts to backend auth availability instead of always assuming OIDC is live.
- `/auth/providers` degrades gracefully when local dev auth is enabled and OIDC is not configured or not reachable.
- `/auth/login` now redirects back to the frontend login screen with `dev_login=1` in local-dev-only environments instead of dead-ending with an OIDC configuration error.
- The login page explicitly promotes the local dev test-user and test-admin path when that is the supported first-run flow.
- Real deployed environments still preserve the SSO-first primary action when OIDC is available.
