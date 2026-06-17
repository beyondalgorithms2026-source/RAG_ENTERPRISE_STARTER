# UX10 — Finish Pass

**Date:** 2026-06-17 · **Plan:** `docs/05_Enterprise_RAG_UIUX_Audit_Remediation_Milestones.md` · **Gate:** UX10 · **Audit:** mn1–mn5, polish

Final milestone of the UX series.

## Deliverables

- **Placeholders → em dash:** removed prose placeholders. `chat-workspace` latency "Captured" → `—`; `admin-dashboard`, `admin-panels`, `sources-page` `formatMetric`/`formatTimestamp` "Unavailable" → `—`.
- **Removed internal jargon:** the chat metadata bar's `Path:` (operator term) is now **`Route:`** with a `title="How this answer was retrieved."` tooltip, and the value is humanized (snake_case → spaces). `—` when absent.
- **Glossary:** `web/DESIGN.md §5b` standardizes product vocabulary (Ask, Search, History, Thread, Source, Citation, Evidence, Corpus, Freshness, Route, Relevance, Coming soon, em-dash placeholders).
- **Access-request form → modal:** the long inline form in the no-context card is now opened by a **"Request access to a source"** button into a focusable **`role="dialog"` modal** (`.chat-modal-backdrop`/`.chat-modal`) with a header + close button, **Escape-to-close** (effect), and backdrop-click close. The form fields/handlers are unchanged — only relocated — so the answer flow is no longer dominated by a 6-field form.
- **Explicit CSS spinner:** `@keyframes app-spin` + `.app-icon.spin`, applied to the search loading icon (no longer relies on a glyph's own motion).
- **Consistent states:** added a hover state to evidence cards (and the modal close button); existing selected/active/hover states retained.
- **Composer shortcut:** **⌘/Ctrl+Enter** submits the chat composer (guarded by `isStreaming`); the textarea gained an accessible label.

## DoD check

- No prose placeholders or raw internal terms in primary user chrome ✓ (grep: no `Unavailable`/`Captured`/`>Path:`).
- Consistent states across canonical components ✓; explicit spinner ✓; composer shortcut ✓; access-request modal ✓; glossary added ✓.
- `tsc --noEmit` clean ✓; `next build` 12/12 ✓; no-external-deps invariant holds ✓.

## Honest limits

- The access-request modal implements Escape/backdrop/close and a labelled dialog, but **does not trap focus** inside the dialog or restore focus to the trigger on close — a full focus-trap is a small follow-up. Submitting leaves the modal open showing the result notice (user closes it).
- "Consistent hover/active/selected states" was a targeted pass (evidence cards, modal close, plus the rings from UX8), not an exhaustive audit of every interactive element.

## UX series summary (UX0–UX10, all 2026-06-17)

Design language (UX0) → no external deps / network-blocked UI (UX1) → de-Stitch wording + sectioned CSS (UX2) → Search surface repair (UX3) → Markdown answers (UX4) → inline citation anchoring (UX5) → Search facets/sort/relevance (UX6) → IA & coming-soon control hygiene (UX7) → accessibility baseline (UX8) → responsiveness (UX9) → finish pass (UX10). Tags: `ux-foundation-2026-06-17` (UX0–UX2), then `ux3…`–`ux10…`.

**Next:** UX series complete. Remaining follow-ups are the documented honest limits (live axe + keyboard pass, multi-width browser verification, modal focus-trap, server-side faceted search, model-emitted citation markers).
