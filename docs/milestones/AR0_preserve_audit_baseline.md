# AR0 — Preserve Audit Baseline And Link It Into Repo Navigation

**Date:** 2026-06-12 · **Plan:** `docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md` · **Gate:** AR0 (audit is canonical)

## What changed

- `docs/03_Enterprise_RAG_Independent_Product_Audit_2026_06_11.md` and `docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md` were committed unmodified and tagged `audit-baseline-2026-06-11`; verified byte-stable against the tag at AR0 closure.
- `README.md`: audit baseline and remediation plan added to the Start Here reader path (labeled explicitly as an audit baseline, not a marketing document); stale "Current milestone: M32" status replaced with the M33/AR-track state; verification-debt line now states the audit's measured suite result (222 tests: 158 passed, 7 failures, 57 errors) instead of the milder "DB-backed reruns from M17.b.3 onward" phrasing; reviewer/auditor persona path now starts at the audit.
- `STATUS.md`: rewritten around the two-track state — audit summary section with measured suite result, AR0–AR14 progress table, known dev-DB incoherences (wrong registry dimension metadata, `draft-645-retrieval` active as live, migration ledger P012 vs P020), and the audit/remediation docs appended to the canonical reader path. "Current Verification Debt" now leads with the suite being red, replacing the understated M20+ phrasing the audit flagged.
- `CONTEXT.md` / `CLAUDE.md`: AR-series declared the active work track; audit-identified gaps mapped to AR milestones.
- No edits to `docs/02_Enterprise_RAG_Project_Plan_Milestones.md`.

## Why (audit finding)

Audit §1 and AR0's "what was not working": the repo had only self-reported status with no independent baseline, and STATUS.md understated verification debt relative to the measured suite run. Without a preserved, linked baseline, later milestones would drift toward optimistic re-description instead of remediating measured findings.

## DoD check

- Audit file present and byte-stable after review: **yes** (`git diff audit-baseline-2026-06-11` empty for both docs).
- README/STATUS link to both new docs: **yes**.
- No edits to `docs/02_Enterprise_RAG_Project_Plan_Milestones.md`: **yes**.

## Re-run checks

- M31/M32 doc hygiene suites (`reader-clarity-check`) — result recorded at closure in STATUS.md.
- Full-suite status remains red as measured by the audit (222: 158/7/57); restoring it is gate AR1, not AR0.

**Next:** AR1 — Restore Green, Environment-Independent Regression Suite.
