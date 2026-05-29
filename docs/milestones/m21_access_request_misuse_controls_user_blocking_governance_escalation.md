# M21 — Access Request Misuse Controls, User Blocking, And Governance Escalation

Implemented evidence-backed misuse controls for access request and query workflows.

- Added risk-signal storage for repeated similar requests and approver-swapping patterns.
- Added reversible governance restrictions for warning, extra review, access-request block, and severe query block paths.
- Access-request creation now records risk signals and enforces active access-request restrictions.
- Ask endpoints now enforce severe query-block restrictions before generation.
- Added admin governance APIs and tuning-lab visibility for risk signals and restrictions.
- Added smoke coverage for repeated-request detection, approver-swap detection, temporary block, and unblock audit path.

