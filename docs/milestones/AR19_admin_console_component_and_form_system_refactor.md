# AR19 — Admin Console Component And Form-System Refactor

**Status:** Complete (2026-06-15)

## Findings Remediated

- `admin-profiles-panel.tsx` was a 1,403-line mega-component spanning tuning, evaluation, cache governance, query mining, and governance operations.
- Admin forms used duplicated raw inputs, selects, textareas, toggles, labels, and validation conventions.

## Changes

- Added shared `Field`, `TextInput`, `NumberInput`, `Select`, `Textarea`, `Toggle`, `FormActions`, and `useFieldState` primitives with a 36px control baseline.
- Replaced the profiles mega-component with a 36-line composer, one typed workspace provider, and four focused panels. Each panel is below 400 lines.
- Migrated active admin console controls to the shared vocabulary and removed the unused duplicate Profiles and Access implementations from `admin-panels.tsx`.
- Added static regression tests for panel size, primitive use, endpoint parity, and duplicate-panel removal.

## Verification

- Focused AR19 tests: 5/5.
- TypeScript: `npx tsc --noEmit` passed.
- Browser walkthrough: 18 migrated admin routes loaded their forms without page error banners or browser console errors.
- Full backend suite: pending final release-gate run.

## Limits

- AR19 changes structure and form vocabulary only. AR20 owns visual spacing, alignment, select treatment, and screenshot-driven consistency remediation.
- The shared workspace provider intentionally preserves the existing request/state machine; endpoint behavior was not redesigned.
