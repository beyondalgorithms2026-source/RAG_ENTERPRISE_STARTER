# M24 - Endpoint Authorization, Upload Safety, And Abuse Controls

## Summary
- Added scenario-aware authorization to `/search`, `/ask`, `/ask/stream`, `/compare`, `/upload`, `/upload/batch`, and connector request endpoints.
- Kept no-auth research mode limited to search/ask-style use; uploads are rejected unless `AUTH_NONE_ALLOW_UPLOAD=true`.
- Required admin/editor roles for uploads in secured modes.
- Added early upload request-size rejection plus bounded chunked upload reads.
- Added lightweight in-memory rate limits for ask, search, upload, compare, and expensive admin model warm-up paths.

## Verification
- Added focused endpoint authorization, oversized upload, and rate-limit coverage in `backend/tests/test_security_posture_m23_m24.py`.
