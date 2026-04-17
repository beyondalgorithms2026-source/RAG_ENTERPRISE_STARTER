# M11.1 — Ingestion Queue Visibility, ETA, And Priority Governance

- Added a priority-aware ingestion queue worker so uploads and admin reindex requests enter the same governed waiting lane instead of bypassing one another.
- Exposed queue-aware user upload state with stage labels, ETA windows, confidence, queue-delay messaging, and a governed priority-request flow.
- Expanded the admin jobs console with queue health summary cards, richer filters, bounded queue controls, and priority request review plus reprioritization preview.
- Extended admin audit coverage for queue actions and added JSONL audit export for enterprise review workflows.
