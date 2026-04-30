## M10.1.3 — Admin Workspace Route Wiring And Operator Completeness

- Preserved `/console/admin` as a true `System Overview` page with recent traces, job health, report status, notifications, and quick links into routed operator flows.
- Added a dedicated `Overview` entry to the admin sidebar so the overview page remains intentional rather than acting like an accidental default.
- Replaced redirect-only admin sidebar destinations with real routed pages for corpora, jobs, profiles, evals, traces, policies, and audit log.
- Wired currently supported control-plane actions into the routed pages where backend APIs already exist:
  - corpus creation and inventory
  - ingestion/enrichment job visibility
  - profile activation
  - eval triggering and report review
  - trace inspection
- Kept policy and audit destinations truthful by rendering them as read-only or live-summary pages where deeper workflow editing/viewer support belongs to later milestones.
- Fixed admin-shell details that undermined operator trust, including the `New Corpus` CTA target and admin-nav active-state behavior.
