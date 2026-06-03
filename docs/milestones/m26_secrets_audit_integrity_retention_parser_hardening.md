# M26 - Secrets, Audit Integrity, Data Retention, And Parser Hardening

## Summary
- Extended non-local startup validation for HTTPS frontend URLs, database password strength, OIDC secrets, and provider API-key posture.
- Added tamper-evident hash chaining for new admin audit events and an integrity-check API.
- Added lightweight high-impact action approval checks for non-local deployments.
- Added retention/redaction policy execution for query events, feedback, traces, semantic cache, and audit review metadata.
- Added DOCX/PPTX/XLSX archive expansion guards and model warm-up allowlisting against approved registry models.

## Verification
- Added audit tamper detection, retention, parser safety, and warm-up allowlist tests in `backend/tests/test_security_m25_m26.py`.
