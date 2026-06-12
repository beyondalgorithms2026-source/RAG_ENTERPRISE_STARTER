# CLAUDE.md — Token-efficient rules + Enterprise RAG Project Rules

## 1. Token-saving rules (MUST follow every time)
- Be extremely concise. Never explain unless explicitly asked.
- Output ONLY the code changes (use unified diffs when editing files).
- Never repeat content from CLAUDE.md, CONTEXT.md or STATUS.md.
- After finishing a task or milestone: reply ONLY "Milestone complete. Ready for next prompt."
- Keep sessions short — after 10-15 turns suggest /clear or new session.

## 2. Project rules (from the official plan)
- This is the Enterprise RAG Starter built on top of the stable RAG_MM_MASTER_POC baseline.
- Core philosophy:
  • Retrieval + governance are the hard parts. LLM is last-mile generation.
  • Every change must preserve correctness, citation provenance, and security boundaries.
  • Retrieval changes must be measurable, reversible, and explainable.
- Never break baseline correctness or citations.
- Security trimming (ACL) must happen inside retrieval queries (SQL-level), never only in UI.
- Always update STATUS.md after every milestone.
- Add a short milestone/change note in `docs/milestones/` describing the change (create the folder if needed).

## 3. Two milestone tracks
- **M-series (M0–M33+):** Original project plan in `docs/02_Enterprise_RAG_Project_Plan_Milestones.md`. M0–M33 are complete or pending DB-backed reruns.
- **AR-series (AR0–AR14):** Audit remediation plan in `docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md`. Driven by the independent product audit (`docs/03_Enterprise_RAG_Independent_Product_Audit_2026_06_11.md`). AR numbering is deliberately disjoint from M-series.
- **Current active track:** AR-series. Follow the exact AR milestone order (AR0 → AR1 → …).
- AR milestones must not modify `docs/02_Enterprise_RAG_Project_Plan_Milestones.md`.
- No new product surface before AR1–AR3 close.
- Every AR milestone must leave the full suite green.

## 4. How to work with me
- I will work milestone-by-milestone.
- Read CONTEXT.md and STATUS.md at the start of every session.
- When I say "next milestone" or give a prompt, execute exactly that milestone's Goal + DoD from the relevant plan file.
- Always run re-run checks (baseline smoke tests + relevant eval pack) before declaring done.

## 5. Key audit findings to internalize
- 222 tests: 158 passed, 7 failures, 57 errors. 55/57 errors = hardcoded 384-dim vectors vs 768-dim DB column.
- Registry has wrong dimension metadata (bge-small listed as 768, actually 384).
- Active retrieval profile is an unpromoted sandbox draft (draft-645-retrieval).
- Migration ledger records MIG-P012; code plan defines through MIG-P020.
- Query transform is a 5-word synonym stub, not LLM-backed.
- Semantic cache is exact-match, not semantic. The threshold field is dead code.
- MMR is an explicit no-op placeholder.
- Eval packs total ~28 cases with keyword-only pass criteria.
- Sandbox compare monkeypatches module-level resolvers (concurrency-unsafe).
