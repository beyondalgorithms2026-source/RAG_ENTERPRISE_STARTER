# Operational Snapshot

Last reconciled: 13 September 2026.

## Current state

- AR0–AR20 audit remediation is complete.
- UX0–UX12 interface remediation is complete.
- The active implementation is `backend/` and `web/`.
- `frontend/` is retained legacy fallback code and is not the active interface.
- The deterministic public corpus contains 28 synthetic documents. Source 28 is the
  versioned Northwind Operations Manual v3.2 and is parsed and chunked through production
  ingestion code with source-hash validation.
- The approved public quality baseline remains the 25-case v1 run. The 90-case v2 suite
  (25 core plus 65 manual cases), performance thresholds, and expanded RT-01–RT-20
  governance set are implemented as candidates pending live calibration and approval.
- M20–M30 retain manual-verification closure notes; the full test suite now covers their
  implemented paths, but the historical per-milestone notes have not all been closed.

## Verified B004 posture

- This is a self-built proof of concept with a public Render Free portfolio demo over
  the 28-document synthetic corpus. It is not a production or client deployment and has
  no client environment, real users, or real workload evidence.
- Access control is enforced inside retrieval SQL.
- Citation enforcement prefers a safe not-found result to an unsupported answer.
- Retrieval augmentation is implemented but off by default; a backend operator enables
  it per corpus, and the agent cannot change that profile.
- The offline suite is designed to report database-bound coverage as explicit skips.
  Set `RAG_REQUIRE_DB=1` when a live migrated database is required.

The published B004 measurements and their limitations are maintained in the
[evaluation report](https://beyondalgorithms2026-source.github.io/RAG_ENTERPRISE_LANGGRAPH_APP/evaluation/).

## Known limitations

- Owner-approved numeric-claim repair is implemented as a disabled candidate;
  see `docs/NUMERIC_CLAIM_REPAIR.md`. Targeted STARTER checks correct the known
  temperature and financial comparisons; full-stack calibration and cost review
  remain prerequisites for activation. The approved v1 gate is unchanged.

- Single-process runtime; multi-worker safety has not been implemented.
- The public demo uses a versioned GPT-4o Mini snapshot. Provider transport contracts
  remain tested with simulated responses; the live D9 smoke checks are recorded in the
  B004 build log.
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
