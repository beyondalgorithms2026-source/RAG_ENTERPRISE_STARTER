# M13 — Enterprise Email And Attachment Ingestion

- Uploaded `.eml` support remains active and now routes upload metadata to the `email_casework` corpus policy.
- Added a mailbox/archive connector abstraction in `backend/app/connectors/email.py` so enterprise email records can normalize into the same parsed header/body model as uploaded email.
- Email attachments now carry payload bytes through parsing and supported attachment types can become searchable child sources.
- Attachment relationships are persisted in `attachments` with parent and child source IDs, preserving source provenance for retrieval and review.
- User connector requests now include Email Archive scope fields and Google Drive file request details; admins can inspect scope, write review notes, approve/deny, and use database requests as setup drafts.
