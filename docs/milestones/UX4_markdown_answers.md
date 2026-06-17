# UX4 — Render Grounded Answers As Markdown

**Date:** 2026-06-17 · **Plan:** `docs/05_Enterprise_RAG_UIUX_Audit_Remediation_Milestones.md` · **Gate:** UX4 (structured answers survive) · **Audit:** C2

## Provenance

Answers were rendered by `message.content.split(/\n+/)` into `<p>` tags (`chat-workspace.tsx`), flattening lists, tables, headings, code, and bold — exactly the structure enterprise grounded answers rely on. Long answers became a wall of text.

## Deliverables

- **`components/markdown.tsx`** — `AnswerMarkdown`, a small wrapper over `react-markdown` (9.1.0) + `remark-gfm` (4.0.1) rendering GFM Markdown: headings, ordered/unordered lists, tables, fenced + inline code, emphasis, blockquotes, links (opened in a new tab with `rel="noreferrer"`). Both libraries are **bundled** — no runtime external/network dependency.
- **`chat-workspace.tsx`** — replaced the `split(/\n+/)` `<p>` block with `<AnswerMarkdown content={message.content} />`. Nothing else in the answer card changed (cache notice, no-context card, citation pills, evidence rail, feedback row all untouched).
- **`globals.css`** — `.chat-markdown` typography under the Workspace section: constrained **72ch** reading measure, scoped styles for headings (modest sizes, not the card's 2rem `h3`), lists, code (`var(--font-mono)` on `--surface-high`), `pre`, tables (canonical bordered/zebra-free look with `--surface-high` headers), blockquotes, links (`--primary`), and `hr`. Answer body stays visually distinct from citations/metadata.

## Sanitization

`react-markdown` does **not** render raw HTML by default (rehype-raw is intentionally not used), so there is no HTML-injection path. Verified by rendering test:
- `<script>alert('xss')</script>` → **not** present as a tag; appears as escaped text `&lt;script&gt;`.
- `<img src=x onerror=alert(1)>` → no real `<img` tag emitted; appears as escaped `&lt;img…`.
- Structure rendered correctly: `<h1>`, `<table>`+`<th>`, `<li>`, `<code>` all present.

## DoD check

- A structured answer (list + table + code + headings) renders correctly ✓ (render test).
- Sanitization verified — no raw-HTML injection ✓.
- `tsc --noEmit` clean ✓; `next build` compiles 12/12 ✓.
- No regression to citation pills / evidence rail ✓ (only the answer-text block was replaced).
- No-external-deps invariant holds: zero `googleapis|gstatic|googleusercontent|material-symbols` under `web/app|components|lib` ✓ (markdown libs are bundled JS, not CDN assets).

## Honest limits

- **Bundle size:** the chat route first-load JS grew (~115 kB → ~159 kB) from the Markdown libraries. Acceptable for the workspace surface; could be code-split/lazy-loaded later if needed.
- **Streaming:** answers still render once `message.content` is set (per the existing progress model); incremental Markdown-while-streaming is not introduced here.
- Two new npm dependencies (`react-markdown`, `remark-gfm`) were added to `package.json`/`pnpm-lock.yaml`.

**Next:** UX5 — inline citation anchoring (claim → source), tying inline `[n]` markers to the evidence rail + chunk-context.
