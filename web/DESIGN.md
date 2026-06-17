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

### 2.3 Palette decision (UX0)
**Keep the current palette as canonical.** It is already applied consistently across chat + admin, and a full neutral re-skin is a large change with no functional gain. The governing rules going forward:
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
- **Empty / loading / error states:** every data surface needs all three; reuse the existing empty-card pattern; loading uses an explicit CSS spinner (not a glyph).
- **Coming-soon pattern:** controls that are intentionally not wired yet are **preserved, not removed**, and marked consistently: keep them `disabled` (or `readOnly`/`tabIndex={-1}` for inputs), set `title="Coming in a later release."`, give an accessible name suffixed `(coming soon)`, and show a `.coming-soon-badge` ("Soon") pill on labelled controls or the `.is-coming-soon` accent dot on icon-only controls. Do not invent per-control wording.

---

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
- Reference mockups (out of build, do not depend on): `web/stitch-reference/`.
