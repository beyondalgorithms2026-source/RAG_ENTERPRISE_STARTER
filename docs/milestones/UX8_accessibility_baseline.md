# UX8 — Accessibility Baseline

**Date:** 2026-06-17 · **Plan:** `docs/05_Enterprise_RAG_UIUX_Audit_Remediation_Milestones.md` · **Gate:** UX8 · **Audit:** C4, mn6

## Deliverables

- **Global visible focus ring:** a `:focus-visible` baseline in `globals.css` (Base section) outlines every interactive element (`a`, `button`, `[role="tab"]`, `[tabindex]`, inputs) in `--primary`; components may still add their own ring. Focus-visible rules went 5 → 11.
- **Live regions:** `aria-live="polite"` on the chat answer `<article>` so the completed answer is announced; `role="status"` on the streaming progress card with the changing **% marked `aria-hidden`** (announce the coarse stage label, not every percent tick). `role="alert"` on the chat + search error banners; `role="status"` on the search loading state.
- **Accessible names:** the one genuinely icon-only unnamed control — the chat **New thread** button — now has `aria-label`/`title`. (Other icon buttons already carry visible text or were named in UX7's coming-soon pass.)
- **Focus-trap cleanup:** the fake/readOnly command + workspace search inputs are out of the tab order (`tabIndex={-1}`, set in UX7) so keyboard users don't land on inert fields.
- **Tablists/dialogs:** the admin data/JSON viewer already uses `role="tablist"/"tab"/"tabpanel"` with `aria-selected`; there are no modal dialogs in the current chrome.

## Contrast audit (UX0 palette)

Programmatic WCAG check of the key foreground/background pairs — **all pass AA** (≥4.5 for normal text):

| Pair | Ratio |
|---|---|
| muted on surface | 5.81 |
| muted on surface-low | 5.52 |
| muted on surface-panel | 6.09 |
| muted on surface-high | 4.96 |
| primary on white | 10.05 · primary-strong 6.96 |
| success-ink on success-bg | 5.73 |
| danger on danger-soft | 5.00 |
| warning ink on warning bg | 5.61 |
| ink on surface | 16.30 · answer body on white 9.38 |

The DESIGN.md §2.3 "verify muted-on-tan contrast in UX8" item is resolved: **no token change needed.**

## DoD check

- Global visible focus ring present ✓; keyboard focus is visible across chrome (verified the rule applies to all interactive selectors; inert fake inputs removed from tab order).
- `aria-live` on progress card + completed answer ✓; status/alert roles on loading/error ✓; accessible names on icon-only buttons ✓.
- Contrast audit run; all key pairs AA ✓.
- `tsc --noEmit` clean ✓; `next build` 12/12 ✓; no-external-deps invariant holds ✓.

## Honest limits

- **Automated axe was not executed headlessly** in this environment (no running app + browser harness available). Instead the audit covered axe's main categories statically: accessible names, roles/landmarks, live regions, focus visibility, and **programmatic contrast** (above). A live axe pass + full keyboard walkthrough should be run in a browser before release.
- Live-region announcements are intentionally coarse (stage label, not every percent) to avoid screen-reader spam; exact verbosity should be validated with a real screen reader.

**Next:** UX9 — responsiveness pass (intermediate breakpoints; evidence rail → drawer; metadata bar wrap).
