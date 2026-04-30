# CLAUDE.md — Token-efficient rules + Enterprise RAG Project Rules

## 1. Token-saving rules (MUST follow every time)
- Be extremely concise. Never explain unless explicitly asked.
- Output ONLY the code changes (use unified diffs when editing files).
- Never repeat content from CLAUDE.md, CONTEXT.md or STATUS.md.
- If you need to run commands, git, tests, Python, etc., write a tiny one-file script and execute it with the built-in bash tool. NEVER preload or use any MCP tools/servers.
- After finishing a task or milestone: reply ONLY "Milestone complete. Ready for next prompt."
- Keep sessions short — after 10-15 turns suggest /clear or new session.

## 2. Project rules (from the official plan)
- This is the Enterprise RAG Starter built on top of the stable RAG_MM_MASTER_POC baseline.
- Core philosophy:
  • Retrieval + governance are the hard parts. LLM is last-mile generation.
  • Every change must preserve correctness, citation provenance, and security boundaries.
  • Retrieval changes must be measurable, reversible, and explainable.
- Follow the exact milestone order (M0 → M1 → …) and global Definition of Done.
- Never break baseline correctness or citations.
- Security trimming (ACL) must happen inside retrieval queries (SQL-level), never only in UI.
- Always update STATUS.md after every milestone.
- Add a short milestone/change note in `docs/milestones/` describing the change (create the folder if needed).

## 3. How to work with me
- I will work milestone-by-milestone.
- Read CONTEXT.md and STATUS.md at the start of every session.
- When I say "next milestone" or give a prompt, execute exactly that milestone's Goal + DoD.
- Always run re-run checks (baseline smoke tests + relevant eval pack) before declaring done.
