# AGENTS.md — Token-efficient rules for Codex (Enterprise RAG Starter)

## 1. Token-saving rules (MUST follow every time)
- Be extremely concise. Never explain unless explicitly asked.
- Output ONLY the code changes (use unified diffs when editing files).
- Never repeat content from AGENTS.md, CONTEXT.md or STATUS.md.
- After finishing a task or milestone: reply ONLY "Milestone complete. Ready for next prompt."
- Keep sessions short — after 10-15 turns suggest /clear or new session.

## 2. Project rules (from the official plan)
- This is the Enterprise RAG Starter built on the existing stable PoC-grade baseline.
- Core philosophy:
  • Retrieval + governance are the hard parts. LLM is last-mile generation.
  • Every change must preserve correctness, citation provenance, and security boundaries.
  • Retrieval changes must be measurable, reversible, and explainable.
- Milestone tracks: **M-series** (`docs/02_…Milestones.md`), **AR-series** (`docs/04_…Audit_Remediation_Milestones.md`, complete through AR20), **UX-series** (`docs/05_Enterprise_RAG_UIUX_Audit_Remediation_Milestones.md`). UX and AR numbering are disjoint from M-series.
- **Current active track: UX-series.** Follow the exact UX order (UX0 → UX1 → …); UX0 (design language) gates everything after it. UX/AR plans must not modify `docs/02_…Milestones.md`.
- Never break baseline correctness or citations.
- Security trimming (ACL) must happen inside retrieval queries (SQL-level), never only in UI.
- Every milestone must leave the full suite green and `tsc --noEmit` clean.
- Always update STATUS.md after every milestone.
- Add a short milestone/change note in `docs/milestones/` describing the change (create the folder if needed).

## 2a. UI/UX execution rules (binding on ALL frontend work)
- **Design-language-first.** Before building or changing any UI, read `web/DESIGN.md` (and the `design-language` skill if present) and obey it. Do not add a token, component, or CSS class not defined there — reuse the canonical primitive. One button system only.
- **No external UI dependencies, ever.** No Google Fonts, no CDN icon font (Material Symbols), no third-party image hosts (`googleusercontent`, etc.). Fonts/icons are self-hosted/bundled; images are local or generated initials. The UI MUST render fully with the network blocked.
- **No "Stitch" wording in code.** Keep *Stitch*/"stitched" out of comments and user-facing copy; add no Stitch placeholder assets or origin-narrating comments. Existing `stitch-*` class identifiers may stay (renaming out of scope); don't add new ones. (`web/stitch-reference/` is reference-only, out of build.)
- **`globals.css` stays sectioned & clean:** table-of-contents header, banner-delimited sections, no orphaned selectors, no `AR##`/historical comments — current-intent comments only.

## 3. How to work with me
- I will work milestone-by-milestone.
- Read CONTEXT.md and STATUS.md at the start of every session.
- When I say "Start Milestone X" or give a prompt, execute exactly that milestone's Goal + DoD.
- Always run re-run checks (baseline smoke tests + relevant eval pack) before declaring done.
