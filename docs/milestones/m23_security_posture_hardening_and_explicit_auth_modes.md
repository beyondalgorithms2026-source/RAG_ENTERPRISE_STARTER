# M23 - Security Posture Hardening And Explicit Auth Modes

## Summary
- Added explicit `APP_ENV` and `AUTH_MODE` posture handling for `none`, `dev`, `password`, and `oidc`.
- Kept `AUTH_MODE=none` as an intentional trusted research mode while protecting admin and connector-control surfaces.
- Restricted local-dev login/impersonation to `APP_ENV=local|dev` plus `AUTH_MODE=dev`.
- Added startup posture validation so staging/prod reject `none`, `dev`, reserved `password`, and weak/default secrets.
- Preserved local PoC dev login behavior for the built-in test user and test admin.

## Verification
- Added focused M23/M24 smoke tests in `backend/tests/test_security_posture_m23_m24.py`.
