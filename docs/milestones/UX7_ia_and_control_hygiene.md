# UX7 — IA & Control Hygiene (nav grouping, vocabulary, coming-soon)

**Date:** 2026-06-17 · **Plan:** `docs/05_Enterprise_RAG_UIUX_Audit_Remediation_Milestones.md` · **Gate:** UX7 · **Audit:** M1, M3, M4

## Deviation from the plan (per operator instruction)

The plan's UX7 said "remove or honestly label" the fake/disabled controls. The operator directed: **do not remove them — mark them "coming soon" consistently; removal can be done later** (removing now risks them never being implemented). This note records that decision; the controls are preserved with a consistent coming-soon treatment instead of deleted.

## Deliverables

- **Admin nav grouping (M3):** `lib/admin-nav.ts` — a **server-free** module with `AdminNavItem`/`AdminNavSection` and `groupAdminNav()`, grouping the flat 18-item nav into **Operate / Retrieval / Data / Governance** with **Overview pinned**. `admin-modules.ts` re-exports these (kept its server-only `serverFetch` out of the client bundle). `console-shell` renders pinned links + **collapsible** sections (per-section expand/collapse state).
- **Nav vocabulary (M4):** one verb set. Workspace sidebar is now **Ask / Search / History / Approvals & Access / My Sources / Upload Documents / Connectors** — "Chat"→"Ask" (matches the topbar Ask/Search toggle), "Search History"→"History", and **Search is now in the sidebar** (was only a topbar toggle). Guide-card copy aligned ("return to Ask or Search", "Open Ask").
- **Coming-soon treatment (M1, preserved):** a consistent pattern for controls intentionally not wired yet — `disabled` (or `readOnly`/`tabIndex={-1}` for inputs), `title="Coming in a later release."`, accessible name suffixed `(coming soon)`, and either a `.coming-soon-badge` ("Soon") pill (labelled controls) or a `.is-coming-soon` accent dot (icon-only). Applied to: admin ⌘K search, workspace search input, Settings (admin + workspace), chat composer attach/image/mic, and Export Findings. The old ad-hoc "not wired yet / not live yet / lands in a later milestone" strings are gone. Pattern documented in `web/DESIGN.md`.
- **CSS:** `.admin-sidebar-group/-section/-section-symbol` (Admin section) and the shared `.coming-soon-badge`/`.is-coming-soon`/`[data-coming-soon]` (Components section). No new tokens.

## DoD check

- Admin sidebar is grouped + collapsible with Overview pinned ✓.
- Workspace nav labels are consistent and Search is discoverable in the sidebar ✓.
- No inert "not wired yet"-style controls remain in primary chrome — each is now consistently marked coming-soon (and preserved) ✓ (grep: no residual ad-hoc strings).
- `tsc --noEmit` clean ✓; `next build` compiles 12/12 ✓; no-external-deps invariant holds ✓.

## Honest limits

- Per the operator decision, the coming-soon controls remain **non-functional** (disabled) — this milestone makes them honest and consistent, not live. Wiring them up is future work.
- Admin nav section membership is a static mapping by module key; modules outside the four sections fall into a "More" group so nothing is dropped.

**Next:** UX8 — accessibility baseline (focus ring, aria-live, names, contrast).
