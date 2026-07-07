# AGENTS.md — Codex rules (Enterprise RAG Starter)

**The canonical operating manual is [CLAUDE.md](CLAUDE.md). Read it first; this file is a
compressed mirror and defers to it.** For current project state, `STATUS.md` wins over
both.

## Session start
- Read `README.md`, `CONTEXT.md`, `STATUS.md`. `STATUS.md` = current posture when older
  docs (including audit findings quoted in CONTEXT.md) conflict — AR0–AR20 and UX0–UX12
  are complete; the 2026-06-11 audit defects are fixed.
- Active code: backend `backend/`, frontend `web/`. `frontend/` is legacy fallback —
  never build there.

## Hard rules
- Retrieval + governance are the hard parts; LLM is last-mile. Never break citation
  provenance or safe not-found behavior.
- ACL trimming happens inside SQL retrieval queries
  (`backend/app/auth/access_strategy.py` → `backend/app/db/repo_search.py`), never only
  in UI or Python post-filtering.
- Retrieval changes must be measurable (eval evidence), reversible (flag/profile),
  explainable (traced). Never hardcode embedding dimensions; dimension-changing swaps go
  through the AR7 lifecycle endpoints only.
- Single-worker runtime (AR8): no multi-worker assumptions, no module-global
  monkeypatching (use the `profile_overrides` ContextVar).
- UX/AR work must not modify `docs/02_Enterprise_RAG_Project_Plan_Milestones.md`.

## UI rules (all frontend work)
- Read `web/DESIGN.md` first and obey it. One button system (`.stitch-button*`), one
  form system (`components/ui/*`), one table (`.admin-data-table`). No new
  token/hex/class without updating `web/DESIGN.md`.
- No external UI dependencies, ever (no Google Fonts, CDN icon fonts, remote image
  hosts). The UI must render with the network blocked.
- No new Stitch wording or new `stitch-*` class names; `globals.css` stays sectioned,
  no orphaned selectors or `AR##` narration comments.

## Milestone loop
- Execute exactly the milestone's Goal + DoD from its plan file. Keep changes scoped.
- Gate before declaring done: `make test`; `cd web && npx tsc --noEmit && pnpm run build`
  if `web/` changed; `make scenario-validate` if auth/ACL/modules changed;
  `make repo-hygiene-check` always.
- Then update `STATUS.md` and add a note in `docs/milestones/`.
- Never commit `backend/.env`, `web/.env.local`, `web/tsconfig.tsbuildinfo`, or root
  eval outputs (reports go to `data/reports/`).

## Style
- Be extremely concise; output the code changes, not essays. Don't re-quote
  AGENTS.md/CLAUDE.md/CONTEXT.md/STATUS.md. After finishing a milestone reply only
  "Milestone complete. Ready for next prompt."

Full details — canonical paths, all commands, quality bars per deliverable type,
escalation rules, and repo-specific skill procedures — live in [CLAUDE.md](CLAUDE.md).
