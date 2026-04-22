# Manual Test Steps — M12 To M16

## Common Setup
1. Start Docker Desktop.
2. Run `docker compose up -d` from the repo root.
3. Run backend migrations: `cd backend`, `. .venv/bin/activate`, `python -m app.db.migrate`.
4. Start backend: `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`.
5. Start frontend in another terminal: `cd web`, `pnpm dev --port 3001`.
6. Open `http://127.0.0.1:3001/login`.
7. Use `test-user@ragenterprise.local` / `password123` for user checks and `test-admin@ragenterprise.local` / `password123` for admin checks.

## M12 — DB And Structured Connectors
1. In Docker Postgres: `docker exec -it rag_enterprise_starter_db psql -U rag_enterprise_starter -d rag_enterprise_starter`.
2. Create test table:
   ```sql
   CREATE TABLE IF NOT EXISTS m12_browser_cases (
     id integer primary key,
     updated_at timestamptz not null default now(),
     title text not null,
     body text not null,
     customer_id text not null,
     region text not null
   );
   INSERT INTO m12_browser_cases VALUES
   (1, now(), 'Renewal blocker', 'Acme needs contract support for the EU rollout.', 'acme', 'eu')
   ON CONFLICT (id) DO UPDATE SET updated_at = now();
   ```
3. As user, open `/console/workspace/connectors`, submit a Postgres request with scope `m12_browser_cases`.
4. As admin, open `/console/admin/connectors`, view and approve the request.
5. In the DB setup form use URL `postgresql://rag_enterprise_starter:rag_enterprise_starter_dev_pass@localhost:55432/rag_enterprise_starter`, table `m12_browser_cases`, text columns `title,body`, metadata `customer_id,region`, corpus `db_rows`, ACL group `dev-users`.
6. Click Save Connector, Inspect Schema, Preview Sync, then Sync Rows.
7. As user, search for `Acme contract support EU rollout`.
8. Cleanup SQL:
   ```sql
   DELETE FROM db_connectors WHERE table_name = 'm12_browser_cases';
   DELETE FROM connector_requests WHERE requested_scope_json::text ILIKE '%m12_browser_cases%';
   DELETE FROM sources WHERE source_type = 'db_row' AND source_metadata_json ->> 'table' = 'm12_browser_cases';
   DROP TABLE IF EXISTS m12_browser_cases;
   ```

## M13 — Email And Attachments
1. Create or use a `.eml` file with a text attachment.
2. As user, open `/console/workspace/uploads`.
3. Upload the `.eml` file and wait until it reaches completed/indexed state.
4. Open `/console/workspace/sources` and confirm the email source plus supported attachment child source are visible.
5. Search for text that appears only in the attachment.
6. Optional request path: open `/console/workspace/connectors`, choose Email Archive, enter mailbox/folder scope, submit, then review it as admin under `/console/admin/connectors`.

## M14 — Tool Actions With Policy Gate
1. As admin, open `/console/admin/actions`.
2. Invoke `generate_report` with corpus `default`; it should complete and appear under Recent Tool Invocations.
3. Invoke `send_email`; it should create a pending approval instead of sending externally.
4. As user, call the same action only through API or UI if exposed; `send_email` should be denied for role policy, while `generate_report` is allowed.
5. Check `/console/admin/audit-log` for tool invocation records.

## M15 — Human Approval Workflow
1. As user, ask a sensitive question in chat, for example one containing `salary` or `API key`.
2. Confirm the answer content is not released and the chat says it is pending human approval.
3. As admin, open `/console/admin/actions`.
4. In Approval Queue, add a review reason and approve or deny the request.
5. Confirm the approval status updates and audit log records the decision.

## M16 — Fallback, Clarification, Feedback
1. As user, ask a question that has no indexed evidence.
2. Confirm chat returns `Not found in provided sources.` and shows a missing-source input.
3. Enter a source name/link hint and click Send.
4. Mark an answer helpful or not helpful.
5. As admin, open `/console/admin/actions`.
6. Confirm Top Failed Queries and feedback rows reflect missing-evidence or not-helpful submissions.
