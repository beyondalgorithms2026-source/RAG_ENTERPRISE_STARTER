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

type IngestionJob = {
  id: number;
  source_id?: number | null;
  status: string;
  stage: string;
  triggered_by: string;
  error_message?: string | null;
  job_metadata_json: Record<string, unknown>;
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

function statusCopy(job: IngestionJob | null, fileName: string | null) {
  if (!job || !fileName) {
    return "";
  }
  const stage = job.stage.replace(/_/g, " ");
  if (job.status === "failed") {
    return `${fileName} failed during ${stage}. ${job.error_message || ""}`.trim();
  }
  if (job.status === "completed") {
    return `${fileName} is indexed and ready for search and ask.`;
  }
  if (stage === "embed") {
    return `${fileName} is embedding now. Retrieval is not ready until indexing finishes.`;
  }
  return `${fileName} is ${job.status} during ${stage}.`;
}

function readinessCopy(status: string) {
  const normalized = status.toLowerCase();
  if (["indexed", "embedded"].includes(normalized)) {
    return "Ready for search and ask.";
  }
  if (normalized === "chunked") {
    return "Chunked only. Still waiting for embedding before retrieval is ready.";
  }
  if (normalized === "failed") {
    return "Processing failed. Re-upload or inspect the job state.";
  }
  return "Still processing. This file is not searchable yet.";
}

export function SourcesPage({ view = "sources" }: { view?: "sources" | "uploads" | "connectors" }) {
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [connectorRequests, setConnectorRequests] = useState<ConnectorRequest[]>([]);
  const [uploadJob, setUploadJob] = useState<IngestionJob | null>(null);
  const [uploadFileName, setUploadFileName] = useState<string | null>(null);
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

  useEffect(() => {
    if (!uploadJob || uploadJob.status === "completed" || uploadJob.status === "failed") {
      return;
    }
    const timer = window.setTimeout(async () => {
      try {
        const next = await browserFetch<IngestionJob>(`/corpus/jobs/${uploadJob.id}`);
        setUploadJob(next);
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to refresh upload job.");
      }
    }, 1200);
    return () => window.clearTimeout(timer);
  }, [uploadJob]);

  async function onFileSelected(file: File | null) {
    if (!file) {
      return;
    }
    setUploading(true);
    setUploadFileName(file.name);
    setUploadJob(null);
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
      const job = await browserFetch<IngestionJob>(`/corpus/jobs/${payload.job_id}`);
      setUploadJob(job);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
      setUploadJob(null);
      setUploadFileName(null);
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
      return source.ingestion_status.toLowerCase() === "indexed" || source.ingestion_status.toLowerCase() === "embedded";
    }
    if (filter === "Syncing") {
      return !["indexed", "embedded"].includes(source.ingestion_status.toLowerCase());
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

  const showUploadFirst = view === "uploads";
  const showConnectorsFirst = view === "connectors";
  const uploadStatus = statusCopy(uploadJob, uploadFileName);

  return (
    <div className="sources-page">
      <div className="sources-header">
        <div>
          <h1>{showUploadFirst ? "Upload Documents" : showConnectorsFirst ? "Connectors" : "My Sources"}</h1>
          <p>
            {showUploadFirst
              ? "Add files, watch indexing stages, and confirm when a source is ready for grounded retrieval."
              : showConnectorsFirst
                ? "Request connectors now, then track available connected sources as backend connector support lands."
                : "Manage visible sources, uploads, and connector requests from one grounded workspace."}
          </p>
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
          <p>Use this page for direct file onboarding. A file is searchable only after indexing finishes; parsing and chunking alone are not enough.</p>
          <div className="sources-upload-chips">
            <span>Max 25 MB</span>
            <span>Grounded retrieval</span>
          </div>
          {uploadStatus ? <strong className="sources-upload-status">{uploadStatus}</strong> : null}
          <p className="sources-upload-footnote">Backend logs like `GET /corpus/jobs/*` and `GET /corpus` are normal polling while the page refreshes live upload progress.</p>
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
                <small>Request flow live</small>
              </button>
            ))}
          </div>
          {connectorRequests[0] ? (
            <div className="sources-connector-note">
              Latest request: <strong>{connectorRequests[0].system}</strong>
            </div>
          ) : (
            <div className="sources-connector-note">
              Requests are stored locally for now; full connector configuration lands in later milestones.
            </div>
          )}
        </aside>
      </div>

      <section className="sources-table-section">
        <div className="sources-table-head">
          <h2>{showConnectorsFirst ? "Connected Data" : "Data Repository"}</h2>
          <label>
            <span>Filter by status:</span>
            <select value={filter} onChange={(event) => setFilter(event.target.value)}>
              <option>All Sources</option>
              <option>Indexed</option>
              <option>Syncing</option>
            </select>
          </label>
        </div>
        <div className="sources-status-legend">
          <span><i className="is-indexed" />Indexed / Embedded: ready for search and ask</span>
          <span><i className="is-syncing" />Chunked / Processing: not searchable yet</span>
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
                    <div className="sources-empty-row">
                      {showConnectorsFirst ? "No connected sources are visible yet." : "No indexed sources yet."}
                    </div>
                  </td>
                </tr>
              ) : (
                visibleSources.map((source) => {
                  const indexed = ["indexed", "embedded"].includes(source.ingestion_status.toLowerCase());
                  return (
                    <tr key={source.id}>
                      <td>
                        <div className="sources-file-cell">
                          <span className="material-symbols-outlined">{iconForSource(source)}</span>
                          <span>{source.file_name}</span>
                        </div>
                      </td>
                      <td>
                        <div className="sources-status-stack">
                          <span className={`sources-status-pill ${indexed ? "is-indexed" : "is-syncing"}`}>
                            <i />
                            {indexed ? "Indexed" : source.ingestion_status}
                          </span>
                          <small className="sources-status-copy">{readinessCopy(source.ingestion_status)}</small>
                        </div>
                      </td>
                      <td>{source.source_type}</td>
                      <td>
                        <span className="sources-corpus-pill">
                          {String(source.source_metadata_json?.corpus || "unassigned")}
                        </span>
                      </td>
                      <td>
                        <a href={browserApiUrl(`/corpus/${source.id}/file`)} className="sources-open-link" target="_blank" rel="noreferrer">
                          Open file
                        </a>
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
          <h2>{showUploadFirst ? "Latest Upload State" : "Connected Data"}</h2>
        </div>
        <div className="sources-connected-card">
          {showUploadFirst && uploadJob ? (
            <div className="sources-connected-item">
              <div className="sources-connected-head">
                <span className="material-symbols-outlined">sync</span>
                <div>
                  <strong>{uploadFileName}</strong>
                  <span>{uploadJob.status}</span>
                </div>
              </div>
              <p>Current stage: {uploadJob.stage.replace(/_/g, " ")}</p>
              <p className="sources-connected-note">Parsing, source-parts saved, chunking, and embedding are expected backend stages. `embed.started` means vector preparation is underway and the file is not searchable yet.</p>
            </div>
          ) : connectedData.length === 0 ? (
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
