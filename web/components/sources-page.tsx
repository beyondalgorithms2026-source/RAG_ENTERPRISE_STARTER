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

export function SourcesPage({ view = "sources" }: { view?: "sources" | "uploads" | "connectors" }) {
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [connectorRequests, setConnectorRequests] = useState<ConnectorRequest[]>([]);
  const [uploadJob, setUploadJob] = useState<IngestionJob | null>(null);
  const [uploadFileName, setUploadFileName] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [filter, setFilter] = useState("All Sources");
  const [error, setError] = useState("");
  const [priorityReason, setPriorityReason] = useState("");
  const [priorityLevel, setPriorityLevel] = useState("200");
  const [priorityBusy, setPriorityBusy] = useState(false);
  const [priorityFeedback, setPriorityFeedback] = useState("");

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
                    <div className="sources-empty-row sources-table-empty">
                      {showConnectorsFirst ? (
                        <>
                          <strong>No connected sources are visible yet.</strong>
                          <p>This is normal until a connector request turns into a real synced source. The request flow is live now; connector ingestion lands later.</p>
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
          ) : connectedData.length === 0 ? (
            <div className="sources-connected-empty">
              <span className="material-symbols-outlined">hub</span>
              <strong>No connected systems yet.</strong>
              <p>Connector requests can be recorded now. Real Postgres, Google Drive, and Confluence ingestion will populate this area once backend connector support is available.</p>
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
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
          <Link href="/security">Security</Link>
          <Link href="/status">Status</Link>
        </div>
      </footer>
    </div>
  );
}
