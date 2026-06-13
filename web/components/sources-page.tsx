"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { browserApiUrl, browserFetch } from "@/lib/api-browser";

type SourceItem = {
  id: number;
  file_name: string;
  source_type: string;
  ingestion_status: string;
  enrichment_status: string;
  source_metadata_json: Record<string, unknown>;
  freshness: {
    status: string;
    observed_at?: string | null;
    threshold_hours: number;
  };
  latest_ingestion_job?: IngestionJob | null;
};

type UploadResult = {
  source_id: number;
  job_id: number;
  file_name: string;
};

type BatchUploadResult = {
  uploaded_count: number;
  items: UploadResult[];
};

type IngestionJob = {
  id: number;
  source_id?: number | null;
  status: string;
  stage: string;
  stage_label?: string | null;
  priority?: number;
  triggered_by: string;
  error_message?: string | null;
  job_metadata_json: Record<string, unknown>;
  estimated_total_seconds?: number | null;
  estimated_remaining_seconds?: number | null;
  eta_window?: EtaWindow | null;
  wait_window?: EtaWindow | null;
  eta_confidence?: string | null;
  queue_position?: number | null;
  jobs_ahead?: number | null;
  queue_delay_message?: string | null;
  source_file_name?: string | null;
  source_type?: string | null;
  file_size_bytes?: number | null;
  corpus_name?: string | null;
  priority_request?: PriorityRequest | null;
};

type EtaWindow = {
  seconds: number;
  lower_seconds: number;
  upper_seconds: number;
  confidence: string;
};

type PriorityRequest = {
  id: number;
  requested_priority: number;
  reason: string;
  status: string;
  review_reason?: string | null;
  reviewed_at?: string | null;
  created_at?: string | null;
};

type ConnectorRequest = {
  id: number;
  connector_type: string;
  requested_system: string;
  business_reason: string;
  requested_scope_json: Record<string, unknown>;
  status: string;
  review_reason?: string | null;
  created_at?: string | null;
};

type DbConnector = {
  id: number;
  name: string;
  connector_type: "postgres" | "mysql" | string;
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
  connector_metadata_json: Record<string, unknown>;
  health_status: string;
  schedule_enabled: boolean;
  sync_interval_minutes: number;
  next_run_at?: string | null;
  retry_at?: string | null;
  consecutive_failures: number;
};

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
  const stage = formatStage(job);
  if (job.status === "failed") {
    return `${fileName} failed during ${stage}. ${job.error_message || ""}`.trim();
  }
  if (job.status === "completed") {
    return `${fileName} is indexed and ready for search and ask.`;
  }
  if (normalizeJobState(job.status) === "queued") {
    return `${fileName} is waiting in the indexing queue. ${job.queue_delay_message || "The system is estimating when work will begin."}`;
  }
  return `${fileName} is currently in ${stage}. ${job.queue_delay_message || "Retrieval is not ready until indexing finishes."}`;
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

function normalizeJobState(value: string | null | undefined) {
  return String(value || "").trim().toLowerCase();
}

function titleCaseWords(value: string | null | undefined) {
  return String(value || "")
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function isActiveJob(job: IngestionJob | null | undefined) {
  return ["queued", "processing", "running", "paused"].includes(normalizeJobState(job?.status));
}

function formatStage(job: IngestionJob | null | undefined) {
  if (!job) {
    return "indexing";
  }
  return String(job.stage_label || job.stage || "indexing").replace(/_/g, " ");
}

function formatDurationSeconds(seconds: number | null | undefined) {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) {
    return "Unavailable";
  }
  if (seconds < 60) {
    return `${Math.max(Math.round(seconds), 1)} sec`;
  }
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return `${minutes} min`;
  }
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return remainder ? `${hours} hr ${remainder} min` : `${hours} hr`;
}

function formatEtaWindow(window: EtaWindow | null | undefined) {
  if (!window) {
    return "ETA not available yet";
  }
  const lower = formatDurationSeconds(window.lower_seconds);
  const upper = formatDurationSeconds(window.upper_seconds);
  return lower === upper ? lower : `${lower} to ${upper}`;
}

function priorityStatusCopy(request: PriorityRequest | null | undefined) {
  if (!request) {
    return "";
  }
  const normalized = normalizeJobState(request.status);
  if (normalized === "approved") {
    return "Priority request approved. The queue estimate above reflects the updated priority.";
  }
  if (normalized === "denied") {
    return `Priority request denied${request.review_reason ? `: ${request.review_reason}` : "."}`;
  }
  if (normalized === "expired") {
    return "Priority request expired before an admin reviewed it.";
  }
  if (normalized === "under_review") {
    return "Priority request is under admin review.";
  }
  return "Priority request submitted and waiting for admin review.";
}

export function SourcesPage({ view = "sources", canManageConnectors = false }: { view?: "sources" | "uploads" | "connectors"; canManageConnectors?: boolean }) {
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [connectorRequests, setConnectorRequests] = useState<ConnectorRequest[]>([]);
  const [dbConnectors, setDbConnectors] = useState<DbConnector[]>([]);
  const [connectorFeedback, setConnectorFeedback] = useState("");
  const [uploadJob, setUploadJob] = useState<IngestionJob | null>(null);
  const [uploadFileName, setUploadFileName] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [filter, setFilter] = useState("All Sources");
  const [error, setError] = useState("");
  const [priorityReason, setPriorityReason] = useState("");
  const [priorityLevel, setPriorityLevel] = useState("200");
  const [priorityBusy, setPriorityBusy] = useState(false);
  const [priorityFeedback, setPriorityFeedback] = useState("");
  const [connectorDraft, setConnectorDraft] = useState({
    requested_system: "Postgres",
    connector_type: "database",
    business_reason: "",
    database_hint: "",
    table_or_scope: "",
    drive_file_name: "",
    drive_file_url: "",
    access_note: "",
  });

  async function refresh() {
    try {
      const [payload, connectorPayload, requestPayload] = await Promise.all([
        browserFetch<SourceItem[]>("/corpus"),
        browserFetch<DbConnector[]>("/connectors/db"),
        browserFetch<ConnectorRequest[]>("/connectors/requests"),
      ]);
      setSources(payload);
      setDbConnectors(connectorPayload);
      setConnectorRequests(requestPayload);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sources.");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (!isActiveJob(uploadJob) && !sources.some((source) => isActiveJob(source.latest_ingestion_job))) {
      return;
    }
    const timer = window.setTimeout(async () => {
      try {
        await refresh();
        if (uploadJob?.id) {
          const next = await browserFetch<IngestionJob>(`/corpus/jobs/${uploadJob.id}`);
          setUploadJob(next);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to refresh upload job.");
      }
    }, 1200);
    return () => window.clearTimeout(timer);
  }, [sources, uploadJob]);

  async function onFilesSelected(fileList: FileList | null) {
    if (!fileList?.length) {
      return;
    }
    const files = Array.from(fileList);
    setUploading(true);
    setUploadFileName(files.length === 1 ? files[0].name : `${files.length} files selected`);
    setUploadJob(null);
    setError("");
    const formData = new FormData();
    try {
      let selectedJobId: number | null = null;
      let uploadLabel = files.length === 1 ? files[0].name : `${files.length} files selected`;
      const endpoint = files.length === 1 ? "/upload" : "/upload/batch";
      if (files.length === 1) {
        formData.append("file", files[0]);
      } else {
        for (const file of files) {
          formData.append("files", file);
        }
      }
      const response = await fetch(browserApiUrl(endpoint), {
        method: "POST",
        body: formData,
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error((await response.text()) || "Upload failed.");
      }
      if (files.length === 1) {
        const payload = (await response.json()) as UploadResult;
        selectedJobId = payload.job_id;
        uploadLabel = payload.file_name;
      } else {
        const payload = (await response.json()) as BatchUploadResult;
        selectedJobId = payload.items[0]?.job_id ?? null;
        if (payload.items.length > 0) {
          uploadLabel = `${payload.items.length} files queued`;
        }
      }
      setUploadFileName(uploadLabel);
      if (selectedJobId) {
        const job = await browserFetch<IngestionJob>(`/corpus/jobs/${selectedJobId}`);
        setUploadJob(job);
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
      setUploadJob(null);
      setUploadFileName(null);
    } finally {
      setUploading(false);
    }
  }

  function chooseConnectorRequest(system: string) {
    const connectorType = system === "Postgres" || system === "MySQL" ? "database" : system.toLowerCase().replace(/\s+/g, "_");
    setConnectorDraft((current) => ({
      ...current,
      requested_system: system,
      connector_type: connectorType,
      business_reason: current.business_reason || `Need ${system} content available in governed search.`,
    }));
    setConnectorFeedback(`${system} selected. Add scope details and submit the request.`);
  }

  async function addConnectorRequest() {
    setConnectorFeedback("");
    try {
      await browserFetch<ConnectorRequest>("/connectors/requests", {
        method: "POST",
        json: {
          connector_type: connectorDraft.connector_type,
          requested_system: connectorDraft.requested_system,
          business_reason: connectorDraft.business_reason,
          requested_scope_json: {
            database_hint: connectorDraft.database_hint,
            table_or_scope: connectorDraft.table_or_scope,
            drive_file_name: connectorDraft.drive_file_name,
            drive_file_url: connectorDraft.drive_file_url,
            access_note: connectorDraft.access_note,
          },
        },
      });
      setConnectorFeedback(`${connectorDraft.requested_system} request submitted. Track the status below.`);
      await refresh();
    } catch (err) {
      setConnectorFeedback(err instanceof Error ? err.message : "Failed to submit connector request.");
    }
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
      lowerType.includes("db_row") ||
      lowerType.includes("email") ||
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
  const indexedSourceCount = sources.filter((source) => ["indexed", "embedded"].includes(source.ingestion_status.toLowerCase())).length;
  const processingSourceCount = sources.filter((source) => !["indexed", "embedded", "failed"].includes(source.ingestion_status.toLowerCase())).length;
  const activeRequestableJob = uploadJob && isActiveJob(uploadJob) ? uploadJob : sources.find((source) => isActiveJob(source.latest_ingestion_job))?.latest_ingestion_job || null;

  async function submitPriorityRequest() {
    if (!activeRequestableJob) {
      return;
    }
    setPriorityBusy(true);
    setPriorityFeedback("");
    try {
      const next = await browserFetch<PriorityRequest>(`/corpus/jobs/${activeRequestableJob.id}/priority-request`, {
        method: "POST",
        json: {
          reason: priorityReason,
          requested_priority: Number(priorityLevel),
        },
      });
      setUploadJob((current) => (current && current.id === activeRequestableJob.id ? { ...current, priority_request: next, priority: next.requested_priority } : current));
      setPriorityFeedback(priorityStatusCopy(next));
      setPriorityReason("");
      await refresh();
    } catch (err) {
      setPriorityFeedback(err instanceof Error ? err.message : "Failed to submit priority request.");
    } finally {
      setPriorityBusy(false);
    }
  }

  return (
    <div className="sources-page">
      <div className="sources-header">
        <div>
          <h1>{showUploadFirst ? "Upload Documents" : showConnectorsFirst ? "Connectors" : "My Sources"}</h1>
          <p>
            {showUploadFirst
              ? "Add files, watch indexing stages, and confirm when a source is ready for grounded retrieval."
              : showConnectorsFirst
                ? "Request a specific connected source and track admin review, approval, denial, and synced data."
                : "Manage visible sources, uploads, and connector requests from one grounded workspace."}
          </p>
        </div>
        <button type="button" className="stitch-button stitch-button-primary" onClick={() => chooseConnectorRequest("Postgres")}>
          <span className="material-symbols-outlined">add_link</span>
          Request New Connector
        </button>
      </div>

      <div className="sources-top-grid">
        <label className={`sources-upload-card ${uploading ? "is-uploading" : ""}`}>
          <input type="file" multiple hidden onChange={(event) => onFilesSelected(event.target.files)} />
          <div className="sources-upload-icon">
            <span className="material-symbols-outlined">upload_file</span>
          </div>
          <h3>Upload Documents</h3>
          <p>Use this page for direct file onboarding. One or many files can be queued together, and each becomes searchable only after indexing finishes.</p>
          <div className="sources-upload-chips">
            <span>Max 25 MB</span>
            <span>Grounded retrieval</span>
          </div>
          {!uploadStatus && sources.length === 0 ? <strong className="sources-upload-status sources-upload-tip">Start with one or more PDF or text files. This page will show upload acceptance, indexing progress, and the final ready state.</strong> : null}
          {uploadStatus ? <strong className="sources-upload-status">{uploadStatus}</strong> : null}
          <p className="sources-upload-footnote">Backend logs like `GET /corpus/jobs/*` and `GET /corpus` are normal polling while the page refreshes live upload progress.</p>
          {error ? <strong className="sources-upload-error">{error}</strong> : null}
        </label>

        <aside className="sources-connector-card">
          <h4>Connectors</h4>
          <div className="sources-connector-grid">
            {[
              ["database", "Postgres"],
              ["database", "MySQL"],
              ["add_to_drive", "Google Drive"],
              ["alternate_email", "Email Archive"],
            ].map(([icon, label]) => (
              <button
                key={label}
                type="button"
                className="sources-connector-button"
                onClick={() => chooseConnectorRequest(label)}
              >
                <span className="material-symbols-outlined">{icon}</span>
                <span>{label}</span>
                <small>Select</small>
              </button>
            ))}
          </div>
          {connectorRequests[0] ? (
            <div className="sources-connector-note">
              Latest request: <strong>{connectorRequests[0].requested_system}</strong> · {titleCaseWords(connectorRequests[0].status)}
            </div>
          ) : (
            <div className="sources-connector-note">
              Requests go to admins for scope review, connector setup, and governed sync.
            </div>
          )}
          {connectorFeedback ? <div className="sources-connector-note"><strong>{connectorFeedback}</strong></div> : null}
        </aside>
      </div>

      {showConnectorsFirst ? (
        <section className="sources-table-section">
          <div className="sources-connected-card sources-request-card">
            <div className="sources-table-head">
              <h2>Connector Request</h2>
              {canManageConnectors ? <Link href="/console/admin/connectors" className="stitch-button stitch-button-secondary">Open Admin Connectors</Link> : null}
            </div>
            <div className="admin-form-grid">
              <label><span>System</span><select value={connectorDraft.requested_system} onChange={(event) => chooseConnectorRequest(event.target.value)}><option>Postgres</option><option>MySQL</option><option>Google Drive</option><option>Email Archive</option></select></label>
              <label><span>Business Reason</span><input value={connectorDraft.business_reason} onChange={(event) => setConnectorDraft((current) => ({ ...current, business_reason: event.target.value }))} placeholder="Why this data is needed" /></label>
              <label><span>Database Or Workspace</span><input value={connectorDraft.database_hint} onChange={(event) => setConnectorDraft((current) => ({ ...current, database_hint: event.target.value }))} placeholder="CRM prod, finance DB, Drive folder" /></label>
              <label><span>Table Or Scope</span><input value={connectorDraft.table_or_scope} onChange={(event) => setConnectorDraft((current) => ({ ...current, table_or_scope: event.target.value }))} placeholder="schema.table, mailbox, folder, labels" /></label>
              <label><span>Drive File Name</span><input value={connectorDraft.drive_file_name} onChange={(event) => setConnectorDraft((current) => ({ ...current, drive_file_name: event.target.value }))} placeholder="Only for Google Drive" /></label>
              <label><span>Drive File URL</span><input value={connectorDraft.drive_file_url} onChange={(event) => setConnectorDraft((current) => ({ ...current, drive_file_url: event.target.value }))} placeholder="Shared Google Drive URL" /></label>
              <label className="form-span-3"><span>Access Note</span><textarea value={connectorDraft.access_note} onChange={(event) => setConnectorDraft((current) => ({ ...current, access_note: event.target.value }))} rows={3} placeholder="Owner, sensitivity, requested ACL group, or admin access instructions" /></label>
            </div>
            <div className="toolbar-inline">
              <button type="button" className="stitch-button stitch-button-primary" onClick={addConnectorRequest}>Submit Request</button>
            </div>
          </div>
        </section>
      ) : null}

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
                    <div className="sources-empty-row sources-table-empty">
                      {showConnectorsFirst ? (
                        <>
                          <strong>No connected sources are visible yet.</strong>
                          <p>This is normal until an admin configures and syncs an approved connector.</p>
                        </>
                      ) : filter === "Indexed" && processingSourceCount > 0 ? (
                        <>
                          <strong>No files are ready yet.</strong>
                          <p>Sources exist, but they are still parsing, chunking, or embedding. Retrieval becomes available only after indexing completes.</p>
                        </>
                      ) : filter === "Syncing" && indexedSourceCount > 0 ? (
                        <>
                          <strong>No files are currently indexing.</strong>
                          <p>Everything visible right now is already indexed, embedded, failed, or otherwise out of the active processing lane.</p>
                        </>
                      ) : (
                        <>
                          <strong>No sources yet.</strong>
                          <p>Upload the first file above. It will appear here after the source record is created, then move to an indexed ready state once retrieval is available.</p>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ) : (
                visibleSources.map((source) => {
                  const indexed = ["indexed", "embedded"].includes(source.ingestion_status.toLowerCase());
                  const activeJob = isActiveJob(source.latest_ingestion_job) ? source.latest_ingestion_job : null;
                  return (
                    <tr key={source.id}>
                      <td>
                        <div className="sources-file-cell">
                          <span className="material-symbols-outlined">{iconForSource(source)}</span>
                          <span>{source.file_name}</span>
                          <span className={`badge ${source.freshness.status === "fresh" ? "is-good" : source.freshness.status === "stale" ? "is-danger" : "is-warning"}`}>
                            {source.freshness.status}
                          </span>
                        </div>
                      </td>
                      <td>
                        <div className="sources-status-stack">
                          <span className={`sources-status-pill ${indexed ? "is-indexed" : "is-syncing"}`}>
                            <i />
                            {indexed ? "Indexed" : activeJob ? formatStage(activeJob) : source.ingestion_status}
                          </span>
                          <small className="sources-status-copy">
                            {activeJob
                              ? `${activeJob.queue_position ? `Queue #${activeJob.queue_position} • ` : ""}${formatEtaWindow(activeJob.eta_window)} • ${titleCaseWords(activeJob.eta_confidence || "low")} confidence`
                              : readinessCopy(source.ingestion_status)}
                          </small>
                          {activeJob?.priority_request ? <small className="sources-status-copy">{priorityStatusCopy(activeJob.priority_request)}</small> : null}
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
                  <span>{titleCaseWords(uploadJob.status)}</span>
                </div>
              </div>
              <p>Current stage: {formatStage(uploadJob)}</p>
              <p>Estimated completion: {formatEtaWindow(uploadJob.eta_window)} {uploadJob.eta_confidence ? `(${uploadJob.eta_confidence} confidence)` : ""}</p>
              <p>{uploadJob.queue_delay_message || "The queue will update this estimate if earlier enterprise jobs change materially."}</p>
              {uploadJob.priority_request ? <p className="sources-connected-note">{priorityStatusCopy(uploadJob.priority_request)}</p> : null}
              {isActiveJob(uploadJob) ? (
                <div className="page-stack">
                  <div className="sources-upload-chips">
                    <span>{uploadJob.queue_position ? `Queue position ${uploadJob.queue_position}` : "Being processed now"}</span>
                    <span>{uploadJob.jobs_ahead ? `${uploadJob.jobs_ahead} ahead` : "No earlier jobs ahead"}</span>
                  </div>
                  <textarea
                    value={priorityReason}
                    onChange={(event) => setPriorityReason(event.target.value)}
                    placeholder="Need faster indexing? Explain why this file should be prioritized."
                    rows={3}
                  />
                  <div className="toolbar-inline">
                    <select value={priorityLevel} onChange={(event) => setPriorityLevel(event.target.value)}>
                      <option value="200">Urgent</option>
                      <option value="160">High</option>
                      <option value="120">Elevated</option>
                    </select>
                    <button type="button" className="stitch-button stitch-button-primary" disabled={priorityBusy} onClick={submitPriorityRequest}>
                      {priorityBusy ? "Submitting..." : uploadJob.priority_request ? "Update Priority Request" : "Request Priority Review"}
                    </button>
                  </div>
                  <p className="sources-connected-note">Priority requests do not skip governance. They enter the admin queue for review and can update ETA if approved.</p>
                  {priorityFeedback ? <strong className="sources-upload-status">{priorityFeedback}</strong> : null}
                </div>
              ) : null}
              <p className="sources-connected-note">Parsing, chunking, embedding, and indexing/enrichment are expected backend stages. Retrieval becomes available only after the job reaches completed.</p>
            </div>
          ) : showUploadFirst ? (
            <div className="sources-connected-empty">
              <span className="material-symbols-outlined">upload_file</span>
              <strong>No upload started yet.</strong>
              <p>On a clean workspace, start with one file upload above. This panel will switch from upload accepted to indexing progress and finally to ready for retrieval.</p>
            </div>
          ) : dbConnectors.length === 0 && connectedData.length === 0 && (!showConnectorsFirst || connectorRequests.length === 0) ? (
            <div className="sources-connected-empty">
              <span className="material-symbols-outlined">hub</span>
              <strong>No connected systems yet.</strong>
              <p>Approved and synced connector data appears here with corpus and readiness status.</p>
            </div>
          ) : (
            <div className="sources-connected-list">
              {showConnectorsFirst && connectorRequests.map((request) => (
                <article key={`request-${request.id}`} className="sources-connected-item">
                  <div className="sources-connected-head">
                    <span className="material-symbols-outlined">fact_check</span>
                    <div>
                      <strong>{request.requested_system}</strong>
                      <span>{titleCaseWords(request.status)} · {request.created_at || "submitted"}</span>
                    </div>
                  </div>
                  <p>{request.business_reason || "No reason supplied."}</p>
                  {request.review_reason ? <p className="sources-connected-note">{request.review_reason}</p> : null}
                </article>
              ))}
              {dbConnectors.map((connector) => (
                <article key={`db-connector-${connector.id}`} className="sources-connected-item">
                  <div className="sources-connected-head">
                    <span className="material-symbols-outlined">database</span>
                    <div>
                      <strong>{connector.name}</strong>
                      <span>{connector.connector_type} · {connector.table_name}</span>
                    </div>
                  </div>
                  <p>Status: {titleCaseWords(connector.status)}. Cursor: {connector.last_cursor_updated_at || "not synced"} / {connector.last_cursor_id || "none"}.</p>
                  <p>Text: {connector.text_columns.join(", ")}. Filters: {connector.metadata_columns.length ? connector.metadata_columns.join(", ") : "none"}.</p>
                  {connector.acl_group_names.length ? <p>ACL groups: {connector.acl_group_names.join(", ")}</p> : <p>No explicit ACL groups configured; local dev bypass still follows backend ACL rules.</p>}
                  {connector.last_error ? <p className="sources-connected-note">{connector.last_error}</p> : null}
                  {canManageConnectors ? <Link href="/console/admin/connectors" className="stitch-button stitch-button-secondary">Manage</Link> : null}
                </article>
              ))}
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
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
          <Link href="/security">Security</Link>
          <Link href="/status">Status</Link>
        </div>
      </footer>
    </div>
  );
}
