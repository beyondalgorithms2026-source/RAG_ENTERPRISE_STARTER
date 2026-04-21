# M12 Cloud DB And Structured Source Connectors

- Added persisted Postgres/MySQL connector configuration with incremental sync cursors.
- Serialized database rows into `db_row` sources, source parts, chunks, corpus metadata, row provenance, and structured filter locator fields.
- Preserved SQL-level ACL trimming by assigning connector row sources to configured ACL groups during ingestion.
- Upgraded the user connector workspace with scoped request submission, connector status, review status, and connected row-source visibility.
- Extended DB verification and smoke coverage for connector schema, row serialization, metadata filters, and ACL-scoped DB row retrieval.
- Moved connector governance into a dedicated admin connector page with scoped request detail, review notes, approve/deny decisions, DB connector setup, schema inspection, sync preview, and approved sync controls.
- Kept direct connector credentials and sync controls in the admin console.
