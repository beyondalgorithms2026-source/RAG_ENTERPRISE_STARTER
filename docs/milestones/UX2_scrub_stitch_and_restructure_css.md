# UX2 — Scrub Stitch Wording + Re-architect `globals.css`

**Date:** 2026-06-17 · **Plan:** `docs/05_Enterprise_RAG_UIUX_Audit_Remediation_Milestones.md` · **Gate:** UX2 (one button system, sectioned stylesheet, no Stitch wording)

## Provenance

Shipped code still *read* like a design-tool export: two button systems (`.button*` and `.stitch-button*`), the word *Stitch* in copy and a storage key, dead token aliases, `AR##` narration comments, and a flat 6,100-line stylesheet with no section map. Per the milestone, the working `stitch-*` **class identifiers are kept** (renaming them app-wide is out of scope); only the wording, the duplicate system, dead code, and the structure are addressed.

## Deliverables

- **One button system:** migrated **76** `.button button-primary|secondary` usages across 13 components onto `stitch-button stitch-button-primary|secondary stitch-button-small` (the `-small` size preserves admin density). Deleted the `.button`/`.button.button-primary`/`.button.button-secondary`/`.button:disabled` CSS. Updated `.cache-policy-list > button:not(.button)` → `:not(.stitch-button)` so the migrated buttons stay excluded.
- **Scrubbed Stitch wording (copy + strings, not class names):** "stitched thread" → "thread" (`chat-workspace`), "stitched threads" → "threads" (`history-page`), and the thread storage key `rag_console_threads_stitch_v1` → `rag_console_threads_v1` (`lib/workspace.ts`). `stitch-*` class identifiers intentionally remain.
- **Deleted dead code:** the unused `--color-*` / `--border-radius-*` alias block in `:root` (0 `var()` references) and its narration comment. `DESIGN.md §2.5` updated to state raw radius values so it no longer references the removed tokens.
- **Stripped `AR##` narration comments** (7) — 1 removed with the alias block, 6 rewritten as current-intent comments.
- **Re-architected `globals.css`:** added a TOC header listing 11 sections and inserted banner-delimited section headers (Tokens → Base/typography → Form controls → Data tables → Icons & avatars → Buttons → Public/marketing → Admin → Workspace → Tuning lab → Responsive). Rules were **not reordered** (the file's domains interleave; reordering 6k lines would be high-risk for no functional gain) — the TOC notes that responsive overrides are colocated and clustered at the tail.

## DoD check

- No "stitch"/"Stitch" in comments or user-facing strings under `web/app|components|lib` ✓ (only the `stitch-*` class identifiers remain, intentionally excluded).
- Exactly one button class system remains (`.stitch-button*`); `.button*` deleted; zero `button button-` usages ✓.
- `globals.css` opens with a section map; sections are banner-delimited; no `AR##` narration; dead alias block removed ✓.
- UX1 invariant still holds: zero `googleapis|gstatic|googleusercontent|material-symbols` under `web/app|components|lib` ✓.
- `tsc --noEmit` clean ✓; `next build` compiles (12/12 pages) ✓.

## Honest limits

- **Button visual delta:** migrated admin buttons now use the canonical gradient primary + `-small` sizing instead of the old flat `--primary-strong` fill. This is the intended consolidation (one system), so dense admin toolbars look slightly more prominent than before — acceptable and on-system, but a visual change, not pixel-identical.
- **Thread history reset:** renaming the storage key means threads saved under the old `..._stitch_v1` key in an existing browser won't carry over. These are browser-local dev threads in a starter; no migration shim was added because it would reintroduce the `stitch` string. New threads persist normally.
- **CSS sectioning is by banners, not reordering.** The file is navigable via the TOC + 11 banners, but a given domain's rules are not all physically contiguous; a future pass could split into imported partials if desired (the milestone allows either).

**Next:** UX3 — repair the Search surface (rebuild results on the canonical data-table/result-card pattern with labeled columns and a relevance indicator).
