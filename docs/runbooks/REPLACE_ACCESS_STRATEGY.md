# Replace Access Strategy

Access strategy changes must stay inside SQL-level source access predicates.

1. Choose `ACCESS_STRATEGY` from the supported set.
2. For corpus-level access, populate `corpus_access_grants`.
3. For document ACL access, populate `document_acl` and user group memberships.
4. Do not filter protected results only in the UI.
5. Re-run M28 tests plus ACL leak tests.

If promoting from corpus-level access to document ACL, migrate corpus grants into group memberships and document ACL assignments, then switch `ACCESS_STRATEGY`.
