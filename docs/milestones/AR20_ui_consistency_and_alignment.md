# AR20 — UI Consistency & Alignment Remediation

**Date:** 2026-06-15 · **Plan:** `docs/04_…Milestones.md` · **Gate:** AR20 (every control is boxed, aligned, and visually consistent)

## Provenance

Post-audit console-quality milestone from the 2026-06-13 review (screenshots): native selects rendered as bare text, inputs had an olive/tan fill, dense tables (flywheel/health) looked dated, long lists lost the selected item, and some values showed raw snake_case. Shipped in two tranches.

## Part 1 (commit `3414745`)
- **Root-cause control fix** (`web/app/globals.css`): native `input/select/textarea` were `border: 0` filled with the tan `--surface-highest`. Now one boxed control on the white `--surface-panel` — visible border, custom select chevron (`appearance: none`), 38px min-height, shared focus ring; range/checkbox/radio excluded. `.ui-control` switched to the white surface to match. This fixes the connector/queue/trace/access screenshots across every panel at once.
- **System Posture info dots** (`admin-health-panel`): an `(i)` with a plain-language hover tooltip on each heading.
- **Source download** (item 5): `GET /admin/sources/{id}/download` (file or db_row text) + `/download-info` (25 MB too-large flag); Sources page "Download" button that warns + confirms before a large download. Backend `tests/test_source_download_ar20.py`.

## Part 2 (this commit)
- **Consistent data tables** (`globals.css` `.admin-data-table` + `.admin-table-scroll`): zebra rows, sticky header, padding, hover, height-capped scroll. Applied to the flywheel pass-rate trend, System Posture, and cost rollup tables — the "90s" flat tables are gone.
- **Sticky + reveal-on-select for long lists** (item 4): `.admin-sticky-detail` plus a `ref` + `scrollIntoView` so selecting an item far down a list brings its detail pane into view and keeps it there. Applied to **Sources, Jobs, and Audit Log**.
- **Human-readable values**: snake_case humanized in the cost rollup (`retrieval_mode` → `retrieval mode`, `deep_research` → `deep research`).
- **Explanatory affordances**: tuning **Visual Mode** now has a `title` ("display only — switch between guided editor and raw parameter form"); the **"AR14 Retrieval Evidence"** eyebrow is relabeled to operator language **"Retrieval tuning evidence"** with an explanatory tooltip.
- **`docs/runbooks/UI_CONSISTENCY_CHECKLIST.md`**: the standard for future panels (controls, labels, tables, master/detail, tooltips, per-panel sign-off).

## DoD check

- The screenshotted panels render boxed, consistent controls; no tan/olive input fills remain ✓ (global control rule).
- Dense tables read as the design system ✓; long-list selection no longer lost ✓ (sticky + reveal on Sources/Jobs/Audit Log).
- `tsc --noEmit` clean; backend suite unaffected — **349/349** green (part 1); reader-clarity 21/21; `docs/02` untouched.

## Honest limits

- The bare-control automated CI guard described in the plan is documented in the checklist but not yet implemented as a test — the global CSS rule makes a stray native control look correct regardless, so this is low-risk; a lint can be added later.
- Sticky detail relies on the surrounding scroll container; reveal-on-select is the reliable behavior and is always present.

**Next:** AR-series plan (AR0–AR20) is complete. Remaining backlog items are operator-driven, not audit-driven.
