# AR16 — Embedding & Model-Swap Console

**Date:** 2026-06-15 · **Plan:** `docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md` · **Gate:** AR16 (a managed model swap runs from the console, no CLI)

## Provenance

Post-audit console-completeness milestone. AR7 shipped the embedding/index swap lifecycle and the serving guard as API-only; this puts the whole flow in the admin console so a non-CLI operator can run a safe model swap.

## What was built (web only — no backend change)

- `web/components/admin-embedding-panel.tsx` + `web/app/console/admin/embedding/page.tsx` (gated to the `profiles` module until AR18 adds a dedicated `embedding` module); nav entry added in `web/lib/admin-modules.ts`.
- Serving-state header from `GET /admin/embedding/serving` (serviceable/degraded + declared vs index dims), with a prominent keyword-only warning when degraded.
- Target embedding-profile selector from `GET /admin/tuning/configurations` (`approved_options.embedding`), with the live profile marked.
- Drives the AR7 state machine: **Plan** (`/swap/plan` → requires_reindex / requires_column_resize / already-embedded vs total) → **Begin** (`/swap/begin`, sends `X-Approval-Actor` when provided, for production segregation-of-duties) → **Run batch** (`/swap/run` with a batch_limit, repeatable, with an embedded/total progress bar) → **Verify** (`/swap/verify`, shows counts + sample self-similarity) → **Abort** (`/swap/abort`).
- A persistent "Vector search is serving keyword-only until this reindex completes" banner while a run is `reindexing`.
- Run-history table from `GET /admin/embedding/swaps`.

No backend change was required — the AR7 run payloads already carry `total_chunks`, `embedded_chunks`, `status`, `verification_json`, and dims, so progress percent is computed client-side.

## DoD check

- A swap is fully drivable from the console (plan → begin → run(s) with visible progress → verify → completed); the degraded-serving banner shows during reindex ✓ (UI wired to the AR7 endpoints; AR7's lifecycle tests already prove the backend transitions).
- `tsc --noEmit` clean; backend suite unaffected — **321/321** green; `docs/02` untouched; reader-clarity 21/21.

## Notes

- Approval actor is optional and only enforced in non-local runtimes (segregation of duties); locally `Begin` proceeds without it.
- AR18 will promote this surface to a first-class, independently toggleable `embedding` module and gate `/admin/embedding/*` accordingly (currently mapped to `overview` server-side / the page gated to `profiles`).

**Next:** AR17 — Generation Provider & Cost-Governance Console.
