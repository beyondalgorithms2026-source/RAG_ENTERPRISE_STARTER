# Scenario Pack: research_no_auth

Trusted research/admin RAG with no user identity layer. Use only for controlled local or internal research environments with non-sensitive data.

## Build Choices
- `AUTH_MODE=none`
- `ACCESS_STRATEGY=none`
- Admin modules focus on source/corpus operations, jobs, evals, traces, and audit review.
- Tuning, governance, connector setup, actions, and ACL administration are disabled by default.
