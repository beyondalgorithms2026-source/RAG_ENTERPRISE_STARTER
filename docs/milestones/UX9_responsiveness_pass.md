# UX9 — Responsiveness Pass

**Date:** 2026-06-17 · **Plan:** `docs/05_Enterprise_RAG_UIUX_Audit_Remediation_Milestones.md` · **Gate:** UX9 · **Audit:** M6, mn7

## Provenance

Only 4 media queries existed across 6,600 CSS lines; chat used a fixed `1fr / 320px` grid; the evidence rail was a sticky, height-capped column (double scroll). Narrow laptops/tablets crowded and overflowed.

## Deliverables (appended to the `globals.css` responsive section, broad→narrow so the narrowest wins)

- **≤1280px:** chat layout tightens (rail 320→300px), chat metadata bar gap/padding reduced.
- **≤1024px:** **evidence rail drops below the conversation as a full-width sheet** (`.chat-evidence-panel` → static, natural height, top border; `.chat-layout` → single column); the **chat metadata bar wraps**; admin **4/5-column filter grids → 2 columns**; the search query input goes full-width.
- **≤768px:** admin filter grids → **1 column**; chat answer card padding/radius shrink; chat metadata bar tightens; search page padding reduced; **search facets stack** (groups + selects full-width); snippet `max-width` removed so it uses available width.
- Dense admin **tables keep their horizontal scroll** (`.admin-table-scroll` `overflow-x`), so wide tables scroll inside their container instead of overflowing the viewport.

## DoD check

- Breakpoints at 1280 / 1024 / 768 added ✓; evidence rail becomes a stacked sheet ≤1024 ✓; metadata bar wraps ✓; admin filter grids collapse ✓.
- `tsc --noEmit` clean ✓; `next build` compiles 12/12 ✓; no-external-deps invariant holds ✓.

## Honest limits

- **Live multi-width browser verification was not run** in this environment: the console (chat/search/admin) is auth-gated (`requireViewer` redirects to login) and needs the backend for data, so a headless screenshot pass at 1280/1024/768 wasn't feasible here. Verification is by build + CSS reasoning against the known overflow vectors (fixed rail, multi-col grids, wide tables, long snippets). A real-browser pass at the three widths should be done before release.
- **Evidence rail is a stacked full-width sheet**, not a JS toggle drawer/overlay. This avoids new client state and regression risk while resolving the crowding/double-scroll; a true off-canvas drawer (with a toggle) can be layered on later.
- **Sidebar nav remains a fixed aside** at all widths; a true off-canvas/hamburger mobile nav is out of this milestone's scope. Content tables scroll internally so the viewport does not overflow horizontally.

**Next:** UX10 — finish pass (placeholders, jargon, glossary, access-request modal, states, spinner, composer shortcut).
