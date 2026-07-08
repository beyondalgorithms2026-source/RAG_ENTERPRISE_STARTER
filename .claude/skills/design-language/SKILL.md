---
name: design-language
description: Enterprise RAG console UI design language. Load BEFORE building or changing any UI under web/ — defines the canonical tokens, button/table/form components, patterns, and the hard "do not" rules (no external deps, no second button system, no new Stitch wording). Mirrors web/DESIGN.md.
---

# Design Language — Enterprise RAG Console

**Read `web/DESIGN.md` (the source of truth) before any UI work.** This skill is its agent-facing summary. If the two ever disagree, `web/DESIGN.md` wins.

## Principles
Enterprise operations console, not a marketing site. Dense-but-organized over spacious-but-vague. Color = meaning only. One way to do a thing. Self-contained (renders network-blocked). Provenance is first-class.

## Tokens (only from `app/globals.css :root` — never hardcode hex)
- Surfaces (V2 cool neutrals): `--surface #f6f7fb`, `--surface-low`, `--surface-panel #fff` (working surface), cool-grey steps; text `--ink #14161f`, `--muted #586373`; borders `--outline-strong`. Dark nav rail: `--rail-bg #12141f`, `--rail-ink`, `--rail-active`, `--rail-line`.
- Brand/semantic: `--primary #0e11d8` / `--primary-strong`; `--primary-soft` (focus/info); `--hero-gradient` (primary button only); `--lime` = **accent only, never status**; success `--success-bg/ink`, danger `--danger/-soft`, warning `#f7e6bf/#7a5200`.
- Spacing scale: 4/8/12/16/24/32/48 (migrate toward it; add no arbitrary values).
- Radii: 10 (controls/tables/cards) / 14 / 16 (buttons; small 12); pills 999.
- Type: Inter (self-hosted) + system fallback; table .82rem, label .78/700, help/error .75, badge .68/900 uppercase, button .96/700 (small .82). Keep answer body / citations-metadata / labels visually distinct.

## Palette decision (V2, supersedes UX0)
V2 (2026-07-07) moved surfaces to cool neutrals and added the dark rail. Status = semantic tokens only; lime is accent not status; primary indigo for actions/links/focus/selection.

## V2 workflow console (workspace)
The user workspace uses the `v2-*` system (globals.css §12): dark icon rail + command-bar shell (rail becomes the mobile drawer ≤820px), `.v2-page`/`.v2-panel` scaffolding, `.v2-metric-card` metric cards (illustrative values MUST carry the `.v2-demo-chip` "Sample data" marker), `.v2-status-chip is-pass/is-fail/is-review`, `.v2-timeline` audit feeds, `.v2-result-card` search results (supersedes the results table on Search only), and the approval-gate cards (`.v2-review-card`, `.v2-request-card`). Admin console keeps the §8 shell and `.admin-data-table`.

## Canonical components (use these; never a second variant)
- Button: `.stitch-button` + `-primary/-secondary/-white/-outline-light/-small/-block`. The `.button*` system is being deleted (UX2). Do NOT rename `.stitch-button*`.
- Controls: `components/ui/TextInput|NumberInput|Select|Textarea|Toggle|Field|FormActions` (`.ui-control*`, `.ui-field*`).
- Table: `.admin-table-scroll` > `.admin-data-table` (sticky header, zebra, real column headers). Master/detail: `.admin-sticky-detail`.
- Badge/status: `.badge` + `-is-good/-is-warning/-is-danger` (semantic only).
- Icons: inline SVG in `components/icons.tsx` (no icon font, no CDN). Avatars: local initials/monogram (no external hosts).

## Patterns
Data-table (wrap + headers, never bare/unlabeled rows). Master/detail (sticky reveal-on-select). Answer+citation (Markdown body → inline markers → evidence rail → chunk-context). Form (Field + ui/* control + FormActions). Every data surface needs empty/loading/error states; loading uses a CSS spinner, or `.skeleton-line` placeholder rows for tabular surfaces with a known loaded shape (aria-hidden skeleton inside a `role="status"` wrapper; static under reduced motion). Mobile nav drawer (≤820px): the sidebar becomes an off-canvas drawer (`.is-mobile-open`) opened by the topbar `.shell-nav-toggle`, with `.shell-nav-backdrop` scrim; closes on backdrop/Escape/route change, focus moves into the drawer. Shells start with a `.skip-link` to `#console-main` (hidden until keyboard focus). Interaction states: 120–160ms ease transitions on background/color/box-shadow; active sidebar route gets a 3px primary leading bar; composer focus = card-level `:focus-within` ring; global reduced-motion override collapses all motion.

## DO NOT
- No second button system or one-off button class.
- No new token/hex/spacing outside `:root` + `web/DESIGN.md`.
- No external/CDN UI dependency (Google Fonts, Material Symbols icon font, `googleusercontent`/third-party images). Must render network-blocked.
- No new `stitch-*` class names and no Stitch wording in comments/copy (existing `stitch-*` identifiers stay).
- Lime (or any non-semantic color) for status.
- Bare tables / unlabeled rows. Newline-split answer rendering (use Markdown).
- CSS rules outside their section; orphaned selectors; `AR##` narration comments.
