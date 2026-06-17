---
name: design-language
description: Enterprise RAG console UI design language. Load BEFORE building or changing any UI under web/ — defines the canonical tokens, button/table/form components, patterns, and the hard "do not" rules (no external deps, no second button system, no new Stitch wording). Mirrors web/DESIGN.md.
---

# Design Language — Enterprise RAG Console

**Read `web/DESIGN.md` (the source of truth) before any UI work.** This skill is its agent-facing summary. If the two ever disagree, `web/DESIGN.md` wins.

## Principles
Enterprise operations console, not a marketing site. Dense-but-organized over spacious-but-vague. Color = meaning only. One way to do a thing. Self-contained (renders network-blocked). Provenance is first-class.

## Tokens (only from `app/globals.css :root` — never hardcode hex)
- Surfaces: `--surface #fbfbe6`, `--surface-low`, `--surface-panel #fff` (working surface), tan steps; text `--ink #1b1d10`, `--muted #586373`; borders `--outline-strong`.
- Brand/semantic: `--primary #0e11d8` / `--primary-strong`; `--primary-soft` (focus/info); `--hero-gradient` (primary button only); `--lime` = **accent only, never status**; success `--success-bg/ink`, danger `--danger/-soft`, warning `#f7e6bf/#7a5200`.
- Spacing scale: 4/8/12/16/24/32/48 (migrate toward it; add no arbitrary values).
- Radii: 10 (controls/tables/cards) / 14 / 16 (buttons; small 12); pills 999.
- Type: Inter (self-hosted) + system fallback; table .82rem, label .78/700, help/error .75, badge .68/900 uppercase, button .96/700 (small .82). Keep answer body / citations-metadata / labels visually distinct.

## Palette decision (UX0)
Keep the current palette. Status = semantic tokens only; lime is accent not status; primary indigo for actions/links/focus/selection. A neutral re-skin is out of scope. Verify muted-on-tan contrast in UX8.

## Canonical components (use these; never a second variant)
- Button: `.stitch-button` + `-primary/-secondary/-white/-outline-light/-small/-block`. The `.button*` system is being deleted (UX2). Do NOT rename `.stitch-button*`.
- Controls: `components/ui/TextInput|NumberInput|Select|Textarea|Toggle|Field|FormActions` (`.ui-control*`, `.ui-field*`).
- Table: `.admin-table-scroll` > `.admin-data-table` (sticky header, zebra, real column headers). Master/detail: `.admin-sticky-detail`.
- Badge/status: `.badge` + `-is-good/-is-warning/-is-danger` (semantic only).
- Icons: inline SVG in `components/icons.tsx` (no icon font, no CDN). Avatars: local initials/monogram (no external hosts).

## Patterns
Data-table (wrap + headers, never bare/unlabeled rows). Master/detail (sticky reveal-on-select). Answer+citation (Markdown body → inline markers → evidence rail → chunk-context). Form (Field + ui/* control + FormActions). Every data surface needs empty/loading/error states; loading uses a CSS spinner.

## DO NOT
- No second button system or one-off button class.
- No new token/hex/spacing outside `:root` + `web/DESIGN.md`.
- No external/CDN UI dependency (Google Fonts, Material Symbols icon font, `googleusercontent`/third-party images). Must render network-blocked.
- No new `stitch-*` class names and no Stitch wording in comments/copy (existing `stitch-*` identifiers stay).
- Lime (or any non-semantic color) for status.
- Bare tables / unlabeled rows. Newline-split answer rendering (use Markdown).
- CSS rules outside their section; orphaned selectors; `AR##` narration comments.
