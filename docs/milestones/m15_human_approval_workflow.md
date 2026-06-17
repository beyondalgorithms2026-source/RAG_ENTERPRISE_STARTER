# M15 — Human Approval Workflow For Sensitive Outputs And Actions

- Added rules-based sensitive detection for compensation, personal identifiers, and secrets.
- Sensitive answers are held in `approval_requests` and replaced with a pending-approval user response.
- Tool actions that require human review create approval requests before external dispatch.
- Admins can approve or deny requests with a review reason from the Actions console.
- Approval decisions are audit-recorded and remain visible to requesters through the approval API.
