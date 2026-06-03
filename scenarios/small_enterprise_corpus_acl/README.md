# Scenario Pack: small_enterprise_corpus_acl

MSME-friendly setup with simple login identity and corpus-level authorization instead of per-document ACL complexity.

## Build Choices
- `AUTH_MODE=dev` locally; replace with `password` after password auth is implemented, or `oidc` for production pilots.
- `ACCESS_STRATEGY=corpus_level`
- Source, corpus, access, jobs, evals, traces, and audit modules are enabled.
- Tuning lab, governance, actions, connector setup, profiles, and policies are disabled by default.
