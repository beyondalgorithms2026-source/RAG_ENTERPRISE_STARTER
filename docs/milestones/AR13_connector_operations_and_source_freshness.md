# AR13 — Connector Operations And Source Freshness

- Added `MIG-P025`: source lifecycle timestamps, DB connector schedules/leases/health, and durable `connector_sync_runs`.
- Added interval scheduling with atomic PostgreSQL claims, manual-run conflict rejection, degraded health, and bounded exponential retry.
- Added fresh/stale/unknown source metadata to admin sources, user sources, search results, citations, cache hits, and citation context.
- Added connector health, schedule controls, retry timing, and run history to the admin console.
- Corrected email scope: ingestion is uploaded `.eml`; live mailbox/archive synchronization remains unimplemented.
- Verification: AR13 regression pack and updated M12 smoke green; full backend suite 310/310; `npx tsc --noEmit` green; reader clarity 21/21; protected-plan diff empty.

**Next:** AR14 — Retrieval Enhancements, Only With Eval-Proven Gains.
