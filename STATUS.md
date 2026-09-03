# Operational Snapshot

Last reconciled: 3 September 2026.

## Current state

- AR0–AR20 audit remediation is complete.
- UX0–UX12 interface remediation is complete.
- The active implementation is `backend/` and `web/`.
- `frontend/` is retained legacy fallback code and is not the active interface.
- M20–M30 retain manual-verification closure notes; the full test suite now covers their
  implemented paths, but the historical per-milestone notes have not all been closed.

## Verified B004 posture

- This is a self-built proof of concept, not a deployed service. It has no client
  environment, users, or real workload evidence.
- Access control is enforced inside retrieval SQL.
- Citation enforcement prefers a safe not-found result to an unsupported answer.
- Retrieval augmentation is implemented but off by default; a backend operator enables
  it per corpus, and the agent cannot change that profile.
- The offline suite is designed to report database-bound coverage as explicit skips.
  Set `RAG_REQUIRE_DB=1` when a live migrated database is required.

The published B004 measurements and their limitations are maintained in the
[evaluation report](https://beyondalgorithms2026-source.github.io/RAG_ENTERPRISE_LANGGRAPH_APP/evaluation/).

## Known limitations

- Single-process runtime; multi-worker safety has not been implemented.
- Hosted LLM provider contracts are transport-tested without live cloud credentials in
  this environment.
- Connector scheduling uses an in-process poller; live mailbox/archive synchronization
  is not implemented.
- Provider API keys are write-only through the API and excluded from response/audit
  payloads, but storage-at-rest protection remains a deployment responsibility.
- Dimension-changing embedding swaps must use the managed lifecycle; direct activation
  is blocked.

## Canonical paths

- Public entry point: `README.md`
- Local setup: `docs/01_quickstart.md`
- Repository map: `docs/04_repo_navigation_blueprint.md`
- Safe extension guide: `docs/runbooks/SAFE_EXTENSION_BLUEPRINT.md`
- Current contributor rules: `CLAUDE.md` and `AGENTS.md`

## Historical Detail

Milestone chronology is archived in
`docs/project_state/milestone_history_archive.md`; implementation evidence remains under
`docs/milestones/`. Dated audits and `docs/_master_docs/` are historical references, not
the current-state record.
