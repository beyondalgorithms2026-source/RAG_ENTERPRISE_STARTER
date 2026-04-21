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
  const [expandedRequestId, setExpandedRequestId] = useState<number | null>(null);
  const [reviewReasons, setReviewReasons] = useState<Record<number, string>>({});
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

  function useRequestAsDraft(request: ConnectorRequest) {
    setForm((current) => ({
      ...current,
      name: current.name || `${request.requested_system} ${request.id}`,
      connector_type: request.requested_system === "MySQL" ? "mysql" : "postgres",
      table_name: scopeValue(request, "table_or_scope") === "Not supplied" ? current.table_name : scopeValue(request, "table_or_scope"),
    }));
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

  return (
    <div className="admin-page page-stack">
      <section className="admin-section-intro">
        <span>Connectors</span>
        <h1>Connector Governance</h1>
        <p>Review source requests, configure read-only DB connectors, inspect schema, preview rows, and sync approved database scope into governed retrieval.</p>
      </section>

      <section className="admin-card page-stack">
        <h2>Connector Requests</h2>
        {requests.length === 0 ? (
          <p className="empty-copy">No connector requests yet.</p>
        ) : (
          <div className="admin-list">
            {requests.map((request) => (
              <article key={request.id} className="admin-list-item admin-list-item-stacked">
                <div className="admin-list-main">
                  <div>
                    <strong>{request.requested_system}</strong>
                    <p>{request.business_reason || "No business reason supplied."}</p>
                    <small>{request.requester_email || "Unknown requester"} · {titleCase(request.status)}</small>
                  </div>
                  <div className="toolbar-inline">
                    <button type="button" className="stitch-button stitch-button-secondary" disabled={busy} onClick={() => setExpandedRequestId(expandedRequestId === request.id ? null : request.id)}>View Request</button>
                    <button type="button" className="stitch-button stitch-button-secondary" disabled={busy || request.connector_type !== "database"} onClick={() => useRequestAsDraft(request)}>Use For DB Setup</button>
                    <button type="button" className="stitch-button stitch-button-secondary" disabled={busy} onClick={() => reviewRequest(request.id, "under_review")}>Mark Reviewing</button>
                    <button type="button" className="stitch-button stitch-button-primary" disabled={busy} onClick={() => reviewRequest(request.id, "approved")}>Approve</button>
                    <button type="button" className="stitch-button stitch-button-secondary" disabled={busy} onClick={() => reviewRequest(request.id, "denied")}>Deny</button>
                  </div>
                </div>
                {expandedRequestId === request.id ? (
                  <div className="request-detail-grid">
                    <p><strong>Database or workspace</strong><span>{scopeValue(request, "database_hint")}</span></p>
                    <p><strong>Table, folder, or mailbox</strong><span>{scopeValue(request, "table_or_scope")}</span></p>
                    <p><strong>Drive file</strong><span>{scopeValue(request, "drive_file_name")}</span></p>
                    <p><strong>Drive URL</strong><span>{scopeValue(request, "drive_file_url")}</span></p>
                    <p className="form-span-3"><strong>Access note</strong><span>{scopeValue(request, "access_note")}</span></p>
                    <label className="form-span-3"><span>Review Note</span><textarea value={reviewReasons[request.id] || ""} onChange={(event) => setReviewReasons((current) => ({ ...current, [request.id]: event.target.value }))} rows={3} placeholder="Explain what was approved, denied, or still needed." /></label>
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
                  <span>{connector.connector_type} · {connector.table_name} · {titleCase(connector.status)}</span>
                </div>
              </div>
              <p>Text: {connector.text_columns.join(", ")}. Filters: {connector.metadata_columns.join(", ") || "none"}.</p>
              <p>ACL: {connector.acl_group_names.join(", ") || "none"} · Cursor: {connector.last_cursor_updated_at || "not synced"} / {connector.last_cursor_id || "none"}</p>
              {connector.last_error ? <p className="sources-connected-note">{connector.last_error}</p> : null}
              <div className="toolbar-inline">
                <button type="button" className="stitch-button stitch-button-secondary" onClick={() => inspectSchema(connector.id)}>Inspect Schema</button>
                <button type="button" className="stitch-button stitch-button-secondary" onClick={() => previewSync(connector.id)}>Preview Sync</button>
                <button type="button" className="stitch-button stitch-button-primary" disabled={busy} onClick={() => syncRows(connector.id)}>Sync Rows</button>
              </div>
              {schemaById[connector.id] ? <p className="sources-connected-note">Columns: {schemaById[connector.id].columns.map((column) => `${column.name}${column.configured ? " *" : ""}`).join(", ")}</p> : null}
              {previewById[connector.id] ? <p className="sources-connected-note">Preview: {previewById[connector.id].preview_row_count} row(s) up to limit {previewById[connector.id].row_limit}.</p> : null}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
