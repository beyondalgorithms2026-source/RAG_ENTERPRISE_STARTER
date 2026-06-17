# UX1 — Remove All Google / External UI Dependencies

**Date:** 2026-06-17 · **Plan:** `docs/05_Enterprise_RAG_UIUX_Audit_Remediation_Milestones.md` · **Gate:** UX1 (the UI renders fully offline)

## Provenance

The console depended on `fonts.googleapis.com` (Inter + the Material Symbols icon font) and on `lh3.googleusercontent.com` for 8 hardcoded avatar/image URLs. A blocked network (locked-down enterprise, CSP, air-gapped, expired URL) degraded the UI badly: ~90 icon usages rendered as literal ligature words and "avatars" were AI-stock faces served from Google. UX1 makes the UI fully self-contained.

## Deliverables

- **Self-hosted Inter** (`app/layout.tsx`): `next/font/local` with 6 bundled woff2 weights (400/500/600/700/800/900) under `web/app/fonts/`; removed both `googleapis`/`gstatic` preconnect+stylesheet `<link>`s and the Material Symbols `<link>`. `body` font-family now `var(--font-inter), <system stack>`.
- **Inline-SVG icons** (`components/icons.tsx`): new `MaterialIcon` maps the app's glyph names to bundled line SVGs (≈55 base glyphs + alias table) with a neutral fallback so an unmapped name degrades gracefully instead of rendering text. **89 `material-symbols` span usages** across 16 components migrated to `<MaterialIcon name=… />` (static and dynamic `{item.icon}` cases). The CDN icon-font CSS was replaced: `.material-symbols-outlined` → `.app-icon`, sized in `em` so the existing per-context `font-size` rules keep controlling icon size; `.icon-fill` now bumps stroke weight instead of a font FILL axis.
- **Local avatars** (`components/icons.tsx`): new deterministic `Monogram` (initials + seeded hue). Replaced all 8 external images — viewer avatars in `console-shell` (removed the `brandAvatar` URLs), testimonial/team avatars in `public-pages`, and decorative art in `auth-card`/`public-pages` via a local `.media-placeholder` gradient block.

## DoD check

- **Zero matches** for `googleapis|gstatic|googleusercontent|material-symbols` under `web/app`, `web/components`, `web/lib` ✓ (grep clean).
- App renders **network-blocked** ✓ — verified via build artifacts: fonts bundled to `.next/static/media` (6 woff2), icons are inline SVG, avatars are local; no app code references any external host. (The only `fonts.googleapis.com/css` string in build output is an inert Next.js framework constant in `main.js`/`_error.js`, present regardless of usage; it does not reference our Inter/Material Symbols/avatars and triggers no fetch since `next/font/google` is never used.)
- `next build` succeeds ✓; `tsc --noEmit` clean ✓.

## Honest limits

- The inline icons are a clean, consistent **line-icon set**, not pixel-identical reproductions of Material Symbols; several related glyph names intentionally alias to one base glyph. Visual parity is "equivalent and on-brand," not "identical."
- A literal DevTools-offline screenshot was not captured in this headless run; the offline guarantee is evidenced by the source grep + bundled-font build artifacts + absence of any app-level external host reference.
- `.app-icon`/`.icon-fill`/`.monogram`/`.media-placeholder` were added near the existing icon CSS; full sectioning of `globals.css` is UX2.

**Next:** UX2 — scrub Stitch wording from comments/copy, collapse to one button system, delete dead selectors, and re-architect `globals.css` into a sectioned, TOC-headed stylesheet.
