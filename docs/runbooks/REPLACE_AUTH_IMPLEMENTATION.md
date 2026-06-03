# Replace Auth Implementation

Use the current auth layer as the boundary. Replace token validation and identity mapping, not retrieval internals.

1. Keep `AuthenticatedUser` fields stable: `user_id`, `email`, `roles`, `groups`.
2. Replace OIDC/dev validation with the target provider.
3. Keep `require_authenticated_user`, `require_admin_user`, and upload-role checks as endpoint gates.
4. Re-run M23-M24 security posture tests.
5. Re-run M28 access strategy tests to confirm identity still drives SQL-level trimming.

For MSME username/password mode, implement `AUTH_MODE=password` behind the same user contract before enabling it in non-local environments.
