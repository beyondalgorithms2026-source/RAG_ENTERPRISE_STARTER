# M13 — Enterprise Email And Attachment Ingestion

- Uploaded `.eml` support remains active and now routes upload metadata to the `email_casework` corpus policy.
- Added a normalization abstraction in `backend/app/connectors/email.py`; it is not a live mailbox connector. Operational ingestion remains uploaded `.eml` files.
- Email attachments now carry payload bytes through parsing and supported attachment types can become searchable child sources.
- Attachment relationships are persisted in `attachments` with parent and child source IDs, preserving source provenance for retrieval and review.
- Parsed email and attachment text/metadata is sanitized before persistence to remove Postgres-incompatible NUL characters from real-world PDF/email extraction output.
- User connector requests now include Email Archive scope fields and Google Drive file request details; admins can inspect scope, write review notes, approve/deny, and use database requests as setup drafts.
- Live IMAP, Microsoft Graph, Gmail, PST, and archive synchronization remain unimplemented and out of scope through AR13.
