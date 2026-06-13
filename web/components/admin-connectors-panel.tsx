"use client";

import { useEffect, useState } from "react";

import { browserFetch } from "@/lib/api-browser";

type DbConnector = {
  id: number;
  name: string;
  connector_type: string;
  table_name: string;
  id_column: string;
  updated_at_column: string;
  text_columns: string[];
  metadata_columns: string[];
  corpus_name?: string | null;
  acl_group_names: string[];
  status: string;
  last_cursor_updated_at?: string | null;
  last_cursor_id?: string | null;
  last_run_at?: string | null;
  last_error?: string | null;
  health_status: string;
  schedule_enabled: boolean;
  sync_interval_minutes: number;
  next_run_at?: string | null;
  retry_at?: string | null;
  last_success_at?: string | null;
  consecutive_failures: number;
};

type ConnectorRun = {
  id: number;
  trigger_type: string;
  status: string;
  attempt_number: number;
  rows_ingested: number;
  error_message?: string | null;
  retry_at?: string | null;
  started_at?: string | null;
};

type ConnectorRequest = {
  id: number;
  connector_type: string;
  requested_system: string;
  business_reason: string;
  requested_scope_json: Record<string, unknown>;
  status: string;
  review_reason?: string | null;
  requester_email?: string | null;
  created_at?: string | null;
};

type SchemaPreview = {
  connector_id: number;
  table_name: string;
  columns: { name: string; configured: boolean }[];
  configured_columns: string[];
};

type SyncPreview = {
  preview_row_count: number;
  row_limit: number;
  first_row?: Record<string, unknown> | null;
};

type SetupDraft = {
  name: string;
  connector_type: string;
  db_url: string;
  table_name: string;
  id_column: string;
  updated_at_column: string;
  text_columns: string;
  metadata_columns: string;
  corpus_name: string;
  acl_group_names: string;
};

function splitCsv(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function titleCase(value: string) {
  return value.split(/[_\s]+/).filter(Boolean).map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}

export function AdminConnectorsPanel() {
  const [connectors, setConnectors] = useState<DbConnector[]>([]);
  const [requests, setRequests] = useState<ConnectorRequest[]>([]);
  const [schemaById, setSchemaById] = useState<Record<number, SchemaPreview>>({});
  const [previewById, setPreviewById] = useState<Record<number, SyncPreview>>({});
  const [runsById, setRunsById] = useState<Record<number, ConnectorRun[]>>({});
  const [expandedRequestId, setExpandedRequestId] = useState<number | null>(null);
  const [reviewReasons, setReviewReasons] = useState<Record<number, string>>({});
  const [setupDrafts, setSetupDrafts] = useState<Record<number, SetupDraft>>({});
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [form, setForm] = useState({
    name: "",
    connector_type: "postgres",
    db_url: "",
    table_name: "",
    id_column: "id",
    updated_at_column: "updated_at",
    text_columns: "",
    metadata_columns: "customer_id,region",
    corpus_name: "db_rows",
    acl_group_names: "",
  });
  const activeRequests = requests.filter((request) => ["submitted", "under_review"].includes(request.status));

  async function refresh() {
    const [nextConnectors, nextRequests] = await Promise.all([
      browserFetch<DbConnector[]>("/connectors/db"),
      browserFetch<ConnectorRequest[]>("/connectors/requests"),
    ]);
    setConnectors(nextConnectors);
    setRequests(nextRequests);
  }

  useEffect(() => {
    refresh().catch((err) => setFeedback(err instanceof Error ? err.message : "Failed to load connectors."));
  }, []);

  async function saveConnector() {
    setBusy(true);
    setFeedback("");
    try {
      await browserFetch<DbConnector>("/connectors/db", {
        method: "POST",
        json: {
          ...form,
          text_columns: splitCsv(form.text_columns),
          metadata_columns: splitCsv(form.metadata_columns),
          acl_group_names: splitCsv(form.acl_group_names),
          corpus_name: form.corpus_name.trim() || null,
        },
      });
      setFeedback("Connector saved.");
      await refresh();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Failed to save connector.");
    } finally {
      setBusy(false);
    }
  }

  function scopeValue(request: ConnectorRequest, key: string) {
    const value = request.requested_scope_json?.[key];
    return typeof value === "string" && value.trim() ? value : "Not supplied";
  }

  function defaultSetupDraft(request: ConnectorRequest): SetupDraft {
    const tableOrScope = scopeValue(request, "table_or_scope");
    return {
      name: `${request.requested_system} request ${request.id}`,
      connector_type: request.requested_system === "MySQL" ? "mysql" : "postgres",
      db_url: scopeValue(request, "database_hint") === "Not supplied" ? "" : scopeValue(request, "database_hint"),
      table_name: tableOrScope === "Not supplied" ? "" : tableOrScope,
      id_column: "id",
      updated_at_column: "updated_at",
      text_columns: "",
      metadata_columns: "customer_id,region",
      corpus_name: "db_rows",
      acl_group_names: "",
    };
  }

  function setupDraftFor(request: ConnectorRequest) {
    return setupDrafts[request.id] || defaultSetupDraft(request);
  }

  function updateSetupDraft(request: ConnectorRequest, patch: Partial<SetupDraft>) {
    setSetupDrafts((current) => ({ ...current, [request.id]: { ...setupDraftFor(request), ...patch } }));
  }

  function openRequest(request: ConnectorRequest) {
    setExpandedRequestId(expandedRequestId === request.id ? null : request.id);
    setSetupDrafts((current) => current[request.id] ? current : { ...current, [request.id]: defaultSetupDraft(request) });
  }

  function useRequestAsDraft(request: ConnectorRequest) {
    const draft = setupDraftFor(request);
    setForm(draft);
    setExpandedRequestId(request.id);
    setFeedback("Request details copied into the DB connector draft. Add the connection URL and column mapping before saving.");
  }

  async function reviewRequest(requestId: number, status: "under_review" | "approved" | "denied") {
    setBusy(true);
    setFeedback("");
    try {
      await browserFetch<ConnectorRequest>(`/connectors/requests/${requestId}/review`, {
        method: "POST",
        json: { status, review_reason: reviewReasons[requestId] || (status === "approved" ? "Approved for connector configuration." : status === "denied" ? "Scope needs revision before ingestion." : "Under review.") },
      });
      await refresh();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Failed to review request.");
    } finally {
      setBusy(false);
    }
  }

  async function approveWithConnector(request: ConnectorRequest) {
    const draft = setupDraftFor(request);
    setBusy(true);
    setFeedback("");
    try {
      const connector = await browserFetch<DbConnector>("/connectors/db", {
        method: "POST",
        json: {
          ...draft,
          text_columns: splitCsv(draft.text_columns),
          metadata_columns: splitCsv(draft.metadata_columns),
          acl_group_names: splitCsv(draft.acl_group_names),
          corpus_name: draft.corpus_name.trim() || null,
        },
      });
      await browserFetch<ConnectorRequest>(`/connectors/requests/${request.id}/review`, {
        method: "POST",
        json: {
          status: "approved",
          review_reason: reviewReasons[request.id] || `Approved and configured as connector ${connector.name}.`,
        },
      });
      setExpandedRequestId(null);
      setFeedback(`Request approved and connector ${connector.name} saved.`);
      await refresh();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Failed to approve and configure connector.");
    } finally {
      setBusy(false);
    }
  }

  async function inspectSchema(connectorId: number) {
    const schema = await browserFetch<SchemaPreview>(`/connectors/db/${connectorId}/schema`);
    setSchemaById((current) => ({ ...current, [connectorId]: schema }));
  }

  async function previewSync(connectorId: number) {
    const preview = await browserFetch<SyncPreview>(`/connectors/db/${connectorId}/preview`, {
      method: "POST",
      json: { row_limit: 25 },
    });
    setPreviewById((current) => ({ ...current, [connectorId]: preview }));
  }

  async function syncRows(connectorId: number) {
    setBusy(true);
    setFeedback("");
    try {
      const result = await browserFetch<{ rows_ingested: number }>(`/connectors/db/${connectorId}/sync`, {
        method: "POST",
        json: { row_limit: 200 },
      });
      setFeedback(`Sync completed. ${result.rows_ingested} row source(s) ingested or refreshed.`);
      await refresh();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Sync failed.");
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  async function updateSchedule(connector: DbConnector) {
    setBusy(true);
    try {
      await browserFetch<DbConnector>(`/connectors/db/${connector.id}/schedule`, {
        method: "PATCH",
        json: {
          schedule_enabled: !connector.schedule_enabled,
          sync_interval_minutes: connector.sync_interval_minutes,
        },
      });
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  async function loadRuns(connectorId: number) {
    const payload = await browserFetch<{ runs: ConnectorRun[] }>(`/connectors/db/${connectorId}/runs`);
    setRunsById((current) => ({ ...current, [connectorId]: payload.runs }));
  }

  return (
    <div className="admin-page page-stack">
      <section className="admin-section-intro">
        <span>Connectors</span>
        <h1>Connector Governance</h1>
        <p>Review source requests, configure read-only DB connectors, inspect schema, preview rows, and sync approved database scope into governed retrieval.</p>
      </section>

      <section className="admin-card page-stack">
        <h2>Connector Requests</h2>
        {activeRequests.length === 0 ? (
          <p className="empty-copy">No active connector requests. Approved and denied requests remain available in Audit Log.</p>
        ) : (
          <div className="admin-list">
            {activeRequests.map((request) => (
              <article key={request.id} className="admin-list-item admin-list-item-stacked">
                <div className="admin-list-main">
                  <div>
                    <strong>{request.requested_system}</strong>
                    <p>{request.business_reason || "No business reason supplied."}</p>
                    <small>{request.requester_email || "Unknown requester"} · {titleCase(request.status)}</small>
                  </div>
                  <div className="toolbar-inline">
                    <button type="button" className="stitch-button stitch-button-secondary" disabled={busy} onClick={() => openRequest(request)}>View Request</button>
                    <button type="button" className="stitch-button stitch-button-secondary" disabled={busy || request.connector_type !== "database"} onClick={() => useRequestAsDraft(request)}>Use For DB Setup</button>
                    <button type="button" className="stitch-button stitch-button-secondary" disabled={busy} onClick={() => reviewRequest(request.id, "under_review")}>Mark Reviewing</button>
                    <button type="button" className="stitch-button stitch-button-primary" disabled={busy} onClick={() => reviewRequest(request.id, "approved")}>Approve</button>
                    <button type="button" className="stitch-button stitch-button-secondary" disabled={busy} onClick={() => reviewRequest(request.id, "denied")}>Deny</button>
                  </div>
                </div>
                {expandedRequestId === request.id ? (
                  <div className="request-detail-panel">
                    <div className="request-detail-table">
                      {[
                        ["Database or workspace", scopeValue(request, "database_hint")],
                        ["Table, folder, or mailbox", scopeValue(request, "table_or_scope")],
                        ["Drive file", scopeValue(request, "drive_file_name")],
                        ["Drive URL", scopeValue(request, "drive_file_url")],
                        ["Access note", scopeValue(request, "access_note")],
                      ].map(([label, value]) => (
                        <div key={label} className="request-detail-row">
                          <strong>{label}</strong>
                          <span>{value}</span>
                        </div>
                      ))}
                    </div>
                    {request.connector_type === "database" ? (
                      <div className="request-setup-box">
                        <h3>Approve With DB Connector Setup</h3>
                        <div className="admin-form-grid">
                          <label><span>Name</span><input value={setupDraftFor(request).name} onChange={(event) => updateSetupDraft(request, { name: event.target.value })} /></label>
                          <label><span>Type</span><select value={setupDraftFor(request).connector_type} onChange={(event) => updateSetupDraft(request, { connector_type: event.target.value })}><option value="postgres">Postgres</option><option value="mysql">MySQL</option></select></label>
                          <label><span>Connection URL</span><input value={setupDraftFor(request).db_url} onChange={(event) => updateSetupDraft(request, { db_url: event.target.value })} placeholder="postgresql://user:pass@host:5432/db" /></label>
                          <label><span>Table</span><input value={setupDraftFor(request).table_name} onChange={(event) => updateSetupDraft(request, { table_name: event.target.value })} placeholder="public.customer_cases" /></label>
                          <label><span>ID Column</span><input value={setupDraftFor(request).id_column} onChange={(event) => updateSetupDraft(request, { id_column: event.target.value })} /></label>
                          <label><span>Updated At Column</span><input value={setupDraftFor(request).updated_at_column} onChange={(event) => updateSetupDraft(request, { updated_at_column: event.target.value })} /></label>
                          <label><span>Text Columns</span><input value={setupDraftFor(request).text_columns} onChange={(event) => updateSetupDraft(request, { text_columns: event.target.value })} placeholder="title,body,notes" /></label>
                          <label><span>Metadata Filters</span><input value={setupDraftFor(request).metadata_columns} onChange={(event) => updateSetupDraft(request, { metadata_columns: event.target.value })} placeholder="customer_id,region" /></label>
                          <label><span>Corpus</span><input value={setupDraftFor(request).corpus_name} onChange={(event) => updateSetupDraft(request, { corpus_name: event.target.value })} /></label>
                          <label><span>ACL Groups</span><input value={setupDraftFor(request).acl_group_names} onChange={(event) => updateSetupDraft(request, { acl_group_names: event.target.value })} placeholder="support,finance" /></label>
                        </div>
                      </div>
                    ) : null}
                    <label><span>Review Note</span><textarea value={reviewReasons[request.id] || ""} onChange={(event) => setReviewReasons((current) => ({ ...current, [request.id]: event.target.value }))} rows={3} placeholder="Explain what was approved, denied, or still needed." /></label>
                    <div className="toolbar-inline">
                      {request.connector_type === "database" ? <button type="button" className="stitch-button stitch-button-primary" disabled={busy} onClick={() => approveWithConnector(request)}>Approve + Save Connector</button> : null}
                      <button type="button" className="stitch-button stitch-button-secondary" disabled={busy} onClick={() => reviewRequest(request.id, "denied")}>Deny Request</button>
                    </div>
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="admin-card page-stack">
        <h2>Admin DB Connector Setup</h2>
        <div className="admin-form-grid">
          <label><span>Name</span><input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} /></label>
          <label><span>Type</span><select value={form.connector_type} onChange={(event) => setForm((current) => ({ ...current, connector_type: event.target.value }))}><option value="postgres">Postgres</option><option value="mysql">MySQL</option></select></label>
          <label><span>Connection URL</span><input value={form.db_url} onChange={(event) => setForm((current) => ({ ...current, db_url: event.target.value }))} placeholder="postgresql://user:pass@host:5432/db" /></label>
          <label><span>Table</span><input value={form.table_name} onChange={(event) => setForm((current) => ({ ...current, table_name: event.target.value }))} placeholder="public.customer_cases" /></label>
          <label><span>ID Column</span><input value={form.id_column} onChange={(event) => setForm((current) => ({ ...current, id_column: event.target.value }))} /></label>
          <label><span>Updated At Column</span><input value={form.updated_at_column} onChange={(event) => setForm((current) => ({ ...current, updated_at_column: event.target.value }))} /></label>
          <label><span>Text Columns</span><input value={form.text_columns} onChange={(event) => setForm((current) => ({ ...current, text_columns: event.target.value }))} placeholder="title,body,notes" /></label>
          <label><span>Metadata Filters</span><input value={form.metadata_columns} onChange={(event) => setForm((current) => ({ ...current, metadata_columns: event.target.value }))} placeholder="customer_id,region" /></label>
          <label><span>Corpus</span><input value={form.corpus_name} onChange={(event) => setForm((current) => ({ ...current, corpus_name: event.target.value }))} /></label>
          <label><span>ACL Groups</span><input value={form.acl_group_names} onChange={(event) => setForm((current) => ({ ...current, acl_group_names: event.target.value }))} placeholder="support,finance" /></label>
        </div>
        <div className="toolbar-inline">
          <button type="button" className="stitch-button stitch-button-primary" disabled={busy} onClick={saveConnector}>Save Connector</button>
          {feedback ? <strong className="sources-upload-status">{feedback}</strong> : null}
        </div>
      </section>

      <section className="admin-card page-stack">
        <h2>Configured DB Connectors</h2>
        {connectors.length === 0 ? <p className="empty-copy">No DB connectors configured.</p> : null}
        <div className="sources-connected-list">
          {connectors.map((connector) => (
            <article key={connector.id} className="sources-connected-item">
              <div className="sources-connected-head">
                <span className="material-symbols-outlined">database</span>
                <div>
                  <strong>{connector.name}</strong>
                  <span>{connector.connector_type} · {connector.table_name} · {titleCase(connector.health_status)}</span>
                </div>
              </div>
              <p>Text: {connector.text_columns.join(", ")}. Filters: {connector.metadata_columns.join(", ") || "none"}.</p>
              <p>ACL: {connector.acl_group_names.join(", ") || "none"} · Cursor: {connector.last_cursor_updated_at || "not synced"} / {connector.last_cursor_id || "none"}</p>
              <p>Schedule: {connector.schedule_enabled ? `every ${connector.sync_interval_minutes} minute(s)` : "disabled"} · Next: {connector.next_run_at || "not scheduled"} · Failures: {connector.consecutive_failures}</p>
              {connector.retry_at ? <p className="sources-connected-note">Retry scheduled: {connector.retry_at}</p> : null}
              {connector.last_error ? <p className="sources-connected-note">{connector.last_error}</p> : null}
              <div className="toolbar-inline">
                <button type="button" className="stitch-button stitch-button-secondary" onClick={() => inspectSchema(connector.id)}>Inspect Schema</button>
                <button type="button" className="stitch-button stitch-button-secondary" onClick={() => previewSync(connector.id)}>Preview Sync</button>
                <button type="button" className="stitch-button stitch-button-primary" disabled={busy} onClick={() => syncRows(connector.id)}>Sync Rows</button>
                <button type="button" className="stitch-button stitch-button-secondary" disabled={busy} onClick={() => updateSchedule(connector)}>{connector.schedule_enabled ? "Disable Schedule" : "Enable Schedule"}</button>
                <button type="button" className="stitch-button stitch-button-secondary" onClick={() => loadRuns(connector.id)}>Run History</button>
              </div>
              {schemaById[connector.id] ? <p className="sources-connected-note">Columns: {schemaById[connector.id].columns.map((column) => `${column.name}${column.configured ? " *" : ""}`).join(", ")}</p> : null}
              {previewById[connector.id] ? <p className="sources-connected-note">Preview: {previewById[connector.id].preview_row_count} row(s) up to limit {previewById[connector.id].row_limit}.</p> : null}
              {runsById[connector.id]?.map((run) => (
                <p key={run.id} className="sources-connected-note">
                  {run.started_at || "Unknown time"} · {titleCase(run.trigger_type)} · {titleCase(run.status)} · attempt {run.attempt_number} · {run.rows_ingested} row(s){run.error_message ? ` · ${run.error_message}` : ""}
                </p>
              ))}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
