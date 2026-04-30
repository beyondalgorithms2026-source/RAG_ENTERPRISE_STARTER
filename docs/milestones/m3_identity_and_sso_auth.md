## M3: Identity And SSO Auth

- Added generic OIDC configuration for Azure AD, Okta, or Google Workspace style providers through discovery metadata and JWT validation.
- Added `/auth/login`, `/auth/callback`, `/auth/logout`, `/auth/me`, and `/auth/providers` endpoints for a basic backend-managed login flow.
- Added request auth middleware that validates bearer or cookie tokens, attaches user context to `request.state`, and propagates identity into structured logs.
- `/ask` and `/ask/stream` now require authentication when `AUTH_ENABLED=true`.
- Introduced simple first-pass roles: `user`, `admin`, `approver`, derived from configured OIDC role claims.
