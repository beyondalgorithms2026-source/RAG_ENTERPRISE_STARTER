## M4: Authorization And ACL Security Trimming

- Added authz data model tables for `auth_users`, `auth_groups`, `user_group_memberships`, and `document_acl`.
- Added `sources.sensitivity_label` with `public` / `internal` / `confidential` style enforcement support.
- Authenticated principals are synced into the authz tables from the request identity context.
- Retrieval SQL now applies ACL trimming inside vector search, keyword search, soft-keyword fallback, and chunk-id materialization.
- Sensitive documents without matching ACL membership are excluded before answer assembly, so forbidden chunks and citations do not leak.
- Search audit logs now include user groups, accessed document ids, corpus labels, and per-document sensitivity labels.
