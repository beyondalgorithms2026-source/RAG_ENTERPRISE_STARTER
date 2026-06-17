# Admin Console UI Consistency Checklist (AR20)

The standard every admin panel must meet. Derived from a console review that
found unstyled native selects, inconsistent input fills, and dense unreadable
tables.

## Form controls
- Use the shared primitives in `web/components/ui/` (`Field`, `TextInput`,
  `NumberInput`, `Select`, `Textarea`, `Toggle`, `FormActions`). Do not hand-roll
  raw `<input>/<select>/<textarea>` in panels.
- Every control is **boxed**: 1px `var(--outline-strong)` border, white
  `var(--surface-panel)` background, `border-radius: 10px`, ≥38px min-height,
  consistent padding. Selects use a custom chevron (`appearance: none`).
- The global rule in `web/app/globals.css` boxes any native control too, so a
  stray native control still looks consistent — but prefer the primitives.
- Range sliders, checkboxes, and radios are excluded from the boxed rule.
- Focus shows the shared ring (`box-shadow: 0 0 0 2px var(--primary-soft)`).

## Labels & spacing
- Field label above control via the `Field` primitive (consistent gap).
- Sentence case. No raw snake_case in user-facing values — humanize
  (`retrieval_mode` → `retrieval mode`).

## Tables
- Use `.admin-data-table` (zebra rows, sticky header, padding, hover) inside an
  `.admin-table-scroll` wrapper when rows can exceed ~12 (caps height, scrolls).
- No bare `<table>` with inline per-cell padding.

## Master / detail (long lists)
- A detail/inspect pane below or beside a long list must use
  `.admin-sticky-detail` (stays in view) **and** scroll into view on selection
  (`ref` + `scrollIntoView({ behavior: "smooth", block: "start" })`), so
  selecting an item far down the list never loses the selection.
- Applied: Sources (`SourcesAdminPanel`). Adopt the same pattern in Jobs and
  Audit Log detail panes.

## Explanatory affordances
- Group headings that need context get a small `(i)` info dot with a
  plain-language `title` tooltip (see `SystemPosture` in `admin-health-panel`).
- Display-only toggles (e.g. tuning "Visual Mode") carry a `title` explaining
  they are presentation-only.

## Per-panel sign-off
For each admin panel, confirm: controls boxed & primitive-based · labels spaced ·
values humanized · long tables use `.admin-data-table` + scroll · master/detail
sticky + reveal-on-select · `npx tsc --noEmit` clean.
