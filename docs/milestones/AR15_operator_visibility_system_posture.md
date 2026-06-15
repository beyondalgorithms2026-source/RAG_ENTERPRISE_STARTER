# AR15 — Operator Visibility: Global Health Banner, Serving State, And System Posture

**Date:** 2026-06-15 · **Plan:** `docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md` · **Gate:** AR15 (an admin sees everything they must know without reading env or the DB)

## Provenance

Post-audit console-completeness milestone from the 2026-06-13 follow-up UI review (not the original 2026-06-11 product audit). The review found that an admin had no in-UI way to know critical posture — chiefly that the semantic cache is globally off unless a policy is active — and that AR10's health banner was page-local.

## What was built

- **`backend/app/system_posture.py::system_posture()`** — one structured read-only payload across seven sections (serving, cache, retrieval defaults, eval enforcement, workers, rate limits, cost governance). Each item carries `label`, `value`, `editable_via` (`ui` / `env:VAR` / `policy` / `profile` / `lifecycle:…`), and `requires_restart`, so the console can tell the operator exactly what to change and where — including settings that, by design, are env-only.
- **`GET /admin/system/posture`** (`backend/app/api/admin.py`); `/admin/system` mapped to the `overview` module.
- **Health dashboard truthfulness** (`backend/app/health.py`): the `semantic_cache` tile now returns `warn` with "Semantic cache is globally OFF (no active policy)" when no policy is active, instead of silently passing. It is not a P0 tile, so this can move the banner to `warn` but never to a P0 fail.
- **Global banner** (`web/components/admin-health-banner.tsx`, mounted in `web/app/console/admin/layout.tsx`): fetches `/admin/health/dashboard` and renders a slim banner on every admin page **only** when `banner !== "pass"` (P0 fail → danger, warn → warning), linking to the health page. A healthy system shows nothing.
- **System Posture panel** (`web/components/admin-health-panel.tsx`): a grouped read-only table consuming `/admin/system/posture` with columns Setting / Current value / How to change (badge) / restart, and the literal "Semantic cache is globally OFF" headline when applicable.

## DoD check

- Fresh dev DB (cache off): the health page shows "Semantic cache is globally OFF" and the System Posture table lists every item with current values + edit method ✓.
- The global banner appears on non-health admin pages when the dashboard banner is not `pass` ✓ (driven by the shared `/admin/health/dashboard` signal; a forced dimension mismatch or injected AR2 state flips it — covered by AR10's P0-breach test).
- Re-run checks: `tests/test_system_posture_ar15.py` (all sections + editable metadata, single-process posture, enforcement mode surfaced, cache-off headline, endpoint contract, cache-off tile warns); AR10 cache-tile test updated for the new warn-when-off semantics; full suite **321/321**; `tsc --noEmit` clean; `docs/02` untouched.

## Notes

- The System Posture panel is intentionally **read-only**: AR17 makes cost budget / price table / enforcement runtime-editable; AR18 makes module enablement editable. Env-only items (workers, rate limits) stay env-only by design and are shown with their exact variable + restart flag.
- A transient `FAILED (failures=2)` appeared once during a full run from Postgres container `/dev/shm` exhaustion while many tests built HNSW indexes concurrently (DiskFull on the shared-memory segment); a clean re-run passed 321/321. This is an environment/Docker `shm_size` limitation, not a code regression.

**Next:** AR16 — Embedding & Model-Swap Console.
