# Source Control Workflow

This runbook defines the canonical git workflow for this repo after M31.

## Canonical branches

- Treat the intended long-lived dev branch as the milestone continuation branch.
- Do not use ad hoc comparison branches as the default PR base.
- Do not compare milestone branches to `master` unless the goal is a true integration diff to `master`.

## Branch naming

- Milestone continuation branches should use a stable product branch name.
- Short-lived task branches should use a scoped prefix such as `codex/`, `fix/`, or `docs/` followed by a concise slug.
- Avoid creating multiple near-duplicate long-lived branches that differ only by casing or punctuation.

## Tag naming

- Milestone completion tags should use stable lowercase milestone-oriented names such as `m31-repo-hygiene-complete`.
- Date-prefixed tags are acceptable only for one-off snapshots that are not the canonical milestone marker.
- Do not create multiple tags for the same milestone outcome unless one is explicitly archival and documented.

## Commit scope and message style

- Keep one commit focused on one milestone or one coherent fix set.
- Use concise imperative messages that describe the repo-visible change.
- Do not mix generated local artifacts into functional commits.

## PR base expectations

- Open PRs against the intended integration branch.
- If a PR is opened against `master`, expect the comparison to include the full cumulative branch delta.
- Confirm the PR base before interpreting large insert/delete counts.

## Generated artifacts

- Commit sample and example artifacts:
  - `backend/.env.example`
  - `web/.env.example`
  - curated benchmark or audit proof kept intentionally
- Do not commit machine-local or transient files:
  - `backend/.env`
  - `web/.env.local`
  - `web/tsconfig.tsbuildinfo`
  - local build caches
  - disposable eval outputs

## Report retention

- Default local eval outputs belong in `data/reports/` and are ignored by git.
- If a report must be kept for milestone proof or audit comparison, move it into a documented committed location under `docs/` or test fixtures with a stable name and context.
- Do not leave ad hoc generated reports at repo root.

## Canonical paths

- Active backend: `backend/`
- Active frontend: `web/`
- Legacy fallback UI: `frontend/`
- Reference-only imported docs: `docs/_master_docs/`, `docs/README_from_master.md`
- Local generated reports: `data/reports/`
