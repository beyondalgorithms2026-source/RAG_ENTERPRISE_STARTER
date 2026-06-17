# M17.2 Manual Test Notes

1. Start the stack:
   - `docker compose up -d`
   - `make dev-web`
2. Import the enterprise ACL seed pack:
   - `make seed-enterprise-acl`
   - or `POST /admin/access/seed-import` from the admin Access page
3. Use these seeded identities from the login page:
   - `test-user@ragenterprise.local`
   - `test-admin@ragenterprise.local`
   - `requester@ragenterprise.local`
   - `approver@ragenterprise.local`
   - `manager@ragenterprise.local`
   - `restricted@ragenterprise.local`
   - `observer@ragenterprise.local`
   - `ceo@ragenterprise.local`
   - `cfo@ragenterprise.local`
4. In `Admin -> Access`, verify:
   - seed pack summary is populated
   - user memberships can be edited
   - source ACL groups can be edited
   - source contacts can be edited
   - source and user access explanations render
5. Retrieval checks:
   - `publichandbooktoken` should be visible to standard users
   - `legalfalcontoken` should be visible to legal/contract reviewer users
   - `q3budgettoken` should be visible to finance and executive access users
   - `compcaltoken` should stay protected and continue to exercise sensitive-answer behavior
6. Access workflow checks:
   - route a request against the seeded protected sources
   - verify approver, manager, and ACL manager context is visible in the admin workflow
