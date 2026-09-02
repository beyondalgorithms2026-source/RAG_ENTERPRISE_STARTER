# Enterprise RAG Starter — UI/UX Audit Remediation Milestone Plan (UX-series)

**Objective (one sentence)**
Convert the 2026-06-17 UI/UX audit into a sequenced set of corrective milestones that give the console a single written design language, remove every external (Google-hosted) UI dependency, erase the design-tool ("Stitch") provenance from shipped code, and close the concrete RAG-surface, accessibility, and responsiveness gaps — so the product reads as enterprise software, not a wired-up mockup.

**Source audit**
The 2026-06-17 UI/UX audit (this session's findings). Findings are referenced by their audit IDs: Critical `C1–C4`, Major `M1–M7`, Minor `mn1–mn7`. Where a milestone and the audit disagree, the audit is the source of truth until re-verified.

**Planning principle (the screenplay before the scenes)**
The audit's central conclusion: the product's *premise* (retrieval + provenance) is strong and several individual screens are well built, but there is **no shared design language**, so screens were generated outward-in (from Google Stitch mockups) and the stylesheet was reverse-engineered to cover them. The result is drift: two button systems, two token vocabularies, orphaned classes behind a visually broken Search page, external image/font dependencies, and "demo-grade" dead controls. **This plan establishes the design language first (UX0) and removes the external/temporary scaffolding next (UX1–UX2). No screen-level fix is built until there is one source of truth to build it against** — otherwise each fix becomes a new dialect and deepens the drift.

**Core rules for this plan**
- **Design-language-first.** No UX milestone after UX0 may introduce a new token, component, or CSS class that is not defined in `web/DESIGN.md`. Reuse the canonical primitive or extend the design language deliberately.
- **No external UI dependencies, ever.** No Google Fonts, no Material Symbols (or any) icon font from a CDN, no third-party image hosts. Fonts and icons are self-hosted and bundled. **A blocked network must never degrade the UI** (the current failure mode renders literal ligature words like "search"/"send" and AI-stock avatars).
- **No "Stitch" wording in shipped code.** Scrub the word *Stitch* from code comments and user-facing copy, and add no Stitch placeholder assets or origin-narrating comments. **Existing `stitch-*` class identifiers may remain** — renaming them across the codebase is an intentionally out-of-scope, high-risk change with no functional gain; only the textual mentions are removed, and no new `stitch-*` names are introduced. the original design reference (removed from this repository) stays as an out-of-build reference folder.
- **`globals.css` is sectioned and dead-code-free.** A table-of-contents header, banner-delimited sections, no orphaned/unused selectors, and no historical "AR##"/retrofit narration comments. Comments explain *current* intent only.
- Every UX milestone must leave the build green: `tsc --noEmit` clean and the backend suite unaffected (`python -m unittest discover -s backend/tests`).
- This plan does not modify or supersede `docs/02_…Milestones.md` or `docs/04_…Audit_Remediation_Milestones.md`. The `UX` prefix is deliberately disjoint from `M`- and `AR`-series numbering.
- Per house rules, add a short change note in `docs/milestones/` (e.g. `UX0_design_language.md`) when each milestone ships, and update `STATUS.md`.

---

## Milestone map

| ID | Title | Audit IDs | Phase | Effort |
|----|-------|-----------|-------|--------|
| UX0 | Establish the design language (single source of truth) | M5, root cause | 0 Foundation | M |
| UX1 | Remove all Google / external UI dependencies (self-host fonts + icons + avatars) | M2, icon-font risk | 0 Foundation | M–L |
| UX2 | Scrub Stitch wording + re-architect `globals.css` into sections | M5, mn4 | 0 Foundation | M |
| UX3 | Repair the Search surface (orphaned classes / unstyled results) | C1 | 1 Structural | M |
| UX4 | Render grounded answers as Markdown | C2 | 4 RAG | M |
| UX5 | Inline citation anchoring (claim → source) | C3 | 4 RAG | L |
| UX6 | Search facets, sort, and labeled relevance | M7 | 4 RAG | M |
| UX7 | IA & dead-control cleanup (admin nav grouping, label consistency, remove fake controls) | M1, M3, M4 | 1–2 Structural/Nav | M |
| UX8 | Accessibility baseline (focus, live regions, names, contrast) | C4, mn6 | 5 A11y | M–L |
| UX9 | Responsiveness pass (breakpoints, evidence rail drawer) | M6, mn7 | 5 Responsive | M |
| UX10 | Finish pass (states, copy, micro-interactions) | mn1–mn5, polish | 6 Polish | S–M |

Dependency spine: **UX0 → UX1, UX2 → (UX3 … UX10)**. UX1 and UX2 may run in parallel after UX0. UX3–UX10 each depend on UX0 (and on UX2 for class names).

---

## Milestone UX0 — Establish The Design Language (Gate UX0: one written source of truth)

**Why this is required**
The root cause of every consistency finding (M5, the dual `--color-*`/`--surface-*` token vocabularies, two button systems, orphaned classes) is the absence of a written design language. Without it, fixing individual screens produces new dialects. This milestone writes the grammar so the rest of the plan composes against it instead of inventing.

**What is not working today**
- Two button systems coexist (`.stitch-button*` and `.button*`); the `components/ui/*` primitives are used only by admin forms, not by chat/search.
- Two token vocabularies were retrofitted together (`web/app/globals.css` aliases an undefined `--color-*` set onto the `--surface-*` palette).
- No document tells a builder (human or agent) which button, table, spacing step, or pattern is canonical.

**Goal**
Produce a single, code-adjacent design-language reference and an agent-readable skill that encodes it, choosing the winners.

**Deliverables**
- `web/DESIGN.md` — the source of truth: **principles** (enterprise, dense-but-scannable, color-for-meaning-only); **tokens** (final palette decision, a fixed spacing scale e.g. 4/8/12/16/24/32, type scale, radii, shadows, semantic colors); **canonical components** (one Button + variants, Input/Select/Textarea/Toggle via `components/ui/*`, one Table = `admin-data-table`, Card, Badge, Tabs, Dialog, EmptyState, Toolbar); **patterns** (data-table, master/detail, answer+citation, form); and an explicit **"do not"** list (no second button system, no external assets, no bespoke one-off classes).
- A re-evaluation of the cream/lime/olive palette against the enterprise principle, with the decision recorded in `DESIGN.md` (keep, or move to a restrained neutral + single accent + semantic states). Whatever is decided becomes the only palette.
- `.claude/skills/design-language/SKILL.md` (or equivalent) mirroring `DESIGN.md` so any agent building UI loads the rules first. (See prompt updates in `CLAUDE.md`/`AGENTS.md`.)
- A short "winners" decision log: the existing `.stitch-button*` system is the canonical Button (kept as-is, **not renamed**); `admin-data-table` → canonical Table; `components/ui/*` → canonical form controls; `--surface-*` → canonical tokens (the `--color-*` aliases are slated for deletion in UX2).

**DoD**
- `web/DESIGN.md` exists and names exactly one canonical choice per component/token category.
- The skill file exists and is referenced by the execution prompts.
- No code changes required to render; this milestone is documentation + decisions. `tsc --noEmit` unaffected.

**Re-run checks**
- `make reader-clarity-check` passes (new doc linked from README reader paths / STATUS).

**Priority:** P0 · **Effort:** M · **Depends on:** none

---

## Milestone UX1 — Remove All Google / External UI Dependencies (Gate UX1: the UI renders fully offline)

**Why this is required**
The console currently depends on `fonts.googleapis.com` for **Inter** and for the **Material Symbols** icon font (`web/app/layout.tsx`, 4 link lines) and on `lh3.googleusercontent.com` for **8 hardcoded avatar/image URLs**. If any of these fail to load — locked-down enterprise network, CSP, air-gapped deploy, expired URL — the UI degrades badly: ~90 icon usages render as literal ligature words ("search", "send", "bolt"), and user "avatars" are AI-generated stock faces served from Google. This is both a trust/privacy problem (M2) and a hard reliability problem.

**What is not working today**
- `app/layout.tsx`: `<link>` preconnect + stylesheet to `fonts.googleapis.com` / `fonts.gstatic.com` for Inter and Material Symbols Outlined.
- ~90 `material-symbols` icon usages across `components/**` depend on the CDN icon font (17 supporting rules in `globals.css`).
- 8 `googleusercontent`/`aida-public` image URLs hardcoded across `console-shell.tsx`, `auth-card.tsx`, `dev-login-form.tsx`, `public-pages.tsx`, `sources-page.tsx`, and several admin panels.

**Goal**
Make the UI fully self-contained: no runtime dependency on any Google or third-party host for fonts, icons, or images.

**Deliverables**
- **Self-host Inter** via `next/font/local` (bundled woff2), removing the `googleapis`/`gstatic` `<link>`s. Set it as the body font with a proper system fallback stack.
- **Replace the Material Symbols icon font** with a bundled inline-SVG icon set (e.g. a single `components/icons.tsx` mapping the ~30 distinct glyphs actually used — search, send, bolt, auto_awesome, thumb_up/down, content_copy, attach_file, image, mic, database, notifications, settings, the admin nav glyphs, etc.). The existing `components/icons.tsx` is the home for this. Remove the icon-font `<link>` and the `material-symbols` CSS once usages are migrated.
- **Replace the 8 external images** with a self-hosted initials/monogram avatar (deterministic from name/email) or a bundled local asset. No component may reference `googleusercontent`.
- A guard note in `DESIGN.md` and the execution prompts: external UI hosts are prohibited.

**DoD**
- Zero matches for `googleapis`, `gstatic`, `googleusercontent`, or `material-symbols` under `web/app`, `web/components`, `web/lib` (the icon font is gone; icons are inline SVG).
- The app renders correctly with the network blocked (manual check: DevTools offline, fonts/icons/avatars all present).
- `tsc --noEmit` clean; no visual regression on chat/admin (icons present, fonts applied).

**Re-run checks**
- Manual offline render check (documented in the milestone note); `next build` succeeds with no external font fetch in the build log.

**Priority:** P0 · **Effort:** M–L · **Depends on:** UX0

---

## Milestone UX2 — Scrub Stitch Wording + Re-architect `globals.css` (Gate UX2: one button system, sectioned stylesheet, no Stitch wording)

**Why this is required**
Shipped code still *reads* like a design-tool export. Of the ~88 `stitch` references, most are the **working `.stitch-button*` class system** (functional — fine to keep), but some are **comments and user-facing copy** (e.g. "stitched thread"), alongside 7 retrofit/`AR##` narration comments in `globals.css`. The wording signals "prototype", the flat 6,170-line stylesheet has no navigable structure, and two button systems (`.stitch-button*` vs `.button*`) still drift (M5). **Renaming the `stitch-*` class identifiers app-wide is intentionally out of scope** — it touches 14 component files + 12 CSS blocks for no functional gain and is regression-prone. This milestone removes the *textual* Stitch mentions, consolidates the two button systems (keeping `.stitch-button*` as the survivor), and makes `globals.css` readable — without renaming live class identifiers.

**What is not working today**
- Two button systems coexist: `.stitch-button*` and `.button*`.
- The word *Stitch*/"stitched" appears in code comments and user-facing copy.
- Orphaned classes behind Search (`workspace-panel`, `panel-toolbar`, `inventory-table`, `inventory-row`, `inventory-title`, `table-subtle` — 0 definitions) still referenced by `search-workspace.tsx` (repaired structurally in UX3; the dead names are cleaned here).
- `globals.css` is one flat 6,170-line file with retrofit/`AR##` comments and no section map.

**Goal**
Remove Stitch wording, collapse to one button system (keeping the existing `.stitch-button*` class as canonical), delete dead selectors, and restructure `globals.css` into a standard, readable, sectioned stylesheet — all without renaming live class identifiers.

**Deliverables**
- **One button system:** migrate the few `.button*` usages onto the existing `.stitch-button*` system and delete the `.button*` system. **Do not rename `.stitch-button*`** — it is the canonical Button per UX0.
- **Scrub Stitch wording:** remove the word *Stitch*/"stitched" from code comments and user-facing copy ("stitched thread" → "thread"/"saved thread"); add no new Stitch-origin comments. `stitch-*` **class identifiers may remain**.
- **Delete dead/orphaned and aliased selectors:** remove the unused `--color-*`/`--border-radius-*` alias block once panels reference canonical tokens; remove selectors with no live usage.
- **`globals.css` architecture:** add a table-of-contents header listing sections, then banner-delimited sections in a standard order — `1. Tokens (:root)` → `2. Base/reset & typography` → `3. Layout shells (workspace/admin)` → `4. Navigation` → `5. Components (buttons, controls, tables, badges, cards, tabs, dialogs)` → `6. Chat & evidence` → `7. Search` → `8. Admin panels` → `9. Public/marketing` → `10. Responsive overrides`. Strip all `AR##`/historical narration comments; keep only comments that explain current non-obvious intent. Consider splitting into a small set of imported partials if the team prefers, but a sectioned single file satisfies the gate.

**DoD**
- No occurrences of the word "stitch"/"Stitch" in **comments or user-facing strings** under `web/app`, `web/components`, `web/lib` (the `stitch-*` class identifiers are intentionally excluded from this check and may remain).
- Exactly one button class system remains (`.stitch-button*`); `.button*` is deleted.
- `globals.css` opens with a section map; every section is banner-delimited; no `AR##` narration comments remain; no orphaned selectors (spot-checked).
- `tsc --noEmit` clean; no visual regression.

**Re-run checks**
- Grep gate (stitch wording in comments/strings only); manual pass over chat + 3 admin panels for button/visual parity.

**Priority:** P0 · **Effort:** M · **Depends on:** UX0 (canonical choices); coordinate with UX3 (Search) on shared classes.

---

## Milestone UX3 — Repair The Search Surface (Gate UX3: Search renders as the design system)

**Why this is required**
`C1`: `search-workspace.tsx` is built entirely on undefined classes, so one of the two primary retrieval surfaces renders as raw, unlabeled stacked `<div>`s (five fields per row including a bare `score.toFixed(3)` float). It looks broken and contradicts the product's trust goal at first contact.

**Goal**
Rebuild Search results on the canonical Table/result-card and control patterns from `DESIGN.md`.

**Deliverables**
- Replace orphaned classes with the canonical `admin-data-table` (or a purpose-built result-card list) — sticky header, zebra rows, real **column headers**, padding.
- Replace the raw score float with a **labeled relevance indicator** (bar + value, with a tooltip explaining the score), and show a **result count**.
- Route the search toolbar (input, mode select, button) through the canonical control + Button components.

**DoD**
- No undefined classes remain in `search-workspace.tsx`; results have labeled columns and a relevance affordance.
- Visual parity with the rest of the console; `tsc --noEmit` clean.

**Re-run checks**
- Manual: run a search, confirm headers/labels/relevance render; empty/loading/no-result states intact.

**Priority:** P1 · **Effort:** M · **Depends on:** UX0, UX2

---

## Milestone UX4 — Render Grounded Answers As Markdown (Gate UX4: structured answers survive)

**Why this is required**
`C2`: answers are rendered by `message.content.split(/\n+/)` into `<p>` tags (`chat-workspace.tsx`), flattening lists, tables, headings, code, and bold — exactly the structure enterprise answers rely on.

**Goal**
Render answer content as sanitized Markdown with typographic styles consistent with `DESIGN.md`.

**Deliverables**
- Sanitized Markdown rendering for assistant answers (lists, tables, code, headings, emphasis), with a constrained reading measure for long text.
- Typography tokens applied so answer body, citations, and metadata remain visually differentiated.

**DoD**
- A structured answer (list + table) renders correctly; sanitization verified (no raw HTML injection).
- `tsc --noEmit` clean; no regression to citation pills/evidence rail.

**Re-run checks**
- Manual answer render of a multi-section response.

**Priority:** P1 · **Effort:** M · **Depends on:** UX0

---

## Milestone UX5 — Inline Citation Anchoring (Gate UX5: claims map to sources)

**Why this is required**
`C3`: citations appear only as filename pills/rail entries, with no inline `[1]/[2]` markers tying sentences to sources. Provenance is the product's core value; today it is asserted, not demonstrated at claim level.

**Goal**
Anchor citations inline in the answer and link them to the existing evidence rail + chunk-context machinery.

**Deliverables**
- Parse/emit citation markers and render them inline as superscript chips.
- Hover/click on an inline marker highlights and scrolls to the matching evidence card and chunk-context (plumbing already exists in `chat-workspace.tsx`).

**DoD**
- Inline markers render, are keyboard-focusable with accessible names, and drive the rail selection.
- `tsc --noEmit` clean.

**Re-run checks**
- Manual: click an inline marker → correct evidence card highlights and chunk context loads.

**Priority:** P1 · **Effort:** L · **Depends on:** UX0, UX4

---

## Milestone UX6 — Search Facets, Sort, And Labeled Relevance (Gate UX6: experts can narrow & trust ranking)

**Why this is required**
`M7`: Search offers only a mode select — no facets (source type, corpus, freshness, date), no sort, no result count, no explained relevance. Repeated expert search is inefficient.

**Goal**
Add faceting, sorting, and a labeled relevance model to Search.

**Deliverables**
- Facet controls (source type, corpus, freshness, date) and a sort control, built on canonical components.
- Result count + the labeled relevance indicator from UX3 carried through.

**DoD**
- Facets/sort filter and reorder results; counts update; controls match the design system.
- `tsc --noEmit` clean.

**Re-run checks**
- Manual facet/sort interaction over a seeded corpus.

**Priority:** P2 · **Effort:** M · **Depends on:** UX0, UX3

---

## Milestone UX7 — IA & Dead-Control Cleanup (Gate UX7: navigation is coherent, no fake controls)

**Why this is required**
`M3` (flat 18-item admin sidebar), `M4` (topbar says "Ask/Search" while the sidebar says "Chat"; Search hidden in a toggle), and `M1` (fake `readOnly` ⌘K/search inputs; permanently `disabled` Settings/attach/image/mic/Export with "not wired yet" tooltips) together make the app feel like a demo and cause hesitation.

**Goal**
Group admin navigation, align nav vocabulary, and remove or honestly label non-functional controls.

**Deliverables**
- Group `lib/admin-modules.ts` into labeled, collapsible sections (Operate / Retrieval / Data / Governance) with Overview pinned.
- Reconcile nav labels (one verb set; surface Search in the workspace sidebar).
- Remove or hide fake/disabled controls; where a roadmap teaser is wanted, use an explicit "Coming soon" affordance, not a dead toolbar item.

**DoD**
- Admin sidebar is grouped; workspace nav labels are consistent and Search is discoverable; no `readOnly`/`disabled` "not wired yet" controls remain in primary chrome.
- `tsc --noEmit` clean.

**Re-run checks**
- Manual nav walkthrough (workspace + admin).

**Priority:** P2 · **Effort:** M · **Depends on:** UX0, UX2

---

## Milestone UX8 — Accessibility Baseline (Gate UX8: keyboard + screen-reader usable)

**Why this is required**
`C4`/`mn6`: ~5 focus rules and ~20 `aria-label`s across the app, **no `aria-live`** for the streaming progress/answer, icon-only buttons without names, and likely contrast failures on the cream palette. Enterprise procurement commonly requires WCAG/VPAT conformance.

**Goal**
Bring the console to a defensible WCAG 2.1 AA baseline.

**Deliverables**
- A global visible focus ring on all interactive elements; remove inert focusable fake inputs (done in UX7).
- `aria-live="polite"` on the chat progress card and completed answer; `role`/labels on tablists, dialogs, and status regions.
- Accessible names on every icon-only button (new-thread, feedback, composer tools).
- Contrast audit of muted/label/accent text against the final palette; fix failures (ties to the UX0 palette decision).

**DoD**
- Keyboard-only walkthrough of chat + search + one admin panel succeeds with visible focus throughout.
- Automated check (e.g. axe) reports no critical violations on chat and search.
- `tsc --noEmit` clean.

**Re-run checks**
- Keyboard + screen-reader smoke pass; axe scan on two core routes.

**Priority:** P2 · **Effort:** M–L · **Depends on:** UX0 (palette), UX7

---

## Milestone UX9 — Responsiveness Pass (Gate UX9: usable on small laptop & tablet)

**Why this is required**
`M6`/`mn7`: only 4 media queries in 6,170 CSS lines; chat is a fixed `1fr/320px` grid; the evidence rail is a sticky, height-capped column (double scroll). Narrow laptops, tablets, and mobile crowd and overflow.

**Goal**
Add intermediate breakpoints and make dense surfaces degrade gracefully.

**Deliverables**
- Intermediate breakpoints (e.g. 1280/1024/768) in the new `globals.css` responsive section.
- Evidence rail becomes a drawer/sheet below ~1024px; chat metadata bar wraps cleanly.
- Pressure-test admin wide tables and 4/5-column filter grids.

**DoD**
- Chat, search, and one dense admin panel render without overflow at 1280 / 1024 / 768 widths.
- `tsc --noEmit` clean.

**Re-run checks**
- Manual responsive check at the three widths.

**Priority:** P3 · **Effort:** M · **Depends on:** UX0, UX2

---

## Milestone UX10 — Finish Pass (Gate UX10: production feel)

**Why this is required**
`mn1–mn5` and polish: prose placeholders leak ("Captured"/"Unavailable"), internal jargon surfaces ("Path:"), vocabulary is inconsistent, the inline access-request form is overlong inside the answer bubble, and the loading spinner relies on a glyph.

**Goal**
Final consistency and micro-interaction pass.

**Deliverables**
- Replace prose placeholders with skeletons/em-dashes; remove/explain internal jargon in user-facing chrome.
- Standardize product vocabulary (glossary in `DESIGN.md`).
- Move the long inline access-request form to a side panel/modal.
- Consistent hover/active/selected states; explicit CSS spinner; ⌘/Ctrl+Enter to submit the composer.

**DoD**
- No prose placeholders or raw internal terms in primary user chrome; consistent states across canonical components.
- `tsc --noEmit` clean.

**Re-run checks**
- Manual pass over chat, search, sources, one admin panel.

**Priority:** P3 · **Effort:** S–M · **Depends on:** UX0–UX9

---

## Closing note

The findings list is the symptom set; **UX0 is the cure for the root cause (drift).** Without it, UX3–UX10 could all land and the console would slowly re-drift the next time a screen is added, because nothing would stop it. The execution prompts (`CLAUDE.md`, `AGENTS.md`) are updated to make the design language, the no-external-dependency rule, and the no-Stitch-wording/sectioned-CSS rules binding on all future UI work — not just this plan. (Existing `stitch-*` class identifiers are deliberately preserved; only Stitch *wording* in comments/copy is removed.)
