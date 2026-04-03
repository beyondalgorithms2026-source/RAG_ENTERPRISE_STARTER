"use client";

import { useEffect, useState } from "react";

import { browserApiUrl, browserFetch } from "@/lib/api-browser";

type SourceItem = {
  id: number;
  file_name: string;
  source_type: string;
  ingestion_status: string;
  enrichment_status: string;
  source_metadata_json: Record<string, unknown>;
};

type UploadResult = {
  source_id: number;
  job_id: number;
  file_name: string;
};

type ConnectorRequest = {
  id: string;
  system: string;
  createdAt: string;
};

const CONNECTOR_STORAGE = "rag_console_connector_requests_stitch_v1";

function iconForSource(source: SourceItem) {
  const type = source.source_type.toLowerCase();
  if (type.includes("pdf")) {
    return "picture_as_pdf";
  }
  if (type.includes("doc") || type.includes("text") || type.includes("md")) {
    return "description";
  }
  if (type.includes("slack")) {
    return "forum";
  }
  return "database";
}

export function SourcesPage() {
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [connectorRequests, setConnectorRequests] = useState<ConnectorRequest[]>([]);
  const [uploadStatus, setUploadStatus] = useState("");
  const [uploading, setUploading] = useState(false);
  const [filter, setFilter] = useState("All Sources");
  const [error, setError] = useState("");

  async function refresh() {
    try {
      const payload = await browserFetch<SourceItem[]>("/corpus");
      setSources(payload);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sources.");
    }
  }

  useEffect(() => {
    refresh();
    try {
      const raw = localStorage.getItem(CONNECTOR_STORAGE);
      const parsed = raw ? (JSON.parse(raw) as ConnectorRequest[]) : [];
      setConnectorRequests(Array.isArray(parsed) ? parsed : []);
    } catch {
      setConnectorRequests([]);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(CONNECTOR_STORAGE, JSON.stringify(connectorRequests));
  }, [connectorRequests]);

  async function onFileSelected(file: File | null) {
    if (!file) {
      return;
    }
    setUploading(true);
    setUploadStatus("Uploading document...");
    setError("");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const response = await fetch(browserApiUrl("/upload"), {
        method: "POST",
        body: formData,
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error((await response.text()) || "Upload failed.");
      }
      const payload = (await response.json()) as UploadResult;
      setUploadStatus(`${payload.file_name} queued as source #${payload.source_id}.`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
      setUploadStatus("");
    } finally {
      setUploading(false);
    }
  }

  function addConnectorRequest(system: string) {
    setConnectorRequests((prev) => [
      { id: Math.random().toString(36).slice(2, 10), system, createdAt: new Date().toISOString() },
      ...prev,
    ]);
  }

  const visibleSources = sources.filter((source) => {
    if (filter === "Indexed") {
      return source.ingestion_status.toLowerCase() === "indexed";
    }
    if (filter === "Syncing") {
      return source.ingestion_status.toLowerCase() !== "indexed";
    }
    return true;
  });

  const connectedData = visibleSources.filter((source) => {
    const metadata = source.source_metadata_json || {};
    const lowerType = source.source_type.toLowerCase();
    return (
      lowerType.includes("database") ||
      lowerType.includes("postgres") ||
      lowerType.includes("sql") ||
      typeof metadata.connector === "string" ||
      typeof metadata.connection_name === "string" ||
      typeof metadata.database === "string"
    );
  });

  return (
    <div className="sources-page">
      <div className="sources-header">
        <div>
          <h1>My Sources</h1>
          <p>Manage and synchronize your data repositories for retrieval.</p>
        </div>
        <button type="button" className="stitch-button stitch-button-primary" onClick={() => addConnectorRequest("Requested Connector")}>
          <span className="material-symbols-outlined">add_link</span>
          Request New Connector
        </button>
      </div>

      <div className="sources-top-grid">
        <label className={`sources-upload-card ${uploading ? "is-uploading" : ""}`}>
          <input type="file" hidden onChange={(event) => onFileSelected(event.target.files?.[0] || null)} />
          <div className="sources-upload-icon">
            <span className="material-symbols-outlined">upload_file</span>
          </div>
          <h3>Upload Documents</h3>
          <p>Drag and drop PDFs, CSVs, or MD files here to index them directly.</p>
          <div className="sources-upload-chips">
            <span>Max 50 MB</span>
            <span>Auto-OCR</span>
          </div>
          {uploadStatus ? <strong className="sources-upload-status">{uploadStatus}</strong> : null}
          {error ? <strong className="sources-upload-error">{error}</strong> : null}
        </label>

        <aside className="sources-connector-card">
          <h4>Connectors</h4>
          <div className="sources-connector-grid">
            {[
              ["database", "Postgres"],
              ["add_to_drive", "Google Drive"],
              ["library_books", "Confluence"],
            ].map(([icon, label]) => (
              <button key={label} type="button" className="sources-connector-button" onClick={() => addConnectorRequest(label)}>
                <span className="material-symbols-outlined">{icon}</span>
                <span>{label}</span>
                <small>Request pending</small>
              </button>
            ))}
          </div>
          {connectorRequests[0] ? (
            <div className="sources-connector-note">
              Latest request: <strong>{connectorRequests[0].system}</strong>
            </div>
          ) : null}
        </aside>
      </div>

      <section className="sources-table-section">
        <div className="sources-table-head">
          <h2>Data Repository</h2>
          <label>
            <span>Filter by status:</span>
            <select value={filter} onChange={(event) => setFilter(event.target.value)}>
              <option>All Sources</option>
              <option>Indexed</option>
              <option>Syncing</option>
            </select>
          </label>
        </div>
        <div className="sources-table-card">
          <table>
            <thead>
              <tr>
                <th>Document Name</th>
                <th>Status</th>
                <th>Source</th>
                <th>Corpus</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {visibleSources.length === 0 ? (
                <tr>
                  <td colSpan={5}>
                    <div className="sources-empty-row">No indexed sources yet.</div>
                  </td>
                </tr>
              ) : (
                visibleSources.map((source) => {
                  const indexed = source.ingestion_status.toLowerCase() === "indexed";
                  return (
                    <tr key={source.id}>
                      <td>
                        <div className="sources-file-cell">
                          <span className="material-symbols-outlined">{iconForSource(source)}</span>
                          <span>{source.file_name}</span>
                        </div>
                      </td>
                      <td>
                        <span className={`sources-status-pill ${indexed ? "is-indexed" : "is-syncing"}`}>
                          <i />
                          {indexed ? "Indexed" : source.ingestion_status}
                        </span>
                      </td>
                      <td>{source.source_type}</td>
                      <td>
                        <span className="sources-corpus-pill">
                          {String(source.source_metadata_json?.corpus || "unassigned")}
                        </span>
                      </td>
                      <td>
                        <button type="button" className="sources-more-button" aria-label="More actions">
                          <span className="material-symbols-outlined">more_vert</span>
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="sources-connected-section">
        <div className="sources-table-head">
          <h2>Connected Data</h2>
        </div>
        <div className="sources-connected-card">
          {connectedData.length === 0 ? (
            <div className="sources-connected-empty">
              <span className="material-symbols-outlined">hub</span>
              <strong>No connected systems yet.</strong>
              <p>Postgres, Google Drive, and Confluence requests will appear here once backend connector support is available.</p>
            </div>
          ) : (
            <div className="sources-connected-list">
              {connectedData.map((source) => (
                <article key={`connected-${source.id}`} className="sources-connected-item">
                  <div className="sources-connected-head">
                    <span className="material-symbols-outlined">database</span>
                    <div>
                      <strong>{source.file_name}</strong>
                      <span>{source.source_type}</span>
                    </div>
                  </div>
                  <p>
                    {String(
                      source.source_metadata_json?.connection_name ||
                      source.source_metadata_json?.database ||
                      source.source_metadata_json?.connector ||
                      "Connected metadata available in source record."
                    )}
                  </p>
                </article>
              ))}
            </div>
          )}
        </div>
      </section>

      <footer className="console-footer">
        <span>Built for enterprise retrieval teams • © 2024</span>
        <div>
          <a href="#privacy">Privacy</a>
          <a href="#terms">Terms</a>
          <a href="#security">Security</a>
          <a href="#status">Status</a>
        </div>
      </footer>
    </div>
  );
}
