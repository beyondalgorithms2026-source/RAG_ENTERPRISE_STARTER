# UX3 — Repair The Search Surface

**Date:** 2026-06-17 · **Plan:** `docs/05_Enterprise_RAG_UIUX_Audit_Remediation_Milestones.md` · **Gate:** UX3 (Search renders as the design system) · **Audit:** C1

## Provenance

`search-workspace.tsx` was built entirely on **undefined** classes (`workspace-panel`, `workspace-title`, `muted-copy`, `panel-toolbar`, `inventory-table`, `inventory-row`, `inventory-title`, `table-subtle`), so one of the two primary retrieval surfaces rendered as raw, unlabeled stacked `<div>`s — five fields per row including a bare `score.toFixed(3)` float. It looked broken and contradicted the product's trust goal at first contact.

## Deliverables

- **Rebuilt results on the canonical table** (`.admin-table-scroll` > `.admin-data-table`): a real `<thead>` with column headers **Source / Type / Location / Relevance / Snippet**, sticky header + zebra rows + hover from the design system.
- **Labeled relevance indicator** replacing the raw float: a bar (`.search-relevance-bar`, width relative to the top result in the set) + the numeric value (`tabular-nums`) + a `title` tooltip explaining it is the retrieval score for the active mode and that the bar is relative to the top result. Honest about normalization rather than implying an absolute 0–1 scale.
- **Result count + summary**: `N results · {mode} retrieval · {latency}ms`.
- **Toolbar through canonical components**: query via `ui/TextInput`, mode via `ui/Select`, submit via `.stitch-button` — plus **Enter-to-search** on the query field. New Search-surface layout classes (`.search-page/-header/-toolbar/-relevance/...`) added under the Workspace section of `globals.css` (bespoke layout for a surface, consistent with `chat-*`/`sources-*`; the canonical Table/controls/Button are reused, not re-invented).
- **Source cell** shows a source-type icon (`MaterialIcon`), heading + filename, and a freshness badge when present (trust cue), reusing the semantic `.badge` styles.
- Preserved the existing **empty / loading / no-result** states.

## DoD check

- No undefined classes remain in `search-workspace.tsx`; every referenced class is canonical or defined in `globals.css` ✓ (verified by grep).
- Results have labeled columns and a relevance affordance ✓; result count present ✓.
- Visual parity with the rest of the console (canonical table + controls + buttons) ✓.
- `tsc --noEmit` clean ✓; `next build` compiles 12/12 (search route 2.67 kB) ✓.
- UX1 invariant holds: zero `googleapis|gstatic|googleusercontent|material-symbols` under `web/app|components|lib` ✓.

## Honest limits

- **Relevance is relative, not absolute.** Hybrid/vector/keyword scores are not normalized to a common 0–1 range by the backend, so the bar is scaled to the top result *within the current result set* and the raw score is shown alongside (with a tooltip). This is a faithful affordance, not a calibrated confidence meter — a normalized cross-query score would be a backend change, out of UX scope.
- **No facets/sort yet.** UX3 only repairs rendering; faceting, sorting, and an explained relevance model are UX6.
- New `.search-*` classes are surface-specific layout (like other surfaces); they are not new *canonical components* and do not alter the design system.

**Next:** UX4 — render grounded answers as sanitized Markdown.
