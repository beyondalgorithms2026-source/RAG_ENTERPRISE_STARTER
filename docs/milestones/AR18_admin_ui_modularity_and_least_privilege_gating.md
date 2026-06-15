# AR18 — Admin UI Modularity And Least-Privilege Gating

**Status:** Complete (2026-06-15)

## Findings Remediated

- Health and Cost rode the always-on `overview` module; Flywheel rode `governance`; Embedding and Providers had no first-class module.
- `/admin/embedding/*`, `/admin/llm/*`, and `/admin/retrieval/*` bypassed module gating because they had no path mapping.
- Module enablement was environment/preset-only with no runtime manager.

## Changes

- Added first-class `health`, `cost`, `flywheel`, `embedding`, and `providers` modules and exact server path mappings.
- Reused MIG-P027 `runtime_settings` for `admin_modules_enabled`; precedence is runtime override, environment override, then scenario preset. `overview` is immutable.
- Added governed `PATCH /admin/modules` with validation, separation-of-duties approval, and audit evidence.
- Added `/console/admin/modules` for deployment-wide module composition and updated all dedicated page gates/navigation.
- Updated scenario inventories; smaller presets retain Health and exclude Cost, Flywheel, Embedding, and Providers.

## Verification

- Focused AR18/M29/M30: 16/16.
- Full backend suite: 340/340 in 177.514s on the live `vector(768)` dev database.
- TypeScript: `npx tsc --noEmit` passed.
- Browser walkthrough: module-manager route loaded as Test Admin; first-class navigation and all module toggles rendered; Overview was checked and disabled; no browser console errors.
- The HNSW index encountered a shared-memory limit during the full suite; the existing migration fallback created IVFFLAT and the suite remained green.

## Limits

- Composition is deployment-wide, not tenant-scoped.
- Scenario presets are coherent supported defaults. Arbitrary custom subsets can disable an endpoint another enabled panel expects.
