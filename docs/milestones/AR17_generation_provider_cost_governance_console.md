# AR17 — Generation Provider & Cost-Governance Console

**Status:** Complete — 2026-06-15

## Delivered

- Added MIG-P027 `runtime_settings` with strict allowlisting and runtime → environment → default precedence.
- Added governed APIs for effective cost budget, model price table, and promotion eval enforcement, including reset and separation-of-duties approval.
- Added candidate LLM connection verification without activation or mutation of live readiness.
- Added provider validation on profile writes and activation.
- Made LLM API keys write-only: responses, tuning payloads, activation payloads, and audit events are recursively redacted.
- Added `/console/admin/providers`, editable cost governance, and promotion-time enforcement controls.

## Evidence

- Unknown providers are rejected with HTTP 422, including legacy-profile activation.
- Runtime price and budget changes appear in `/admin/cost/summary` and drive persisted over-budget alerts.
- Candidate verification returns `{ready, reason}` while preserving live process readiness.
- Secret regression tests prove plaintext API keys never appear in API or audit JSON.
- Full backend suite: 333/333.
- TypeScript: `npx tsc --noEmit` passes.
- Reader clarity: 21/21.
- Protected M-series plan diff: empty.

## Honest Limits

- Cloud providers were transport-mocked; no live cloud credentials were available.
- API keys remain stored in profile JSON. Database-at-rest encryption or an external secret manager is deployment responsibility.

## Next

AR18 — UI Modularity & Least-Privilege Gating.
