# UX6 — Search Facets, Sort, And Labeled Relevance

**Date:** 2026-06-17 · **Plan:** `docs/05_Enterprise_RAG_UIUX_Audit_Remediation_Milestones.md` · **Gate:** UX6 (experts can narrow & trust ranking) · **Audit:** M7

## Provenance

After UX3, Search rendered on the canonical table but offered only a mode select — no facets, no sort, no way to narrow a result set. Repeated expert search was inefficient.

## Deliverables

- **Facet controls (live, client-side):** source type, **corpus**, freshness, and **indexed-within** (Any time / 24h / 7d / 30d), plus a **sort** control (Relevance / File name A–Z / Freshness / Source type). Built on canonical components — multi-select facets use `ui/Toggle` checkboxes, single-selects use `ui/Select`. Filtering + sorting run over the already-fetched result set via `useMemo` (no refetch), so changes apply instantly.
- **Result summary** now reads "**X of Y** results · {mode} · {latency}ms"; the **relevance bar** normalizes to the top *visible* result (carried from UX3, with the tooltip updated accordingly).
- **Facet groups self-hide** when they would not help (corpus/freshness shown only when ≥2 distinct values; source type when present), avoiding empty/dead controls. A **Clear filters (n)** button appears when any facet is active. A dedicated "no results match the current filters" state distinguishes over-filtering from a true no-match.
- **Backend (minimal, additive):** added `corpus_name: Optional[str]` to `SearchResultItem` (`backend/app/core_rag/retrieval.py`), populated in `_materialize_search_results` from `source_metadata_json.corpus` via the already-imported `get_sources_by_ids` — no change to retrieval/scoring logic. Mirrored on the frontend `SearchResult` type. The corpus also appears inline in the Source cell.
- **CSS:** `.search-facets` group/label/options layout under the Workspace section (no new tokens).

## DoD check

- Facets + sort filter and reorder results live ✓; controls match the design system (canonical Toggle/Select/Button) ✓.
- Result count + labeled relevance carried through ✓.
- `tsc --noEmit` clean ✓; `next build` compiles 12/12 (search route 3.9 kB) ✓.
- Backend additive field verified: full backend suite **349/349 green** (isolated re-run; an earlier overlapping run reported 2 transient DB-state failures that did not reproduce on a clean run). 190 search/retrieval cases green in a separate targeted run.
- No-external-deps invariant holds ✓.

## Honest limits

- **Faceting is over the returned set** (default k=8), not a server-side re-query — narrowing refines what retrieval already returned rather than fetching more. A server-side faceted query would be a backend/retrieval change beyond this UX milestone.
- **Date facet** uses the freshness timestamp (`last_ingested_at` → `observed_at` → `last_synced_at`); results without any timestamp are excluded when a window is selected.
- The corpus field reads `source_metadata_json.corpus`; sources without a corpus assignment show as **"Unassigned"**.
- Relevance remains **relative to the visible set**, not an absolute cross-query score (see UX3).

**Next:** UX7 — IA & dead-control cleanup (admin nav grouping, nav-label consistency, remove fake/disabled controls).
