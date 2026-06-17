# M16.1 — Access-Limited Retrieval, Routed Business Approval, And Time-Bound Access Grants

- Preserved SQL-level ACL trimming while adding a no-answer clarification state that can suggest access may be limiting a reliable answer.
- Added a dedicated access-request workflow with admin triage, routed business approval, and admin-executed time-bound direct source grants.
- Added workspace approvals/access and notification surfaces so requesters and business approvers can act without using database tooling or the generic admin approvals queue.
- Added notification records plus email-ready payload storage without introducing live outbound mail delivery in this milestone.
- Refined the requester flow so business reason, optional suggested approver, manager context, and routing hints can be captured without requiring source ids or exact file names.
- Refined the approval flow so approvers can map protected source ids during review, return misrouted requests to admin, and suggest alternate approvers when they are not the real owner.

## Manual test checklist

1. Start backend, web, and local Postgres, then sign in as:
   - `test-admin@ragenterprise.local` for admin
   - `Requester` dev preset for requester
   - `Approver` dev preset for business approver
2. Upload one protected test file and confirm it is indexed.
3. In `Admin -> Sources`, mark unrelated noisy public sources as `confidential` for the test so open documents do not satisfy the question first.
4. Add or confirm ACL on the protected file so the requester cannot retrieve it directly.
5. As requester, ask for the protected content and confirm:
   - answer is `Not found in provided sources.`
   - access-limited clarification is shown
   - `Request Access` form accepts business reason plus optional suggested approver / manager details
6. Submit the request with:
   - business reason
   - optional suggested approver email
   - optional manager context
7. In `Admin -> Access`, confirm the request shows requester context, suggested approver, and no source ids are required to route.
8. Route the request to an approver without source ids to test approver-side source mapping, or include source ids if admin already knows them.
9. As approver in `Workspace -> Approvals & Access`, verify all decision paths:
   - approve with selected source ids
   - deny
   - return `Not Real Owner`
   - return `Does Not Concern Me`
   - return `Suggest Alternate`
10. If approver suggests an alternate approver, confirm admin sees the returned request, the alternate suggestion, and must explicitly reroute it.
11. After approval, have admin click `Grant` and confirm requester can retrieve the protected source only after the temporary grant is active.
12. Expire or revoke the grant and confirm requester loses retrieval access again.
