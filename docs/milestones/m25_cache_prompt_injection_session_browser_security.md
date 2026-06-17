# M25 - Cache, Prompt-Injection, Session, And Browser Security Hardening

## Summary
- Added direct-grant fingerprinting to semantic-cache scope so time-bound/user-specific grants affect cache eligibility.
- Reauthorized cached citation source access before serving cached answers; unauthorized cached citations now produce a cache miss.
- Fenced retrieved context as untrusted source text in answer and compare prompts.
- Added log-only prompt-injection signal detection for ingested and retrieved text.
- Added env-driven CORS origins, security headers, non-local secure cookie posture, and CSRF checks for cookie-authenticated mutations.

## Verification
- Added focused M25/M26 coverage in `backend/tests/test_security_m25_m26.py`.
