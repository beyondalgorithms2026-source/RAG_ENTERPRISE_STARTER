# web/DESIGN.md — Console Design Language (single source of truth)

> **Status:** Canonical. Established by Milestone **UX0** (`docs/05_Enterprise_RAG_UIUX_Audit_Remediation_Milestones.md`).
> Any agent or engineer building or changing UI under `web/` **must read this first and obey it.**
> The mirror at `.claude/skills/design-language/SKILL.md` exists so agents load these rules automatically.
> This milestone is **decisions + documentation only** — it records the canonical choices that already
> exist in the codebase and the rules that govern future work. It changes no rendering.

---

## 1. Principles

1. **Enterprise operations console, not a marketing site.** Optimize for clarity, scanability, repeated expert use, and trust — not delight or spectacle.
2. **Dense but organized beats spacious but vague.** Prefer labelled, grouped, scannable density. Every number gets a label.
3. **Color carries meaning, not decoration.** Status/emphasis come from a fixed semantic set; the lime accent is not a status color.
4. **One way to do a thing.** One button system, one table, one set of form controls, one token vocabulary. If a pattern exists here, reuse it; do not invent a parallel.
5. **Self-contained and trustworthy.** No external/CDN runtime dependency for fonts, icons, or images. The UI must render fully with the network blocked.
6. **Provenance is the product.** Citation, source, freshness, and retrieval-path cues are first-class and must stay legible.

---

## 2. Tokens (canonical = the `:root` vars in `app/globals.css`)

The CSS custom properties in `app/globals.css :root` are the **only** token source. Do not hardcode hex values in components or introduce new variables without updating this file.

### 2.1 Color — surfaces & ink
| Token | Value | Use |
|-------|-------|-----|
| `--surface` | `#fbfbe6` | App canvas |
| `--surface-low` | `#f5f5e0` | Secondary surface, zebra rows, secondary button |
| `--surface-panel` | `#ffffff` | Cards, controls, tables — the working surface |
| `--surface-high` / `--surface-highest` / `--surface-mid` | tan steps | Table headers, toggles, hover |
| `--ink` | `#1b1d10` | Primary text |
| `--muted` | `#586373` | Secondary text, labels, metadata |
| `--outline` / `--outline-strong` | `rgba(198,197,217,.24/.42)` | Borders |

### 2.2 Color — brand & semantic
| Token | Value | Use |
|-------|-------|-----|
| `--primary` / `--primary-strong` | `#0e11d8` / `#343ced` | Primary actions, links, focus |
| `--primary-soft` | `#e0e0ff` | Focus ring, info backgrounds |
| `--hero-gradient` | indigo gradient | Primary button background only |
| `--lime` / `--lime-ink` | `#cdf13d` / `#171e00` | **Accent only** (marketing/illustration). **Never** a status color. |
| `--success-bg` / `--success-ink` | `#dff6e7` / `#1c6b3e` | Success / "fresh" |
| `--danger` / `--danger-soft` | `#ba1a1a` / `#ffdad6` | Error / "stale" |
| warning | `#f7e6bf` bg / `#7a5200` ink | Warning |

### 2.3 Palette decision (V2, supersedes UX0)
**V2 (2026-07-07): the surface system moved from the tan palette to cool neutrals** (`--surface #f6f7fb`, tan `--surface-*` steps → cool grey steps, `--ink #14161f`) as part of the V2 workflow-console redesign, and a dark navigation rail was introduced (`--rail-bg #12141f`, `--rail-ink`, `--rail-active`, `--rail-line`). Semantic tokens (success/warning/danger/primary/lime) are unchanged. The governing rules below still hold:
- **Status = semantic tokens only** (success / warning / danger + primary for info). No ad-hoc status colors.
- **Lime is accent, not status** — restricted to marketing/illustrative surfaces; never used to signal state in the console.
- **Primary indigo** = primary actions, links, selection, focus.
- A future move to a more neutral operations palette is **out of scope** here; if ever taken, it changes only these tokens, not component structure.
- **Contrast:** small muted/label text on tan surfaces is the known risk — verify against WCAG AA in UX8 and adjust the token if it fails. Do not introduce lighter greys.

### 2.4 Spacing
Use a **4-based scale: 4 / 8 / 12 / 16 / 24 / 32 / 48**. Existing components cluster on `6/8/10/12/18` — when editing, migrate toward the scale; do not add new arbitrary values.

### 2.5 Radii
`10px` (controls, tables, cards), `14px` (panels), `16px` (buttons; small button `12px`); pills/badges `999px`. The admin panels reference these via the `--border-radius-md/lg/xl` aliases in `:root` (consumed by inline styles); CSS rules use the raw values.

### 2.6 Typography
- **Font:** Inter (self-hosted as of UX1) with a system fallback stack. `--font-mono` for code/JSON.
- **Scale (as used today):** body ~1rem; table `0.82rem`; field label `0.78rem/700`; help/error `0.75rem`; badge `0.68rem/900` uppercase; primary button `0.96rem/700`, small button `0.82rem`. Headings via the shell heading styles.
- Differentiate **answer body** (readable measure), **citations/metadata** (`--muted`, smaller), and **labels** (uppercase-ish, bold) — never render them at the same weight/size.

### 2.7 Shadows
`--ambient` (cards), `--ambient-lg` (elevated/overlays). Do not invent new shadow values.

---

## 3. Canonical components (the "winners")

> When a screen needs one of these, use the canonical class/primitive below. Do **not** create a second variant.

| Need | Canonical | Notes |
|------|-----------|-------|
| **Button** | `.stitch-button` + `-primary` / `-secondary` / `-white` / `-outline-light` / `-small` / `-block` | The single button system. The legacy `.button*` system is being removed (UX2). **Do not rename** `.stitch-button*` — the name is retained deliberately; only Stitch *wording* in comments/copy is scrubbed. |
| **Text input / number** | `components/ui/TextInput`, `NumberInput` (`.ui-control`) | Boxed control on `--surface-panel`, 38px min-height, shared focus ring. |
| **Select** | `components/ui/Select` (`.ui-control.ui-select`) | Custom chevron, no native appearance. |
| **Textarea** | `components/ui/Textarea` (`.ui-control.ui-textarea`) | |
| **Toggle / checkbox** | `components/ui/Toggle` (`variant="switch"` or `"checkbox"`) | |
| **Field wrapper** | `components/ui/Field` (`.ui-field` + `-label`/`-help`/`-error`) | Label + help/error grid. |
| **Form actions row** | `components/ui/FormActions` (`.ui-form-actions`) | |
| **Data table** | `.admin-table-scroll` > `.admin-data-table` | Sticky header, zebra rows, hover, padding. The one table look. |
| **Master/detail sticky pane** | `.admin-sticky-detail` | Keeps a detail pane in view while a list scrolls. |
| **Badge / status** | `.badge` + `-is-good` / `-is-warning` / `-is-danger` | Semantic colors only. |
| **Icon** | `components/icons.tsx` → `<MaterialIcon name="…" />` | Inline SVG, no icon font / CDN. Unknown names fall back to a neutral glyph. Sized via the `.app-icon` CSS rule. |
| **Avatar** | `components/icons.tsx` → `<Monogram seed="…" />` | Deterministic local initials avatar. No external image hosts. |

Form controls in chat/search currently use bespoke markup; new/edited forms should route through `components/ui/*`.

---

## 4. Patterns

- **Data-table pattern:** wrap `.admin-data-table` in `.admin-table-scroll`; always provide real column headers; for long lists pair with `.admin-sticky-detail`. Never render a bare `<table>` or unlabeled stacked `<div>` rows.
- **Master/detail:** list on one side, sticky detail pane (`.admin-sticky-detail`) that reveals-on-select (scrollIntoView). Used by Sources/Jobs/Audit Log.
- **Answer + citation pattern:** answer body (Markdown, UX4) → inline citation markers (UX5) → evidence rail cards (`chat-evidence-*`) → chunk-context card with neighbors + freshness + open-source link. Keep these four layers visually distinct.
- **Form pattern:** `Field` (label + help/error) wrapping a `ui/*` control; actions in `FormActions`. Validation errors via `.ui-field-error` / `is-invalid`.
- **Empty / loading / error states:** every data surface needs all three; reuse the existing empty-card pattern; loading uses an explicit CSS spinner (not a glyph). For tabular/list surfaces whose loaded shape is known, loading may instead render `.skeleton-line` placeholder rows inside the real layout (shimmer over `--surface-high`/`--surface-low`; static under `prefers-reduced-motion`); mark the skeleton container `aria-hidden` and give the wrapper `role="status"` with an accessible label.
- **Mobile nav drawer:** at ≤820px the workspace/admin sidebar becomes a fixed off-canvas drawer (`.is-mobile-open` on the sidebar) opened by the topbar `.shell-nav-toggle` hamburger, with a `.shell-nav-backdrop` scrim (same rgba scrim value as the modal backdrop). It closes on backdrop click, Escape, and route change; focus moves into the drawer on open (`tabIndex={-1}` on the sidebar); the closed drawer is `visibility: hidden` so it stays out of the tab order. Both elements are inert on wider viewports. On phones the inert coming-soon search boxes and the topbar viewer chip are hidden to make room (identity remains in the avatar and sidebar footer).
- **Keyboard-submit hint:** the chat composer shows the `⌘/Ctrl + Enter` shortcut as a muted `.chat-composer-hint` beside the primary action (`aria-hidden`, hidden ≤768px).
- **Skip link:** both console shells render an `<a href="#console-main" class="skip-link">` as the first focusable element; it is visually hidden until keyboard-focused, then appears over the shell and jumps focus past the navigation.
- **Interaction states:** interactive surfaces use short (120–160ms) `ease` transitions on background/color/box-shadow only. The active sidebar route additionally shows a 3px primary leading-edge bar (`::before` on the canonical link classes); the composer signals focus with a card-level `:focus-within` ring (`--primary-soft`) instead of an inner control ring. A global `prefers-reduced-motion: reduce` override collapses all transitions/animations.
- **Coming-soon pattern:** controls that are intentionally not wired yet are **preserved, not removed**, and marked consistently: keep them `disabled` (or `readOnly`/`tabIndex={-1}` for inputs), set `title="Coming in a later release."`, give an accessible name suffixed `(coming soon)`, and show a `.coming-soon-badge` ("Soon") pill on labelled controls or the `.is-coming-soon` accent dot on icon-only controls. Do not invent per-control wording.

---

## 4b. V2 workflow console (workspace shell + surfaces)

The user workspace runs on the V2 system (globals.css §12, `v2-*` classes); the admin console keeps the §8 shell and canonical data tables.

- **Shell:** `.v2-shell` = dark icon rail (`.v2-rail`, `.v2-rail-link` with icon + short uppercase label, `is-active` state) + top command bar (`.v2-topbar` with `.v2-command` query form that routes to Ask, plus governance `.v2-chip`s). The rail becomes the mobile drawer via the existing `.shell-nav-toggle`/`.shell-nav-backdrop` pattern at ≤820px.
- **Page scaffold:** `.v2-page` (constrained grid) + `.v2-kicker`/`.v2-page-head`/`.v2-page-sub`; content lives in `.v2-panel` cards and `.v2-columns` two-column grids.
- **Metric cards:** `.v2-metric-grid` > `.v2-metric-card` (label / large value / note). Real, committed numbers are presented plainly; illustrative data must carry the `.v2-demo-chip` "Sample data" marker — never present sample values as live.
- **Status chips:** `.v2-status-chip` + `is-pass` / `is-fail` / `is-review` (semantic tokens only). Shell/posture chips: `.v2-chip` + `is-on` / `is-wait` / `is-alert`.
- **Timeline:** `.v2-timeline` ordered list with `.v2-timeline-dot` (+`is-unread`) — used for workflow/audit event feeds.
- **Result cards (Search):** `.v2-result-list` > `.v2-result-card` (rank, source glyph, title/locator, relevance bar, 3-line clamped snippet, `.v2-tag`s + freshness chip + "Ask about this" bridge). This supersedes the UX3 results table **for the Search workspace surface only**; `.admin-data-table` remains the canonical table for admin/operator data.
- **Approval gate:** `.v2-review-card` (pending review with reviewer-note `Field` + timed-grant actions), `.v2-request-card` with `.v2-request-trail` event list, and the timeline feed. All states are live backend data.
- **Distribution bar:** `.v2-dist-bar` > `.v2-dist-segment` (`is-pass`/`is-manual`/`is-fail`, semantic colors).

## 5. Do NOT

- ❌ Add a **second button system** or any one-off button class. Use `.stitch-button*`.
- ❌ Introduce a **new token / hex / spacing value** outside `:root` + this file.
- ❌ Add any **external/CDN UI dependency** — Google Fonts, Material Symbols (or any) icon font, `googleusercontent`/third-party image hosts. The UI must render network-blocked.
- ❌ Add **new `stitch-*` class names** or any **Stitch wording** in comments/user-facing copy. (Existing `stitch-*` identifiers stay.)
- ❌ Use **lime** (or any non-semantic color) to signal status.
- ❌ Render a **bare table** or **unlabeled rows** (the Search-surface defect, C1).
- ❌ Render answer content by splitting on newlines (use Markdown, UX4).
- ❌ Add rules to `globals.css` outside their **section**, or leave **orphaned/unused** selectors or `AR##` narration comments.

---

## 5b. Glossary (standard product vocabulary)

Use these terms consistently in UI copy, labels, and nav (set in UX10):

- **Ask** — the grounded chat surface (`/console/workspace/chat`). Not "Chat".
- **Search** — keyword/semantic/hybrid retrieval over the corpus (`/console/workspace/search`).
- **History** — saved Ask threads in this browser. Not "Search History".
- **Thread** — one saved Ask conversation. Not "stitched thread".
- **Source** — an ingested document/record. **My Sources** is the user's visible set.
- **Citation** — a cited source backing an answer; rendered inline as a numbered chip and in the evidence rail.
- **Evidence** — the retrieved citations + chunk context shown in the right rail.
- **Corpus** — a named grouping of sources; unassigned sources read "Unassigned".
- **Freshness** — fresh / stale / unknown recency state of a source.
- **Route** — how an answer was retrieved (user-facing label for the internal "retrieval path").
- **Relevance** — a result's retrieval score; shown as a bar relative to the top result (not an absolute confidence).
- **Coming soon** — an intentionally-not-wired control, preserved and marked per the Coming-soon pattern.
- Placeholders for missing values use an em dash (`—`), never prose like "Unavailable"/"Captured".

## 6. Where things live

- Tokens + all CSS: `web/app/globals.css` (kept sectioned with a TOC header from UX2 onward).
- Form primitives: `web/components/ui/*`.
- Icons: `web/components/icons.tsx`.
- Shells/nav: `web/components/console-shell.tsx`, `web/lib/admin-modules.ts`, `web/app/console/**/layout.tsx`.
- Reference mockups (out of build, do not depend on): the original design reference (removed from this repository).
