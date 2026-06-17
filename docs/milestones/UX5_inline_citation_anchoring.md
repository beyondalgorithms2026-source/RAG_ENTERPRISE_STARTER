# UX5 — Inline Citation Anchoring (claim → source)

**Date:** 2026-06-17 · **Plan:** `docs/05_Enterprise_RAG_UIUX_Audit_Remediation_Milestones.md` · **Gate:** UX5 (claims map to sources) · **Audit:** C3

## Provenance

Citations appeared only as filename pills below the answer and as cards in the evidence rail — no inline markers tying specific sentences to specific sources. Provenance, the product's core value, was asserted rather than demonstrated at claim level.

## Deliverables

- **Inline `[n]` chips** (`components/markdown.tsx`): before rendering, in-range `[n]` markers (where `n` is a 1-based index into `message.citations`) are rewritten to `[n](#rag-cite-n)` links; the Markdown `a` renderer detects the `#rag-cite-` href and renders a **superscript `<button>` chip** instead. Out-of-range numbers (e.g. `[9]` with 2 citations), `[n](…)` existing links, and `[^n]` footnotes are left untouched (verified by render test). `#rag-cite-` hash hrefs survive react-markdown's default `urlTransform`.
- **Rail integration:** chip **click** calls the new shared `selectCitation(evidenceId, citationId)` helper in `chat-workspace.tsx` — sets the selected citation (the existing effect loads chunk context), expands the section, and scrolls it into view. Chip **hover/focus** sets `hoveredCitationId`, highlighting the matching evidence card (`.chat-evidence-card.is-hovered`).
- **Accessibility:** each chip is a real `<button>` (keyboard-focusable, Enter/Space-activatable) with an accessible name `aria-label="Citation N: <file>"`, a `title`, and a `:focus-visible` ring. Focus also triggers the hover highlight.
- **Refactor/cleanup:** the citation **pill** onClick and the **evidence-card** onClick were migrated onto the same `selectCitation` helper (removing duplicated select/expand/scroll logic); pills also drive the hover highlight now.
- **CSS:** `.chat-cite-sup`/`.chat-cite-chip` (superscript chip, primary-soft → primary on hover, focus ring) under the Markdown block; `.chat-evidence-card.is-hovered` near the evidence-card styles. No new tokens.

## DoD check

- Inline markers render and are keyboard-focusable with accessible names ✓.
- Markers drive rail selection (highlight + scroll + chunk-context load) ✓ (reuse the proven `selectCitation` path).
- `tsc --noEmit` clean ✓; `next build` compiles 12/12 ✓.
- No-external-deps invariant holds ✓; sanitization unchanged (still no raw-HTML path).

## Honest limits

- **Depends on the model numbering its claims.** Chips appear only when the answer text actually contains `[n]` markers that map to citations. If the model doesn't emit numbered markers, no chips render — the citation pills and evidence rail still work unchanged (graceful degradation). Making the model emit consistent `[n]` markers is a generation/prompt concern, out of UX scope.
- **Simple marker detection.** `[n]` is matched textually; a literal `[1]` inside a fenced code block would also be rewritten. This is rare in grounded answers and low-impact (it becomes a chip); a code-aware pass could be added later if needed.
- Hovering a chip whose evidence section is collapsed shows no card highlight (the card isn't rendered); clicking expands and scrolls to it.

**Next:** UX6 — Search facets, sort, and a labeled relevance model.
