"use client";

import Link from "next/link";
import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { browserApiUrl, browserFetch } from "@/lib/api-browser";
import { findThreadMessageByRequestId } from "@/lib/workspace";

type GenericMap = Record<string, unknown>;

type AdminSectionIntroProps = {
  eyebrow: string;
  title: string;
  description: string;
  badge?: string;
};

type SourceDraft = {
  corpusName: string;
  sensitivityLabel: string;
  aclGroups: string;
};

type SavedViewEntry = {
  name: string;
  filters: Record<string, string>;
};

const ADMIN_SAVED_VIEWS_STORAGE_KEY = "rag_admin_saved_views_v1";

function readSavedAdminViews(viewKey: string): SavedViewEntry[] {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(ADMIN_SAVED_VIEWS_STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as Record<string, SavedViewEntry[]>) : {};
    const views = parsed?.[viewKey];
    if (!Array.isArray(views)) {
      return [];
    }
    return views.filter((entry) => typeof entry?.name === "string" && entry.filters && typeof entry.filters === "object");
  } catch {
    return [];
  }
}

function writeSavedAdminViews(viewKey: string, views: SavedViewEntry[]) {
  if (typeof window === "undefined") {
    return;
  }
  try {
    const raw = window.localStorage.getItem(ADMIN_SAVED_VIEWS_STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as Record<string, SavedViewEntry[]>) : {};
    parsed[viewKey] = views;
    window.localStorage.setItem(ADMIN_SAVED_VIEWS_STORAGE_KEY, JSON.stringify(parsed));
  } catch {
    // Best-effort UX only.
  }
}

function normalizeText(value: unknown) {
  return String(value ?? "").trim().toLowerCase();
}

function matchesQuery(query: string, values: unknown[]) {
  const normalizedQuery = normalizeText(query);
  if (!normalizedQuery) {
    return true;
  }
  return values.some((value) => normalizeText(value).includes(normalizedQuery));
}

function toNumber(value: unknown) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
}

function toTimestampValue(value: unknown) {
  const numeric = new Date(String(value ?? "")).getTime();
  return Number.isFinite(numeric) ? numeric : 0;
}

function roundNumber(value: number, digits = 0) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

function sortGenericMaps(items: GenericMap[], sort: string, handlers: Record<string, (left: GenericMap, right: GenericMap) => number>) {
  const handler = handlers[sort];
  if (!handler) {
    return items;
  }
  return [...items].sort(handler);
}

function saveNamedView(
  viewKey: string,
  name: string,
  filters: Record<string, string>,
  setSavedViews: (views: SavedViewEntry[]) => void,
) {
  const trimmed = name.trim();
  if (!trimmed) {
    return;
  }
  const next = [
    { name: trimmed, filters },
    ...readSavedAdminViews(viewKey).filter((entry) => entry.name !== trimmed),
  ].slice(0, 8);
  writeSavedAdminViews(viewKey, next);
  setSavedViews(next);
}

function deleteNamedView(viewKey: string, name: string, setSavedViews: (views: SavedViewEntry[]) => void) {
  const next = readSavedAdminViews(viewKey).filter((entry) => entry.name !== name);
  writeSavedAdminViews(viewKey, next);
  setSavedViews(next);
}

function filtersMatch(applied: Record<string, string>, draft: Record<string, string>) {
  const keys = new Set([...Object.keys(applied), ...Object.keys(draft)]);
  return Array.from(keys).every((key) => String(applied[key] || "") === String(draft[key] || ""));
}

function titleCaseWords(value: unknown) {
  return String(value || "")
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
}

function questionPreview(value: unknown) {
  const text = String(value || "").trim().replace(/\s+/g, " ");
  if (!text) {
    return "Open trace";
  }
  return text.length > 72 ? `${text.slice(0, 69)}...` : text;
}

function isActiveJobStatus(value: unknown) {
  return ["queued", "processing", "running", "pending"].includes(normalizeText(value));
}

function jobStatusRank(value: unknown) {
  const normalized = normalizeText(value);
  if (["processing", "running", "queued", "pending"].includes(normalized)) {
    return 0;
  }
  if (["failed", "error"].includes(normalized)) {
    return 1;
  }
  if (["completed", "embedded", "indexed"].includes(normalized)) {
    return 2;
  }
  return 3;
}

function formatJobStage(value: unknown) {
  const normalized = normalizeText(value);
  if (!normalized) {
    return "Unknown stage";
  }
  const labels: Record<string, string> = {
    queued: "Waiting in queue",
    parsing: "Reading document",
    chunking: "Splitting into searchable sections",
    embedding: "Building semantic index",
    "indexing/enrichment": "Finalizing retrieval data",
    paused: "Paused",
    cancelled: "Cancelled",
    completed: "Completed",
    failed: "Failed",
  };
  return labels[normalized] || titleCaseWords(normalized);
}

function formatJobTrigger(value: unknown) {
  const normalized = normalizeText(value);
  if (normalized === "upload") {
    return "Started from an upload request";
  }
  if (normalized === "admin_reindex") {
    return "Started by an admin reindex";
  }
  if (normalized === "system") {
    return "Started by the system";
  }
  return `Started by ${String(value || "the system")}`;
}

function formatJobSourceName(job: GenericMap) {
  if (job.source_file_name) {
    return String(job.source_file_name);
  }
  if (normalizeText(job.triggered_by) === "upload") {
    return "Uploaded file awaiting source details";
  }
  if (normalizeText(job.triggered_by) === "admin_reindex") {
    return `Admin reindex for source #${String(job.source_id || job.id || "pending")}`;
  }
  if (normalizeText(job.triggered_by) === "admin_retry") {
    return `Retry job for source #${String(job.source_id || job.id || "pending")}`;
  }
  return `Queued source job #${String(job.id || "pending")}`;
}

function formatJobOwner(job: GenericMap) {
  return String(job.owner_display_name || job.owner_email || job.owner_external_user_id || "Unknown owner");
}

function formatEtaWindow(value: unknown) {
  if (!value || typeof value !== "object") {
    return "ETA unavailable";
  }
  const payload = value as Record<string, unknown>;
  const lower = formatDuration(payload.lower_seconds);
  const upper = formatDuration(payload.upper_seconds);
  return lower === upper ? lower : `${lower} to ${upper}`;
}

function formatQueuePosition(job: GenericMap) {
  const position = Number(job.queue_position);
  if (!Number.isFinite(position) || position <= 0) {
    return "Active now";
  }
  return `Queue #${position}`;
}

function formatPriorityLabel(value: unknown) {
  const priority = Number(value || 0);
  if (priority >= 200) {
    return "Urgent";
  }
  if (priority >= 150) {
    return "High";
  }
  if (priority >= 120) {
    return "Elevated";
  }
  return "Normal";
}

function formatJobTimingLabel(job: GenericMap) {
  if (isActiveJobStatus(job.status)) {
    return `${formatQueuePosition(job)} • ${formatEtaWindow(job.eta_window)}`;
  }
  if (normalizeText(job.status) === "failed" || normalizeText(job.status) === "error") {
    return job.completed_at ? `Failed ${formatTimestamp(job.completed_at)}` : "Failed before completion";
  }
  if (job.completed_at) {
    return `Completed ${formatTimestamp(job.completed_at)}`;
  }
  return formatDuration(job.duration_seconds);
}

function formatJobHeadline(job: GenericMap) {
  const sourceName = formatJobSourceName(job);
  const stage = formatJobStage(job.stage_label || job.stage);
  const normalizedStatus = normalizeText(job.status);
  if (normalizedStatus === "completed") {
    return `${sourceName} completed indexing`;
  }
  if (normalizedStatus === "failed" || normalizedStatus === "error") {
    return `${sourceName} needs attention`;
  }
  return `${sourceName} is ${stage.toLowerCase()}`;
}

function formatJobSubline(job: GenericMap) {
  const parts = [formatJobOwner(job)];
  if (job.corpus_name) {
    parts.push(`${String(job.corpus_name)} corpus`);
  }
  if (job.source_type) {
    parts.push(String(job.source_type).toUpperCase());
  }
  return parts.join(" • ");
}

function buildJobOperatorSummary(job: GenericMap) {
  const sourceName = formatJobSourceName(job);
  const status = titleCaseWords(job.status || "unknown");
  const stage = formatJobStage(job.stage_label || job.stage);
  const trigger = formatJobTrigger(job.triggered_by);
  const owner = ` It belongs to ${formatJobOwner(job)}.`;
  const corpus = job.corpus_name ? ` It is linked to the ${String(job.corpus_name)} corpus.` : " It is not linked to a corpus yet.";
  const eta = isActiveJobStatus(job.status)
    ? ` ${String(job.status).toLowerCase() === "queued" ? "Estimated completion" : "Estimated time remaining"} is ${formatEtaWindow(job.eta_window)}.`
    : "";
  return `${sourceName} is currently ${stage.toLowerCase()} with status ${status}. ${trigger}.${owner}${corpus}${eta}`;
}

function traceLinkTarget(trace: GenericMap) {
  const requestId = String(trace.request_id || "");
  const target = requestId ? findThreadMessageByRequestId(requestId) : null;
  if (target) {
    return `/console/workspace/chat/${target.threadId}#message-${target.messageId}`;
  }
  return `/console/admin/traces`;
}

function SavedViewsToolbar({
  viewLabel,
  draftName,
  onDraftNameChange,
  onSave,
  savedViews,
  onApply,
  onDelete,
}: {
  viewLabel: string;
  draftName: string;
  onDraftNameChange: (value: string) => void;
  onSave: () => void;
  savedViews: SavedViewEntry[];
  onApply: (entry: SavedViewEntry) => void;
  onDelete: (entry: SavedViewEntry) => void;
}) {
  return (
    <div className="admin-saved-view-stack">
      <div className="admin-saved-view-form">
        <input value={draftName} onChange={(event) => onDraftNameChange(event.target.value)} placeholder={`Save ${viewLabel} view`} />
        <button type="button" className="button button-secondary" onClick={onSave} disabled={!draftName.trim()}>
          Save view
        </button>
      </div>
      {savedViews.length ? (
        <div className="admin-saved-view-list">
          {savedViews.map((entry) => (
            <div key={entry.name} className="admin-saved-view-chip">
              <button type="button" className="admin-inline-link" onClick={() => onApply(entry)}>
                {entry.name}
              </button>
              <button type="button" className="admin-delete-chip" aria-label={`Delete saved view ${entry.name}`} onClick={() => onDelete(entry)}>
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function SummaryMetricCard({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <article className={`card admin-mini-card ${tone || ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function formatTimestamp(value: unknown) {
  if (!value) {
    return "Unavailable";
  }
  const parsed = new Date(String(value));
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }
  return parsed.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatCount(value: unknown, singular: string, plural = `${singular}s`) {
  const count = Number(value || 0);
  return `${count} ${count === 1 ? singular : plural}`;
}

function formatFileSize(value: unknown) {
  const size = Number(value || 0);
  if (!size) {
    return "Size unavailable";
  }
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDuration(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "In progress";
  }
  const seconds = Number(value);
  if (!Number.isFinite(seconds)) {
    return "In progress";
  }
  if (seconds === 0) {
    return "Pending timing";
  }
  if (seconds < 1) {
    return `${Math.round(seconds * 1000)} ms`;
  }
  return `${seconds.toFixed(seconds >= 10 ? 0 : 1)} s`;
}

function statusTone(value: unknown) {
  const normalized = String(value || "").toLowerCase();
  if (["completed", "embedded", "indexed", "active", "available", "ok"].includes(normalized)) {
    return "is-good";
  }
  if (["failed", "error", "missing", "denied"].includes(normalized)) {
    return "is-danger";
  }
  if (["queued", "processing", "running", "pending"].includes(normalized)) {
    return "is-warning";
  }
  return "";
}

function AdminSectionIntro({ eyebrow, title, description, badge }: AdminSectionIntroProps) {
  return (
    <section className="admin-route-intro">
      <div>
        <span className="admin-route-eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {badge ? <span className="badge">{badge}</span> : null}
    </section>
  );
}

function EmptyState({
  title,
  copy,
  icon = "inbox",
  actions,
}: {
  title: string;
  copy: string;
  icon?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="admin-empty-state">
      <span className="material-symbols-outlined">{icon}</span>
      <strong>{title}</strong>
      <p>{copy}</p>
      {actions ? <div className="admin-empty-state-actions">{actions}</div> : null}
    </div>
  );
}

function sourceDraftFromItem(source: GenericMap | null): SourceDraft {
  return {
    corpusName: String(source?.corpus_name || ""),
    sensitivityLabel: String(source?.sensitivity_label || "internal"),
    aclGroups: Array.isArray(source?.acl_groups) ? (source?.acl_groups as string[]).join(", ") : "",
  };
}

function isPlainRecord(value: unknown): value is GenericMap {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function formatDataKey(value: unknown) {
  return titleCaseWords(String(value ?? "").replace(/[.-]/g, "_")) || "Value";
}

function formatDataValue(value: unknown) {
  if (value === null) {
    return "null";
  }
  if (value === undefined) {
    return "Not provided";
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (typeof value === "number") {
    return String(value);
  }
  const text = String(value);
  return text.trim() ? text : "Empty";
}

function DataReader({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (Array.isArray(value)) {
    if (!value.length) {
      return <span className="data-reader-empty">Empty list</span>;
    }
    return (
      <div className="data-reader-table" data-depth={depth}>
        {value.map((item, index) => (
          <div className="data-reader-row" key={`${depth}-${index}`}>
            <div className="data-reader-key">{`Item ${index + 1}`}</div>
            <div className="data-reader-value">
              {isPlainRecord(item) || Array.isArray(item) ? <DataReader value={item} depth={depth + 1} /> : formatDataValue(item)}
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (isPlainRecord(value)) {
    const entries = Object.entries(value);
    if (!entries.length) {
      return <span className="data-reader-empty">No fields</span>;
    }
    return (
      <div className="data-reader-table" data-depth={depth}>
        {entries.map(([key, item]) => (
          <div className="data-reader-row" key={`${depth}-${key}`}>
            <div className="data-reader-key">{formatDataKey(key)}</div>
            <div className="data-reader-value">
              {isPlainRecord(item) || Array.isArray(item) ? <DataReader value={item} depth={depth + 1} /> : formatDataValue(item)}
            </div>
          </div>
        ))}
      </div>
    );
  }

  return <span className="data-reader-empty">{formatDataValue(value)}</span>;
}

function JsonPanel({ value }: { value: unknown }) {
  const [activeTab, setActiveTab] = useState<"reader" | "json">("reader");

  return (
    <div className="data-panel">
      <div className="data-panel-tabs" role="tablist" aria-label="Payload view mode">
        <button
          type="button"
          className={activeTab === "reader" ? "is-active" : ""}
          onClick={() => setActiveTab("reader")}
          role="tab"
          aria-selected={activeTab === "reader"}
        >
          Reader
        </button>
        <button
          type="button"
          className={activeTab === "json" ? "is-active" : ""}
          onClick={() => setActiveTab("json")}
          role="tab"
          aria-selected={activeTab === "json"}
        >
          Raw JSON
        </button>
      </div>
      {activeTab === "reader" ? (
        <div className="data-reader-panel" role="tabpanel">
          <DataReader value={value ?? {}} />
        </div>
      ) : (
        <pre className="json-panel" role="tabpanel">{JSON.stringify(value ?? {}, null, 2)}</pre>
      )}
    </div>
  );
}

export function CorporaAdminPanel() {
  const [payload, setPayload] = useState<{ corpora: GenericMap[]; sources: GenericMap[]; unassigned_source_count: number } | null>(null);
  const [selectedCorpusName, setSelectedCorpusName] = useState("");
  const [assignSourceIds, setAssignSourceIds] = useState<number[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  async function refresh() {
    setIsLoading(true);
    try {
      const next = await browserFetch<{ corpora: GenericMap[]; sources: GenericMap[]; unassigned_source_count: number }>("/admin/corpora");
      setPayload(next);
      setError("");
      setSelectedCorpusName((current) => current || String(next.corpora?.[0]?.name || ""));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load corpora.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const selectedCorpus = useMemo(
    () => payload?.corpora.find((item) => String(item.name) === selectedCorpusName) || null,
    [payload, selectedCorpusName],
  );
  const assignedSources = useMemo(
    () => (payload?.sources || []).filter((item) => String(item.corpus_name || "") === selectedCorpusName),
    [payload, selectedCorpusName],
  );
  const unassignedSources = useMemo(
    () => (payload?.sources || []).filter((item) => !item.corpus_name),
    [payload],
  );

  async function createCorpus(event: FormEvent) {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      await browserFetch("/admin/corpora", {
        method: "POST",
        json: { name, description, metadata_json: {} },
      });
      setName("");
      setDescription("");
      await refresh();
      setSelectedCorpusName(name.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create corpus.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function assignSelectedSources() {
    if (!selectedCorpusName || assignSourceIds.length === 0) {
      return;
    }
    setIsSubmitting(true);
    try {
      await browserFetch(`/admin/corpora/${encodeURIComponent(selectedCorpusName)}/sources`, {
        method: "PATCH",
        json: { source_ids: assignSourceIds },
      });
      setAssignSourceIds([]);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to assign sources.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="admin-route-page">
      <AdminSectionIntro
        eyebrow="Interactive"
        title="Corpora"
        description="Create corpora, inspect real source distribution, and assign unplaced sources from a routed operator surface."
        badge={`${payload?.corpora?.length || 0} corpora`}
      />
      {error ? <div className="error-banner">{error}</div> : null}
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Create Corpus</h2>
            <p>Create a new corpus without leaving the admin workspace.</p>
          </div>
        </div>
        <form className="admin-form-grid" onSubmit={createCorpus}>
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Corpus name" />
          <input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Description" />
          <button className="button button-primary" type="submit" disabled={isSubmitting || !name.trim()}>
            {isSubmitting ? "Saving..." : "Create corpus"}
          </button>
        </form>
      </section>

      <div className="results-grid">
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Corpus Inventory</h2>
              <p>Live corpus definitions plus their current source counts.</p>
            </div>
            <span className="badge">{formatCount(payload?.unassigned_source_count, "unassigned source")}</span>
          </div>
          <div className="table-list">
            {isLoading ? <EmptyState title="Loading corpora..." copy="Fetching the current corpus registry and placement counts." icon="progress_activity" /> : payload?.corpora?.length ? payload.corpora.map((corpus) => (
              <article key={String(corpus.name)} className="table-row">
                <div>
                  <strong>{String(corpus.name)}</strong>
                  <span className="muted-copy">{String(corpus.description || "No description yet.")}</span>
                </div>
                <div className="table-metrics">
                  <span>{formatCount(corpus.source_count, "source")}</span>
                  <span>{formatTimestamp(corpus.updated_at)}</span>
                  <button type="button" className="button button-secondary" onClick={() => setSelectedCorpusName(String(corpus.name))}>
                    Inspect
                  </button>
                </div>
              </article>
            )) : <EmptyState title="No corpora yet." copy="This is normal on a clean install. Create the first corpus here, then assign uploaded sources so retrieval can be scoped intentionally." icon="folder_copy" />}
          </div>
        </section>

        <section className="card">
          <div className="section-head">
            <div>
              <h2>{selectedCorpus ? `${String(selectedCorpus.name)} detail` : "Corpus detail"}</h2>
              <p>Assigned sources and unassigned candidates for the selected corpus.</p>
            </div>
          </div>
          {!selectedCorpus ? <EmptyState title={isLoading ? "Loading corpus detail..." : "Select a corpus."} copy={isLoading ? "Waiting for corpus inventory before detail and placement actions can render." : "Choose a corpus from the inventory to inspect its assigned sources and placement workflow."} icon={isLoading ? "progress_activity" : "folder"} /> : (
            <div className="page-stack">
              <div className="table-list">
                {assignedSources.length ? assignedSources.map((source) => (
                  <article key={String(source.id)} className="table-row">
                    <div>
                      <strong>{String(source.file_name)}</strong>
                      <span className="muted-copy">{`${String(source.source_type || "source")} • ${String(source.sensitivity_label || "internal")}`}</span>
                    </div>
                    <div className="table-metrics">
                      <span className={`badge ${statusTone(source.ingestion_status)}`}>{String(source.ingestion_status || "unknown")}</span>
                    </div>
                  </article>
                )) : <EmptyState title="No assigned sources yet." copy={payload?.sources?.length ? "This corpus exists, but nothing is assigned to it yet. Assign sources below or use the Sources page for source-first administration." : "No sources exist yet. Upload the first file from the user workspace, then return here to assign it into this corpus."} icon="move_to_inbox" />}
              </div>
              <div className="section-head">
                <div>
                  <h2>Assign unplaced sources</h2>
                  <p>Place unassigned sources into the selected corpus.</p>
                </div>
                <button type="button" className="button button-primary" disabled={isSubmitting || assignSourceIds.length === 0} onClick={assignSelectedSources}>
                  {isSubmitting ? "Saving..." : "Assign selected"}
                </button>
              </div>
              <div className="table-list">
                {unassignedSources.length ? unassignedSources.map((source) => {
                  const sourceId = Number(source.id);
                  const checked = assignSourceIds.includes(sourceId);
                  return (
                    <label key={sourceId} className="table-row table-row-check">
                      <div>
                        <strong>{String(source.file_name)}</strong>
                        <span className="muted-copy">{`${String(source.source_type || "source")} • ${formatFileSize(source.file_size_bytes)}`}</span>
                      </div>
                      <div className="table-metrics">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(event) =>
                            setAssignSourceIds((current) =>
                              event.target.checked ? [...current, sourceId] : current.filter((item) => item !== sourceId),
                            )
                          }
                        />
                      </div>
                    </label>
                  );
                }) : <EmptyState title="No unassigned sources." copy={payload?.sources?.length ? "All current sources already belong to a corpus." : "No uploaded sources are available yet. The first user upload will appear here once the source record is created."} icon="inventory_2" />}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export function SourcesAdminPanel() {
  const searchParams = useSearchParams();
  const sourceIdParam = searchParams.get("sourceId");
  const defaultFilters = { query: "", status: "all", corpus: "all", sensitivity: "all", sort: "name_asc" };
  const [payload, setPayload] = useState<{ sources: GenericMap[] }>({ sources: [] });
  const [corporaPayload, setCorporaPayload] = useState<{ corpora: GenericMap[] }>({ corpora: [] });
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [draft, setDraft] = useState<SourceDraft>(sourceDraftFromItem(null));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [filters, setFilters] = useState({ ...defaultFilters });
  const [draftFilters, setDraftFilters] = useState({ ...defaultFilters });
  const [savedViews, setSavedViews] = useState<SavedViewEntry[]>([]);
  const [savedViewName, setSavedViewName] = useState("");
  const [selectedSourceIds, setSelectedSourceIds] = useState<number[]>([]);
  const [bulkCorpusName, setBulkCorpusName] = useState("__keep__");
  const [bulkSensitivityLabel, setBulkSensitivityLabel] = useState("__keep__");

  useEffect(() => {
    setSavedViews(readSavedAdminViews("sources"));
  }, []);

  async function refresh() {
    setIsLoading(true);
    try {
      const [sources, corpora] = await Promise.all([
        browserFetch<{ sources: GenericMap[] }>("/admin/sources"),
        browserFetch<{ corpora: GenericMap[] }>("/admin/corpora"),
      ]);
      setPayload(sources);
      setCorporaPayload({ corpora: corpora.corpora || [] });
      setError("");
      setSelectedSourceId((current) => current || sourceIdParam || String(sources.sources?.[0]?.id || ""));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sources.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [sourceIdParam]);

  const selectedSource = useMemo(
    () => payload.sources.find((item) => String(item.id) === selectedSourceId) || null,
    [payload, selectedSourceId],
  );

  const visibleSources = useMemo(() => {
    const filtered = payload.sources.filter((source) => {
      if (!matchesQuery(filters.query, [source.file_name, source.source_type, source.corpus_name, source.sensitivity_label, (source.acl_groups as string[] | undefined)?.join(", ")])) {
        return false;
      }
      if (filters.status !== "all" && normalizeText(source.ingestion_status) !== filters.status) {
        return false;
      }
      if (filters.corpus !== "all" && normalizeText(source.corpus_name) !== filters.corpus) {
        return false;
      }
      if (filters.sensitivity !== "all" && normalizeText(source.sensitivity_label) !== filters.sensitivity) {
        return false;
      }
      return true;
    });

    return sortGenericMaps(filtered, filters.sort, {
      name_asc: (left, right) => String(left.file_name || "").localeCompare(String(right.file_name || "")),
      name_desc: (left, right) => String(right.file_name || "").localeCompare(String(left.file_name || "")),
      size_desc: (left, right) => toNumber(right.file_size_bytes) - toNumber(left.file_size_bytes),
      size_asc: (left, right) => toNumber(left.file_size_bytes) - toNumber(right.file_size_bytes),
      status: (left, right) => String(left.ingestion_status || "").localeCompare(String(right.ingestion_status || "")),
      corpus: (left, right) => String(left.corpus_name || "").localeCompare(String(right.corpus_name || "")),
    });
  }, [payload.sources, filters]);

  const corpusOptions = useMemo(
    () => corporaPayload.corpora.map((corpus) => String(corpus.name)).sort((left, right) => left.localeCompare(right)),
    [corporaPayload.corpora],
  );

  const selectionCount = selectedSourceIds.length;
  const filteredCount = visibleSources.length;
  const readyCount = visibleSources.filter((source) => ["indexed", "embedded"].includes(normalizeText(source.ingestion_status))).length;
  const hasPendingFilterChanges = !filtersMatch(filters, draftFilters);

  useEffect(() => {
    setSelectedSourceId((current) => (current && visibleSources.some((item) => String(item.id) === current) ? current : String(visibleSources[0]?.id || "")));
  }, [visibleSources]);

  useEffect(() => {
    const allSourceIds = new Set(payload.sources.map((source) => Number(source.id)));
    setSelectedSourceIds((current) => current.filter((item) => allSourceIds.has(item)));
  }, [payload.sources]);

  useEffect(() => {
    setDraft(sourceDraftFromItem(selectedSource));
  }, [selectedSource]);

  function applySavedView(entry: SavedViewEntry) {
    const nextFilters = {
      query: String(entry.filters.query || ""),
      status: String(entry.filters.status || "all"),
      corpus: String(entry.filters.corpus || "all"),
      sensitivity: String(entry.filters.sensitivity || "all"),
      sort: String(entry.filters.sort || "name_asc"),
    };
    setDraftFilters(nextFilters);
    setFilters(nextFilters);
  }

  function saveCurrentView() {
    saveNamedView("sources", savedViewName, draftFilters, setSavedViews);
    setSavedViewName("");
  }

  function removeSavedView(entry: SavedViewEntry) {
    deleteNamedView("sources", entry.name, setSavedViews);
  }

  function toggleSelectedSource(sourceId: number, checked: boolean) {
    setSelectedSourceIds((current) =>
      checked ? [...new Set([...current, sourceId])] : current.filter((item) => item !== sourceId),
    );
  }

  function toggleAllVisibleSources(checked: boolean) {
    setSelectedSourceIds((current) => {
      const visibleIds = visibleSources.map((source) => Number(source.id));
      if (checked) {
        return [...new Set([...current, ...visibleIds])];
      }
      return current.filter((item) => !visibleIds.includes(item));
    });
  }

  async function saveSource() {
    if (!selectedSource) {
      return;
    }
    setBusy("save");
    try {
      await browserFetch(`/admin/sources/${selectedSource.id}`, {
        method: "PATCH",
        json: {
          corpus_name: draft.corpusName,
          sensitivity_label: draft.sensitivityLabel,
          acl_group_names: draft.aclGroups
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean),
        },
      });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update source.");
    } finally {
      setBusy("");
    }
  }

  async function runSourceAction(action: "reindex" | "enrich") {
    if (!selectedSource) {
      return;
    }
    setBusy(action);
    try {
      await browserFetch(`/admin/sources/${selectedSource.id}/${action}`, {
        method: "POST",
        json: { force: true },
      });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action} source.`);
    } finally {
      setBusy("");
    }
  }

  async function applyBulkSourceSettings() {
    if (!selectedSourceIds.length || (bulkCorpusName === "__keep__" && bulkSensitivityLabel === "__keep__")) {
      return;
    }
    setBusy("bulk-save");
    try {
      await Promise.all(
        selectedSourceIds.map((sourceId) =>
          browserFetch(`/admin/sources/${sourceId}`, {
            method: "PATCH",
            json: {
              corpus_name: bulkCorpusName === "__keep__" ? undefined : bulkCorpusName === "__none__" ? "" : bulkCorpusName,
              sensitivity_label: bulkSensitivityLabel === "__keep__" ? undefined : bulkSensitivityLabel,
            },
          }),
        ),
      );
      setSelectedSourceIds([]);
      setBulkCorpusName("__keep__");
      setBulkSensitivityLabel("__keep__");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to bulk update sources.");
    } finally {
      setBusy("");
    }
  }

  async function runBulkSourceAction(action: "reindex" | "enrich") {
    if (!selectedSourceIds.length) {
      return;
    }
    setBusy(`bulk-${action}`);
    try {
      await Promise.all(
        selectedSourceIds.map((sourceId) =>
          browserFetch(`/admin/sources/${sourceId}/${action}`, {
            method: "POST",
            json: { force: true },
          }),
        ),
      );
      setSelectedSourceIds([]);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to bulk ${action} sources.`);
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="admin-route-page">
      <AdminSectionIntro
        eyebrow="Interactive"
        title="Sources"
        description="Inspect source-level status, corpus placement, ACL posture, and admin-triggered reindex/enrichment actions."
        badge={`${payload.sources.length} sources`}
      />
      {error ? <div className="error-banner">{error}</div> : null}
      <section className="admin-summary-cards">
        <SummaryMetricCard label="Visible Sources" value={formatCount(filteredCount, "source")} />
        <SummaryMetricCard label="Ready For Retrieval" value={formatCount(readyCount, "source")} tone="is-good" />
        <SummaryMetricCard label="Selected For Bulk Actions" value={formatCount(selectionCount, "source")} tone={selectionCount ? "is-warning" : ""} />
      </section>
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Filters And Saved Views</h2>
            <p>Reduce manual scanning by filtering the live source inventory and reusing operator views.</p>
          </div>
        </div>
        <div className="admin-filter-grid admin-filter-grid-5">
          <input value={draftFilters.query} onChange={(event) => setDraftFilters((current) => ({ ...current, query: event.target.value }))} placeholder="Search file, corpus, ACL group, or type" />
          <select value={draftFilters.status} onChange={(event) => setDraftFilters((current) => ({ ...current, status: event.target.value }))}>
            <option value="all">All statuses</option>
            <option value="indexed">indexed</option>
            <option value="embedded">embedded</option>
            <option value="processing">processing</option>
            <option value="queued">queued</option>
            <option value="failed">failed</option>
          </select>
          <select value={draftFilters.corpus} onChange={(event) => setDraftFilters((current) => ({ ...current, corpus: event.target.value }))}>
            <option value="all">All corpora</option>
            {corpusOptions.map((corpus) => (
              <option key={corpus} value={corpus.toLowerCase()}>{corpus}</option>
            ))}
            <option value="">No corpus</option>
          </select>
          <select value={draftFilters.sensitivity} onChange={(event) => setDraftFilters((current) => ({ ...current, sensitivity: event.target.value }))}>
            <option value="all">All sensitivity</option>
            <option value="public">public</option>
            <option value="internal">internal</option>
            <option value="confidential">confidential</option>
          </select>
          <select value={draftFilters.sort} onChange={(event) => setDraftFilters((current) => ({ ...current, sort: event.target.value }))}>
            <option value="name_asc">Name A-Z</option>
            <option value="name_desc">Name Z-A</option>
            <option value="size_desc">Largest first</option>
            <option value="size_asc">Smallest first</option>
            <option value="status">Status</option>
            <option value="corpus">Corpus</option>
          </select>
        </div>
        <div className="toolbar-inline">
          <span className={`badge ${hasPendingFilterChanges ? "is-warning" : ""}`}>{hasPendingFilterChanges ? "Unapplied filter changes" : `Showing ${filteredCount} of ${payload.sources.length} sources`}</span>
          <button type="button" className="button button-primary" disabled={!hasPendingFilterChanges} onClick={() => setFilters({ ...draftFilters })}>
            Apply filters
          </button>
          <button
            type="button"
            className="button button-secondary"
            onClick={() => {
              setDraftFilters({ ...defaultFilters });
              setFilters({ ...defaultFilters });
            }}
          >
            Reset filters
          </button>
        </div>
        <SavedViewsToolbar
          viewLabel="source"
          draftName={savedViewName}
          onDraftNameChange={setSavedViewName}
          onSave={saveCurrentView}
          savedViews={savedViews}
          onApply={applySavedView}
          onDelete={removeSavedView}
        />
      </section>
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Bulk Actions</h2>
            <p>Apply existing source administration workflows to multiple selected records at once.</p>
          </div>
          <span className="badge">{formatCount(selectionCount, "selected source")}</span>
        </div>
        <div className="admin-filter-grid admin-filter-grid-4">
          <select value={bulkCorpusName} onChange={(event) => setBulkCorpusName(event.target.value)}>
            <option value="__keep__">Keep current corpus</option>
            <option value="__none__">Remove corpus</option>
            {corpusOptions.map((corpus) => (
              <option key={`bulk-${corpus}`} value={corpus}>{corpus}</option>
            ))}
          </select>
          <select value={bulkSensitivityLabel} onChange={(event) => setBulkSensitivityLabel(event.target.value)}>
            <option value="__keep__">Keep current sensitivity</option>
            <option value="public">public</option>
            <option value="internal">internal</option>
            <option value="confidential">confidential</option>
          </select>
          <button type="button" className="button button-secondary" disabled={!visibleSources.length} onClick={() => toggleAllVisibleSources(true)}>
            Select filtered
          </button>
          <button type="button" className="button button-secondary" disabled={!selectionCount} onClick={() => setSelectedSourceIds([])}>
            Clear selection
          </button>
        </div>
        <div className="toolbar-inline">
          <button type="button" className="button button-primary" disabled={busy !== "" || !selectionCount || (bulkCorpusName === "__keep__" && bulkSensitivityLabel === "__keep__")} onClick={applyBulkSourceSettings}>
            {busy === "bulk-save" ? "Saving..." : "Apply bulk settings"}
          </button>
          <button type="button" className="button button-secondary" disabled={busy !== "" || !selectionCount} onClick={() => runBulkSourceAction("reindex")}>
            {busy === "bulk-reindex" ? "Queueing..." : "Bulk reindex"}
          </button>
          <button type="button" className="button button-secondary" disabled={busy !== "" || !selectionCount} onClick={() => runBulkSourceAction("enrich")}>
            {busy === "bulk-enrich" ? "Queueing..." : "Bulk enrich"}
          </button>
        </div>
      </section>
      <div className="results-grid">
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Source Inventory</h2>
              <p>Real source records with ingestion, enrichment, and access posture.</p>
            </div>
          </div>
          <div className="table-list">
            {isLoading ? <EmptyState title="Loading sources..." copy="Fetching source records, placement state, and ACL posture." icon="progress_activity" /> : visibleSources.length ? visibleSources.map((source) => (
              <article key={String(source.id)} className={`table-row ${selectedSourceIds.includes(Number(source.id)) ? "is-selected" : ""}`}>
                <div>
                  <label className="table-row-selector">
                    <input type="checkbox" checked={selectedSourceIds.includes(Number(source.id))} onChange={(event) => toggleSelectedSource(Number(source.id), event.target.checked)} />
                    <span className="sr-only">Select source {String(source.file_name)}</span>
                  </label>
                  <strong>{String(source.file_name)}</strong>
                  <span className="muted-copy">{`${String(source.corpus_name || "No corpus")} • ${String(source.sensitivity_label || "internal")}`}</span>
                </div>
                <div className="table-metrics">
                  <span className={`badge ${statusTone(source.ingestion_status)}`}>{String(source.ingestion_status || "unknown")}</span>
                  <span>{formatFileSize(source.file_size_bytes)}</span>
                  <button type="button" className="button button-secondary" onClick={() => setSelectedSourceId(String(source.id))}>
                    Inspect
                  </button>
                </div>
              </article>
            )) : <EmptyState title="No sources matched this view." copy={payload.sources.length ? "The source inventory is not empty, but nothing matches the applied filter set. Apply a different saved view or reset filters to reopen the broader inventory." : "This is normal on a clean install. User uploads and connector-backed sources will appear here once the first source record is created."} icon="upload_file" />}
          </div>
        </section>

        <section className="card">
          <div className="section-head">
            <div>
              <h2>{selectedSource ? String(selectedSource.file_name) : "Source detail"}</h2>
              <p>Placement, sensitivity, ACL groups, and admin actions for the selected source.</p>
            </div>
          </div>
          {!selectedSource ? <EmptyState title={isLoading ? "Loading source detail..." : "Select a source."} copy={isLoading ? "Waiting for source inventory before detail controls can render." : "Choose a source from the inventory to inspect and modify its admin-facing controls."} icon={isLoading ? "progress_activity" : "description"} /> : (
            <div className="page-stack">
              <div className="form-inline">
                <select value={draft.corpusName} onChange={(event) => setDraft((current) => ({ ...current, corpusName: event.target.value }))}>
                  <option value="">No corpus</option>
                  {corporaPayload.corpora.map((corpus) => (
                    <option key={String(corpus.name)} value={String(corpus.name)}>{String(corpus.name)}</option>
                  ))}
                </select>
                <select value={draft.sensitivityLabel} onChange={(event) => setDraft((current) => ({ ...current, sensitivityLabel: event.target.value }))}>
                  <option value="public">public</option>
                  <option value="internal">internal</option>
                  <option value="confidential">confidential</option>
                </select>
                <input value={draft.aclGroups} onChange={(event) => setDraft((current) => ({ ...current, aclGroups: event.target.value }))} placeholder="ACL groups, comma separated" />
              </div>
              <div className="toolbar-inline">
                <button type="button" className="button button-primary" onClick={saveSource} disabled={busy !== ""}>
                  {busy === "save" ? "Saving..." : "Save source settings"}
                </button>
                <button type="button" className="button button-secondary" onClick={() => runSourceAction("reindex")} disabled={busy !== ""}>
                  {busy === "reindex" ? "Queueing..." : "Reindex source"}
                </button>
                <button type="button" className="button button-secondary" onClick={() => runSourceAction("enrich")} disabled={busy !== ""}>
                  {busy === "enrich" ? "Queueing..." : "Re-run enrichment"}
                </button>
              </div>
              <JsonPanel
                value={{
                  source_id: selectedSource.id,
                  source_type: selectedSource.source_type,
                  mime_type: selectedSource.mime_type,
                  ingestion_status: selectedSource.ingestion_status,
                  enrichment_status: selectedSource.enrichment_status,
                  corpus_name: selectedSource.corpus_name,
                  acl_groups: selectedSource.acl_groups,
                  metadata: selectedSource.source_metadata_json,
                }}
              />
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export function JobsAdminPanel() {
  const searchParams = useSearchParams();
  const sourceIdParam = searchParams.get("sourceId");
  const defaultFilters = { query: "", kind: "all", status: "all", owner: "all", stage: "all", priority: "all", sourceType: "all", sort: "active_first" };
  const [payload, setPayload] = useState<{ ingestion_jobs: GenericMap[]; enrichment_jobs: GenericMap[]; queue_summary?: GenericMap; priority_requests?: GenericMap[] }>({ ingestion_jobs: [], enrichment_jobs: [], queue_summary: {}, priority_requests: [] });
  const [selectedJobKey, setSelectedJobKey] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [filters, setFilters] = useState({ ...defaultFilters });
  const [draftFilters, setDraftFilters] = useState({ ...defaultFilters });
  const [savedViews, setSavedViews] = useState<SavedViewEntry[]>([]);
  const [savedViewName, setSavedViewName] = useState("");
  const [busyAction, setBusyAction] = useState("");
  const [priorityValue, setPriorityValue] = useState("200");
  const [priorityReason, setPriorityReason] = useState("");
  const [reviewReason, setReviewReason] = useState("");
  const [priorityPreview, setPriorityPreview] = useState<GenericMap | null>(null);

  useEffect(() => {
    setSavedViews(readSavedAdminViews("jobs"));
  }, []);

  async function refresh() {
    setIsLoading(true);
    try {
      const next = await browserFetch<{ ingestion_jobs: GenericMap[]; enrichment_jobs: GenericMap[]; queue_summary?: GenericMap; priority_requests?: GenericMap[] }>("/admin/jobs");
      setPayload(next);
      setError("");
      const preferred = [...next.ingestion_jobs, ...next.enrichment_jobs].find((job) => String(job.source_id || "") === String(sourceIdParam || ""));
      setSelectedJobKey((current) => current || (preferred ? `${String(preferred.job_kind)}:${String(preferred.id)}` : `${String(next.ingestion_jobs?.[0]?.job_kind || next.enrichment_jobs?.[0]?.job_kind || "")}:${String(next.ingestion_jobs?.[0]?.id || next.enrichment_jobs?.[0]?.id || "")}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load job state.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [sourceIdParam]);

  const jobs = useMemo(
    () => [...payload.ingestion_jobs, ...payload.enrichment_jobs].sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || ""))),
    [payload],
  );
  const queueSummary = (payload.queue_summary || {}) as GenericMap;
  const priorityRequests = (payload.priority_requests || []) as GenericMap[];
  const visibleJobs = useMemo(() => {
    const filtered = jobs.filter((job) => {
      if (!matchesQuery(filters.query, [job.source_file_name, job.stage, job.stage_label, job.triggered_by, job.job_kind, job.corpus_name, job.owner_display_name, job.owner_email, job.source_type])) {
        return false;
      }
      if (filters.kind !== "all" && normalizeText(job.job_kind) !== filters.kind) {
        return false;
      }
      if (filters.status !== "all" && normalizeText(job.status) !== filters.status) {
        return false;
      }
      if (filters.owner !== "all" && normalizeText(job.owner_email || job.owner_display_name || job.owner_external_user_id || job.triggered_by) !== filters.owner) {
        return false;
      }
      if (filters.stage !== "all" && normalizeText(job.stage_label || job.stage) !== filters.stage) {
        return false;
      }
      if (filters.priority !== "all") {
        const label = normalizeText(formatPriorityLabel(job.priority));
        if (filters.priority !== label) {
          return false;
        }
      }
      if (filters.sourceType !== "all" && normalizeText(job.source_type) !== filters.sourceType) {
        return false;
      }
      return true;
    });
    return sortGenericMaps(filtered, filters.sort, {
      active_first: (left, right) => {
        const rankDiff = jobStatusRank(left.status) - jobStatusRank(right.status);
        if (rankDiff !== 0) {
          return rankDiff;
        }
        const queueDiff = toNumber(left.queue_position || 999999) - toNumber(right.queue_position || 999999);
        if (queueDiff !== 0) {
          return queueDiff;
        }
        return toTimestampValue(left.created_at) - toTimestampValue(right.created_at);
      },
      newest: (left, right) => toTimestampValue(right.created_at) - toTimestampValue(left.created_at),
      oldest: (left, right) => toTimestampValue(left.created_at) - toTimestampValue(right.created_at),
      duration_desc: (left, right) => toNumber(right.duration_seconds) - toNumber(left.duration_seconds),
      duration_asc: (left, right) => toNumber(left.duration_seconds) - toNumber(right.duration_seconds),
      source: (left, right) => String(left.source_file_name || "").localeCompare(String(right.source_file_name || "")),
    });
  }, [jobs, filters]);
  const ownerOptions = useMemo(
    () => Array.from(new Set(jobs.map((job) => normalizeText(job.owner_email || job.owner_display_name || job.owner_external_user_id || job.triggered_by)).filter(Boolean))).sort((left, right) => left.localeCompare(right)),
    [jobs],
  );
  const stageOptions = useMemo(
    () => Array.from(new Set(jobs.map((job) => normalizeText(job.stage_label || job.stage)).filter(Boolean))).sort((left, right) => left.localeCompare(right)),
    [jobs],
  );
  const sourceTypeOptions = useMemo(
    () => Array.from(new Set(jobs.map((job) => normalizeText(job.source_type)).filter(Boolean))).sort((left, right) => left.localeCompare(right)),
    [jobs],
  );
  const activeCount = visibleJobs.filter((job) => ["queued", "processing", "running", "pending"].includes(normalizeText(job.status))).length;
  const failedCount = visibleJobs.filter((job) => ["failed", "error"].includes(normalizeText(job.status))).length;
  const pendingPriorityCount = priorityRequests.filter((request) => ["submitted", "under_review"].includes(normalizeText(request.status))).length;
  const hasPendingFilterChanges = !filtersMatch(filters, draftFilters);
  const selectedJob = useMemo(
    () => visibleJobs.find((job) => `${String(job.job_kind)}:${String(job.id)}` === selectedJobKey) || null,
    [visibleJobs, selectedJobKey],
  );
  const selectedPriorityRequest = selectedJob?.priority_request && typeof selectedJob.priority_request === "object" ? selectedJob.priority_request as GenericMap : null;
  const selectedIngestionJob = selectedJob && normalizeText(selectedJob.job_kind) === "ingestion" ? selectedJob : null;

  useEffect(() => {
    setSelectedJobKey((current) => (current && visibleJobs.some((job) => `${String(job.job_kind)}:${String(job.id)}` === current) ? current : `${String(visibleJobs[0]?.job_kind || "")}:${String(visibleJobs[0]?.id || "")}`));
  }, [visibleJobs]);

  function applySavedView(entry: SavedViewEntry) {
    const nextFilters = {
      query: String(entry.filters.query || ""),
      kind: String(entry.filters.kind || "all"),
      status: String(entry.filters.status || "all"),
      owner: String(entry.filters.owner || "all"),
      stage: String(entry.filters.stage || "all"),
      priority: String(entry.filters.priority || "all"),
      sourceType: String(entry.filters.sourceType || "all"),
      sort: String(entry.filters.sort || "active_first"),
    };
    setDraftFilters(nextFilters);
    setFilters(nextFilters);
  }

  function saveCurrentView() {
    saveNamedView("jobs", savedViewName, draftFilters, setSavedViews);
    setSavedViewName("");
  }

  function removeSavedView(entry: SavedViewEntry) {
    deleteNamedView("jobs", entry.name, setSavedViews);
  }

  async function previewPriorityChange() {
    if (!selectedIngestionJob) {
      return;
    }
    setBusyAction("priority-preview");
    try {
      const next = await browserFetch<{ impact: GenericMap }>("/admin/jobs/ingestion/" + String(selectedIngestionJob.id) + "/priority", {
        method: "POST",
        json: {
          priority: Number(priorityValue),
          reason: priorityReason,
          preview_only: true,
        },
      });
      setPriorityPreview((next.impact || {}) as GenericMap);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to preview priority impact.");
    } finally {
      setBusyAction("");
    }
  }

  async function applyPriorityChange() {
    if (!selectedIngestionJob) {
      return;
    }
    setBusyAction("priority-apply");
    try {
      await browserFetch("/admin/jobs/ingestion/" + String(selectedIngestionJob.id) + "/priority", {
        method: "POST",
        json: {
          priority: Number(priorityValue),
          reason: priorityReason,
          preview_only: false,
        },
      });
      setPriorityPreview(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update job priority.");
    } finally {
      setBusyAction("");
    }
  }

  async function reviewPriorityRequest(decision: "under_review" | "approved" | "denied") {
    if (!selectedIngestionJob || !selectedPriorityRequest?.id) {
      return;
    }
    setBusyAction(`request-${decision}`);
    try {
      await browserFetch(`/admin/jobs/ingestion/${String(selectedIngestionJob.id)}/priority-request/${String(selectedPriorityRequest.id)}`, {
        method: "POST",
        json: {
          decision,
          reason: reviewReason,
        },
      });
      setReviewReason("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to review priority request.");
    } finally {
      setBusyAction("");
    }
  }

  async function runQueueControl(action: "pause" | "resume" | "cancel" | "requeue" | "retry") {
    if (!selectedIngestionJob) {
      return;
    }
    setBusyAction(`control-${action}`);
    try {
      await browserFetch(`/admin/jobs/ingestion/${String(selectedIngestionJob.id)}/control`, {
        method: "POST",
        json: {
          action,
          reason: reviewReason || priorityReason,
        },
      });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action} job.`);
    } finally {
      setBusyAction("");
    }
  }

  return (
    <div className="admin-route-page">
      <AdminSectionIntro
        eyebrow="Interactive"
        title="Jobs"
        description="Monitor ingestion and enrichment queues with real status, ETA, owner, governance controls, and related source context."
        badge={`${jobs.length} jobs`}
      />
      {error ? <div className="error-banner">{error}</div> : null}
      <section className="admin-summary-cards">
        <SummaryMetricCard label="Visible Jobs" value={formatCount(visibleJobs.length, "job")} />
        <SummaryMetricCard label="Active" value={formatCount(activeCount, "job")} tone="is-warning" />
        <SummaryMetricCard label="Failed" value={formatCount(failedCount, "job")} tone={failedCount ? "is-danger" : ""} />
        <SummaryMetricCard label="Priority Requests" value={formatCount(pendingPriorityCount, "request")} tone={pendingPriorityCount ? "is-warning" : ""} />
      </section>
      <section className="admin-summary-cards">
        <SummaryMetricCard label="Backlog" value={formatCount(queueSummary.backlog_count, "waiting job")} />
        <SummaryMetricCard label="Workers" value={formatCount(queueSummary.active_workers, "active worker")} />
        <SummaryMetricCard label="Oldest Wait" value={formatDuration(queueSummary.oldest_wait_seconds)} tone={toNumber(queueSummary.oldest_wait_seconds) > 600 ? "is-warning" : ""} />
        <SummaryMetricCard label="Avg Throughput" value={`${roundNumber(toNumber(queueSummary.average_chunks_per_minute), 1)} chunks/min`} />
      </section>
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Queue Views</h2>
            <p>Filter by wait state, owner, stage, and priority, then reuse those queue views without dropping into raw logs.</p>
          </div>
        </div>
        <div className="admin-filter-grid admin-filter-grid-5">
          <input value={draftFilters.query} onChange={(event) => setDraftFilters((current) => ({ ...current, query: event.target.value }))} placeholder="Search source, stage, corpus, owner, or source type" />
          <select value={draftFilters.kind} onChange={(event) => setDraftFilters((current) => ({ ...current, kind: event.target.value }))}>
            <option value="all">All job kinds</option>
            <option value="ingestion">ingestion</option>
            <option value="enrichment">enrichment</option>
          </select>
          <select value={draftFilters.status} onChange={(event) => setDraftFilters((current) => ({ ...current, status: event.target.value }))}>
            <option value="all">All statuses</option>
            <option value="queued">queued</option>
            <option value="processing">processing</option>
            <option value="running">running</option>
            <option value="paused">paused</option>
            <option value="completed">completed</option>
            <option value="failed">failed</option>
          </select>
          <select value={draftFilters.owner} onChange={(event) => setDraftFilters((current) => ({ ...current, owner: event.target.value }))}>
            <option value="all">All owners</option>
            {ownerOptions.map((owner) => (
              <option key={owner} value={owner}>{owner}</option>
            ))}
          </select>
          <select value={draftFilters.stage} onChange={(event) => setDraftFilters((current) => ({ ...current, stage: event.target.value }))}>
            <option value="all">All stages</option>
            {stageOptions.map((stage) => (
              <option key={stage} value={stage}>{stage}</option>
            ))}
          </select>
        </div>
        <div className="admin-filter-grid admin-filter-grid-5">
          <select value={draftFilters.priority} onChange={(event) => setDraftFilters((current) => ({ ...current, priority: event.target.value }))}>
            <option value="all">All priorities</option>
            <option value="urgent">urgent</option>
            <option value="high">high</option>
            <option value="elevated">elevated</option>
            <option value="normal">normal</option>
          </select>
          <select value={draftFilters.sourceType} onChange={(event) => setDraftFilters((current) => ({ ...current, sourceType: event.target.value }))}>
            <option value="all">All source types</option>
            {sourceTypeOptions.map((sourceType) => (
              <option key={sourceType} value={sourceType}>{sourceType}</option>
            ))}
          </select>
          <select value={draftFilters.sort} onChange={(event) => setDraftFilters((current) => ({ ...current, sort: event.target.value }))}>
            <option value="active_first">Active jobs first</option>
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="duration_desc">Longest duration</option>
            <option value="duration_asc">Shortest duration</option>
            <option value="source">Source name</option>
          </select>
        </div>
        <div className="toolbar-inline">
          <span className={`badge ${hasPendingFilterChanges ? "is-warning" : ""}`}>{hasPendingFilterChanges ? "Unapplied filter changes" : `Showing ${visibleJobs.length} of ${jobs.length} jobs`}</span>
          <button type="button" className="button button-primary" disabled={!hasPendingFilterChanges} onClick={() => setFilters({ ...draftFilters })}>
            Apply filters
          </button>
          <button
            type="button"
            className="button button-secondary"
            onClick={() => {
              setDraftFilters({ ...defaultFilters });
              setFilters({ ...defaultFilters });
            }}
          >
            Reset filters
          </button>
        </div>
        <SavedViewsToolbar
          viewLabel="job"
          draftName={savedViewName}
          onDraftNameChange={setSavedViewName}
          onSave={saveCurrentView}
          savedViews={savedViews}
          onApply={applySavedView}
          onDelete={removeSavedView}
        />
      </section>
      <div className="results-grid">
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Live Job Queue</h2>
              <p>Unified ingestion and enrichment queue with truthful stage, ETA, owner, and priority state.</p>
            </div>
          </div>
          <div className="table-list">
            {isLoading ? <EmptyState title="Loading jobs..." copy="Fetching ingestion and enrichment queue state from the admin control plane." icon="progress_activity" /> : visibleJobs.length ? visibleJobs.map((job) => (
              <article key={`${String(job.job_kind)}:${String(job.id)}`} className="table-row">
                <div>
                  <strong>{formatJobHeadline(job)}</strong>
                  <span className="muted-copy">{formatJobSubline(job)}</span>
                </div>
                <div className="table-metrics">
                  <span className={`badge ${statusTone(job.status)}`}>{titleCaseWords(job.status || "unknown")}</span>
                  <span>{formatPriorityLabel(job.priority)}</span>
                  <span>{formatJobTimingLabel(job)}</span>
                  <button type="button" className="button button-secondary" onClick={() => setSelectedJobKey(`${String(job.job_kind)}:${String(job.id)}`)}>
                    Open detail
                  </button>
                </div>
              </article>
            )) : <EmptyState title="No jobs matched this view." copy={jobs.length ? "The queue is not empty, but nothing matches the applied filters. Apply a different saved view or reset filters to reopen the full queue." : "This is normal on a clean system. The first upload, reindex, or enrichment run will appear here as soon as the platform has indexing work to track."} icon="work_history" />}
          </div>
        </section>

        <section className="card">
          <div className="section-head">
            <div>
              <h2>{selectedJob ? `Job #${String(selectedJob.id)}` : "Job detail"}</h2>
              <p>Execution timing, failure context, and source/corpus cross-links for the selected job.</p>
            </div>
          </div>
          {!selectedJob ? <EmptyState title={isLoading ? "Loading job detail..." : "Select a job."} copy={isLoading ? "Waiting for queue data before job detail can render." : jobs.length ? "Choose a job from the queue to inspect timing, failure context, and source relationships." : "No job detail is available yet because the queue is still empty."} icon={isLoading ? "progress_activity" : "article"} /> : (
            <div className="page-stack">
              <article className="table-row">
                <div>
                  <strong>{buildJobOperatorSummary(selectedJob)}</strong>
                  <span className="muted-copy">{selectedJob.error_message ? `Failure reason: ${String(selectedJob.error_message)}` : normalizeText(selectedJob.status) === "completed" ? `${formatJobSourceName(selectedJob)} completed indexing successfully.` : String(selectedJob.queue_delay_message || "This view explains the current job state in plain language before the raw technical payload.")}</span>
                </div>
                <div className="table-metrics">
                  <span className={`badge ${statusTone(selectedJob.status)}`}>{titleCaseWords(selectedJob.status || "unknown")}</span>
                  <span>{selectedJob.corpus_name ? `Corpus: ${String(selectedJob.corpus_name)}` : "No corpus linked yet"}</span>
                  <span>{isActiveJobStatus(selectedJob.status) ? formatEtaWindow(selectedJob.eta_window) : formatDuration(selectedJob.duration_seconds)}</span>
                </div>
              </article>
              {selectedIngestionJob ? (
                <section className="card">
                  <div className="section-head">
                    <div>
                      <h2>Queue Governance</h2>
                      <p>Raise or lower waiting-job priority, review user escalation requests, and apply bounded queue controls.</p>
                    </div>
                  </div>
                  <div className="page-stack">
                    <div className="admin-summary-cards">
                      <SummaryMetricCard label="Owner" value={formatJobOwner(selectedIngestionJob)} />
                      <SummaryMetricCard label="Priority" value={formatPriorityLabel(selectedIngestionJob.priority)} tone={toNumber(selectedIngestionJob.priority) >= 150 ? "is-warning" : ""} />
                      <SummaryMetricCard label="Queue Position" value={formatQueuePosition(selectedIngestionJob)} />
                      <SummaryMetricCard label="ETA" value={formatEtaWindow(selectedIngestionJob.eta_window)} />
                    </div>
                    <div className="admin-filter-grid admin-filter-grid-3">
                      <select value={priorityValue} onChange={(event) => setPriorityValue(event.target.value)}>
                        <option value="200">Urgent</option>
                        <option value="160">High</option>
                        <option value="120">Elevated</option>
                        <option value="100">Normal</option>
                        <option value="80">Lower priority</option>
                      </select>
                      <input value={priorityReason} onChange={(event) => setPriorityReason(event.target.value)} placeholder="Reason for reprioritization or queue action" />
                      <div className="toolbar-inline">
                        <button type="button" className="button button-secondary" disabled={!selectedIngestionJob || busyAction !== ""} onClick={previewPriorityChange}>
                          {busyAction === "priority-preview" ? "Previewing..." : "Preview impact"}
                        </button>
                        <button type="button" className="button button-primary" disabled={!selectedIngestionJob || busyAction !== ""} onClick={applyPriorityChange}>
                          {busyAction === "priority-apply" ? "Saving..." : "Update priority"}
                        </button>
                      </div>
                    </div>
                    {priorityPreview ? <JsonPanel value={priorityPreview} /> : null}
                    <div className="toolbar-inline">
                      <button type="button" className="button button-secondary" disabled={!selectedIngestionJob || busyAction !== ""} onClick={() => runQueueControl("pause")}>Pause</button>
                      <button type="button" className="button button-secondary" disabled={!selectedIngestionJob || busyAction !== ""} onClick={() => runQueueControl("resume")}>Resume</button>
                      <button type="button" className="button button-secondary" disabled={!selectedIngestionJob || busyAction !== ""} onClick={() => runQueueControl("cancel")}>Cancel</button>
                      <button type="button" className="button button-secondary" disabled={!selectedIngestionJob || busyAction !== ""} onClick={() => runQueueControl("requeue")}>Requeue</button>
                      <button type="button" className="button button-secondary" disabled={!selectedIngestionJob || busyAction !== ""} onClick={() => runQueueControl("retry")}>Retry</button>
                    </div>
                    {selectedPriorityRequest ? (
                      <div className="page-stack">
                        <article className="table-row">
                          <div>
                            <strong>{`Priority request #${String(selectedPriorityRequest.id)}`}</strong>
                            <span className="muted-copy">{`${titleCaseWords(selectedPriorityRequest.status || "submitted")} • Requested priority ${String(selectedPriorityRequest.requested_priority || "")}`}</span>
                          </div>
                          <div className="table-metrics">
                            <span>{String(selectedPriorityRequest.reason || "No user reason provided.")}</span>
                          </div>
                        </article>
                        <div className="admin-filter-grid admin-filter-grid-3">
                          <input value={reviewReason} onChange={(event) => setReviewReason(event.target.value)} placeholder="Review note for the requester and audit trail" />
                          <button type="button" className="button button-secondary" disabled={busyAction !== ""} onClick={() => reviewPriorityRequest("under_review")}>Mark under review</button>
                          <div className="toolbar-inline">
                            <button type="button" className="button button-primary" disabled={busyAction !== ""} onClick={() => reviewPriorityRequest("approved")}>Approve request</button>
                            <button type="button" className="button button-secondary" disabled={busyAction !== ""} onClick={() => reviewPriorityRequest("denied")}>Deny request</button>
                          </div>
                        </div>
                      </div>
                    ) : null}
                  </div>
                </section>
              ) : null}
              <div className="toolbar-inline">
                {selectedJob.source_id ? <Link href={`/console/admin/sources?sourceId=${String(selectedJob.source_id)}`} className="admin-inline-link">Open source</Link> : null}
                {selectedJob.corpus_name ? <Link href="/console/admin/corpora" className="admin-inline-link">Open corpora</Link> : null}
                <Link href="/console/admin/audit-log" className="admin-inline-link">Open queue audit</Link>
              </div>
              <section className="card">
                <div className="section-head">
                  <div>
                    <h2>Technical payload</h2>
                    <p>Raw job fields for engineering follow-up when the plain-language summary is not enough.</p>
                  </div>
                </div>
                <JsonPanel
                  value={{
                    id: selectedJob.id,
                    kind: selectedJob.job_kind,
                    status: selectedJob.status,
                    stage: selectedJob.stage,
                    triggered_by: selectedJob.triggered_by,
                    duration: formatDuration(selectedJob.duration_seconds),
                    created_at: selectedJob.created_at,
                    started_at: selectedJob.started_at,
                    completed_at: selectedJob.completed_at,
                    queue_position: selectedJob.queue_position,
                    eta_window: selectedJob.eta_window,
                    wait_window: selectedJob.wait_window,
                    priority: selectedJob.priority,
                    priority_request: selectedJob.priority_request,
                    owner: {
                      display_name: selectedJob.owner_display_name,
                      email: selectedJob.owner_email,
                      external_user_id: selectedJob.owner_external_user_id,
                    },
                    source_id: selectedJob.source_id,
                    source_file_name: selectedJob.source_file_name,
                    corpus_name: selectedJob.corpus_name,
                    error_message: selectedJob.error_message,
                    job_metadata_json: selectedJob.job_metadata_json,
                  }}
                />
              </section>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export function ProfilesAdminPanel() {
  const [payload, setPayload] = useState<{ profiles: GenericMap[] }>({ profiles: [] });
  const [history, setHistory] = useState<{ events: GenericMap[] }>({ events: [] });
  const [error, setError] = useState("");
  const [activating, setActivating] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  async function refresh() {
    setIsLoading(true);
    try {
      const [profiles, audit] = await Promise.all([
        browserFetch<{ profiles: GenericMap[] }>("/admin/profiles"),
        browserFetch<{ events: GenericMap[] }>("/admin/audit-log?action=profile.activate"),
      ]);
      setPayload(profiles);
      setHistory(audit);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load profiles.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function activate(profileType: string, profileName: string) {
    const key = `${profileType}:${profileName}`;
    setActivating(key);
    try {
      await browserFetch("/admin/profiles/active", {
        method: "POST",
        json: { profile_type: profileType, profile_name: profileName },
      });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to activate profile.");
    } finally {
      setActivating("");
    }
  }

  return (
    <div className="admin-route-page">
      <AdminSectionIntro
        eyebrow="Interactive"
        title="Profiles"
        description="Review live profile inventory, activate current profiles, and inspect activation history from the audit foundation."
        badge={`${payload.profiles.length} profiles`}
      />
      {error ? <div className="error-banner">{error}</div> : null}
      <div className="results-grid">
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Profile Registry</h2>
              <p>Embedding, retrieval, reranker, and LLM profiles currently known to the control plane.</p>
            </div>
          </div>
          <div className="table-list">
            {isLoading ? <EmptyState title="Loading profiles..." copy="Fetching registered profile metadata and current active selections." icon="progress_activity" /> : payload.profiles.length ? payload.profiles.map((profile) => {
              const profileType = String(profile.profile_type);
              const profileName = String(profile.name);
              const key = `${profileType}:${profileName}`;
              return (
                <article key={key} className="table-row">
                  <div>
                    <strong>{`${profileType} / ${profileName}`}</strong>
                    <span className="muted-copy">{profile.is_active ? "Active profile" : "Available for activation"}</span>
                  </div>
                  <div className="table-metrics">
                    <span className={`badge ${statusTone(profile.is_active ? "active" : "available")}`}>{profile.is_active ? "Active" : "Available"}</span>
                    <button
                      type="button"
                      className="button button-secondary"
                      disabled={Boolean(profile.is_active) || activating === key}
                      onClick={() => activate(profileType, profileName)}
                    >
                      {profile.is_active ? "Active" : activating === key ? "Activating..." : "Activate"}
                    </button>
                  </div>
                </article>
              );
            }) : <EmptyState title="No profiles found." copy="Profile metadata will appear here once the backend registry is seeded." />}
          </div>
        </section>

        <section className="card">
          <div className="section-head">
            <div>
              <h2>Activation History</h2>
              <p>Audit-backed profile changes rather than inferred active state alone.</p>
            </div>
          </div>
          <div className="table-list">
            {isLoading ? <EmptyState title="Loading activation history..." copy="Fetching prior profile activation events from the audit foundation." icon="progress_activity" /> : history.events.length ? history.events.map((event) => (
              <article key={String(event.id)} className="table-row">
                <div>
                  <strong>{String(event.resource_name || event.profile_name || "Profile change")}</strong>
                  <span className="muted-copy">{`${String(event.actor_email || event.actor_external_user_id || "unknown actor")} • ${String((event.after_json as GenericMap | undefined)?.profile_name || "")}`}</span>
                </div>
                <div className="table-metrics">
                  <span className={`badge ${statusTone(event.outcome)}`}>{String(event.outcome || "completed")}</span>
                  <span>{formatTimestamp(event.created_at)}</span>
                </div>
              </article>
            )) : <EmptyState title="No activation history yet." copy="Profile activation events will appear here once operators begin switching profiles." />}
          </div>
        </section>
      </div>
    </div>
  );
}

export function EvalsAdminPanel() {
  const [reports, setReports] = useState<{ reports: GenericMap[] }>({ reports: [] });
  const [history, setHistory] = useState<{ events: GenericMap[] }>({ events: [] });
  const [running, setRunning] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [compareLeftKind, setCompareLeftKind] = useState("");
  const [compareRightKind, setCompareRightKind] = useState("");

  async function refresh() {
    setIsLoading(true);
    try {
      const [reportPayload, historyPayload] = await Promise.all([
        browserFetch<{ reports: GenericMap[] }>("/admin/eval/reports"),
        browserFetch<{ events: GenericMap[] }>("/admin/audit-log?action=eval.run"),
      ]);
      setReports(reportPayload);
      setHistory(historyPayload);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load eval reports.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function run(kind: string) {
    setRunning(kind);
    try {
      await browserFetch("/admin/eval/run", { method: "POST", json: { report_kind: kind } });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run eval.");
    } finally {
      setRunning("");
    }
  }

  const existingReports = reports.reports.filter((report) => Boolean(report.exists));
  const compareLeft = existingReports.find((report) => String(report.kind) === compareLeftKind) || existingReports[0] || null;
  const compareRight = existingReports.find((report) => String(report.kind) === compareRightKind) || existingReports[1] || existingReports[0] || null;
  const compareLeftSummary = (compareLeft?.summary || {}) as GenericMap;
  const compareRightSummary = (compareRight?.summary || {}) as GenericMap;
  const passRateDelta = compareLeft && compareRight ? roundNumber(toNumber(compareLeftSummary.pass_rate_percent) - toNumber(compareRightSummary.pass_rate_percent), 2) : null;

  useEffect(() => {
    if (!existingReports.length) {
      setCompareLeftKind("");
      setCompareRightKind("");
      return;
    }
    setCompareLeftKind((current) => current || String(existingReports[0].kind));
    setCompareRightKind((current) => current || String(existingReports[1]?.kind || existingReports[0].kind));
  }, [existingReports]);

  return (
    <div className="admin-route-page">
      <AdminSectionIntro
        eyebrow="Interactive"
        title="Evals"
        description="Run retrieval checks, review report state, and compare the currently available report inventory without leaving the admin console."
        badge={`${reports.reports.length} report slots`}
      />
      {error ? <div className="error-banner">{error}</div> : null}
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Run Eval Packs</h2>
            <p>Trigger live retrieval and benchmark evaluations from the control plane.</p>
          </div>
          <div className="toolbar-inline">
            <button className="button button-secondary" type="button" onClick={() => run("retrieval")} disabled={running !== ""}>
              {running === "retrieval" ? "Running..." : "Run Retrieval Eval"}
            </button>
            <button className="button button-primary" type="button" onClick={() => run("benchmark")} disabled={running !== ""}>
              {running === "benchmark" ? "Running..." : "Run Benchmark"}
            </button>
          </div>
        </div>
      </section>
      <div className="results-grid">
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Report Inventory</h2>
              <p>Truthful visibility into present and missing report artifacts.</p>
            </div>
            <span className="badge">{formatCount(existingReports.length, "available report")}</span>
          </div>
          <div className="table-list">
            {isLoading ? <EmptyState title="Loading eval state..." copy="Fetching known eval report slots and recent run history." icon="progress_activity" /> : reports.reports.length ? reports.reports.map((report) => (
              <article key={String(report.kind)} className="table-row">
                <div>
                  <strong>{String(report.kind)}</strong>
                  <span className="muted-copy">{String(report.path || "No report path")}</span>
                </div>
                <div className="table-metrics">
                  <span className={`badge ${statusTone(report.exists ? "available" : "missing")}`}>{report.exists ? "Available" : "Missing"}</span>
                  <span>{report.exists ? `${String((report.summary as GenericMap | undefined)?.pass_rate_percent ?? "-")}% pass` : "Run pending"}</span>
                </div>
              </article>
            )) : <EmptyState title="No report metadata available." copy="This is normal on a first run. Trigger a retrieval or benchmark eval above to create the first report artifact and populate this page." icon="fact_check" />}
          </div>
        </section>

        <section className="card">
          <div className="section-head">
            <div>
              <h2>Compare Reports</h2>
              <p>Quick operator comparison across the currently available report slots.</p>
            </div>
          </div>
          {existingReports.length ? (
            <div className="page-stack">
              <div className="admin-filter-grid admin-filter-grid-2">
                <select value={compareLeftKind} onChange={(event) => setCompareLeftKind(event.target.value)}>
                  {existingReports.map((report) => (
                    <option key={`left-${String(report.kind)}`} value={String(report.kind)}>{String(report.kind)}</option>
                  ))}
                </select>
                <select value={compareRightKind} onChange={(event) => setCompareRightKind(event.target.value)}>
                  {existingReports.map((report) => (
                    <option key={`right-${String(report.kind)}`} value={String(report.kind)}>{String(report.kind)}</option>
                  ))}
                </select>
              </div>
              <section className="admin-summary-cards">
                <SummaryMetricCard label={`${String(compareLeft?.kind || "Left")} pass rate`} value={`${String(compareLeftSummary.pass_rate_percent ?? "-")}%`} tone="is-good" />
                <SummaryMetricCard label={`${String(compareRight?.kind || "Right")} pass rate`} value={`${String(compareRightSummary.pass_rate_percent ?? "-")}%`} tone="is-good" />
                <SummaryMetricCard label="Pass-rate delta" value={passRateDelta === null ? "n/a" : `${passRateDelta > 0 ? "+" : ""}${passRateDelta}%`} tone={passRateDelta && passRateDelta < 0 ? "is-danger" : "is-warning"} />
              </section>
              <div className="results-grid">
                {[compareLeft, compareRight].map((report, index) => {
                  const summary = (report?.summary || {}) as GenericMap;
                  const metadata = (report?.report_metadata || {}) as GenericMap;
                  return (
                    <section key={`${String(report?.kind || "report")}-${index}`} className="card admin-compare-card">
                      <div className="section-head">
                        <div>
                          <h2>{String(report?.kind || `Report ${index + 1}`)}</h2>
                          <p>{String(report?.path || "No report path")}</p>
                        </div>
                        <span className={`badge ${statusTone(report?.exists ? "available" : "missing")}`}>{report?.exists ? "Available" : "Missing"}</span>
                      </div>
                      <div className="table-list">
                        <article className="table-row">
                          <div>
                            <strong>Coverage</strong>
                            <span className="muted-copy">{`${String(summary.passed ?? "-")} passed • ${String(summary.failed ?? "-")} failed`}</span>
                          </div>
                          <div className="table-metrics">
                            <span>{String(summary.total ?? "-")} total</span>
                            <span>{`${String(summary.pass_rate_percent ?? "-")}% pass`}</span>
                          </div>
                        </article>
                        <article className="table-row">
                          <div>
                            <strong>Evaluated Modes</strong>
                            <span className="muted-copy">{Array.isArray(summary.evaluated_modes) && summary.evaluated_modes.length ? (summary.evaluated_modes as string[]).join(", ") : "No mode metadata"}</span>
                          </div>
                        </article>
                        <article className="table-row">
                          <div>
                            <strong>Active Profiles Snapshot</strong>
                            <span className="muted-copy">{JSON.stringify(metadata.active_profiles || {}, null, 0)}</span>
                          </div>
                        </article>
                      </div>
                    </section>
                  );
                })}
              </div>
            </div>
          ) : (
            <EmptyState title="No reports available for comparison yet." copy="Run the first eval so the operator comparison surface has report data to work with." icon="compare_arrows" />
          )}
        </section>

        <section className="card">
          <div className="section-head">
            <div>
              <h2>Eval Run History</h2>
              <p>Audit-backed visibility into recent eval executions.</p>
            </div>
          </div>
          <div className="table-list">
            {isLoading ? <EmptyState title="Loading eval history..." copy="Fetching audit-backed eval execution history." icon="progress_activity" /> : history.events.length ? history.events.map((event) => (
              <article key={String(event.id)} className="table-row">
                <div>
                  <strong>{String(event.resource_name || event.action)}</strong>
                  <span className="muted-copy">{String(event.actor_email || event.actor_external_user_id || "unknown actor")}</span>
                </div>
                <div className="table-metrics">
                  <span className={`badge ${statusTone(event.outcome)}`}>{String(event.outcome || "completed")}</span>
                  <span>{formatTimestamp(event.created_at)}</span>
                </div>
              </article>
            )) : <EmptyState title="No eval runs recorded yet." copy="This is normal on a clean system. Run the first eval above to establish a baseline and confirm retrieval quality." icon="query_stats" />}
          </div>
        </section>
      </div>
    </div>
  );
}

export function TracesAdminPanel() {
  const defaultFilters = { query: "", mode: "all", fallback: "all", sort: "newest" };
  const [payload, setPayload] = useState<{ traces: GenericMap[]; active_profiles?: GenericMap; retrieval_settings?: GenericMap }>({ traces: [] });
  const [selectedTraceId, setSelectedTraceId] = useState("");
  const [traceDetail, setTraceDetail] = useState<GenericMap | null>(null);
  const [debugQuestion, setDebugQuestion] = useState("");
  const [debugMode, setDebugMode] = useState("hybrid");
  const [debugK, setDebugK] = useState("5");
  const [debugResult, setDebugResult] = useState<GenericMap | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [filters, setFilters] = useState({ ...defaultFilters });
  const [draftFilters, setDraftFilters] = useState({ ...defaultFilters });
  const [savedViews, setSavedViews] = useState<SavedViewEntry[]>([]);
  const [savedViewName, setSavedViewName] = useState("");

  useEffect(() => {
    setSavedViews(readSavedAdminViews("traces"));
  }, []);

  async function refresh() {
    setIsLoading(true);
    try {
      const next = await browserFetch<{ traces: GenericMap[]; active_profiles?: GenericMap; retrieval_settings?: GenericMap }>("/admin/traces");
      setPayload(next);
      setError("");
      setSelectedTraceId((current) => current || String(next.traces?.[0]?.id || ""));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load traces.");
      setPayload({ traces: [] });
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const visibleTraces = useMemo(() => {
    const filtered = payload.traces.filter((trace) => {
      if (!matchesQuery(filters.query, [trace.question, trace.request_id, trace.retrieval_path, trace.resolved_mode, trace.fallback_reason])) {
        return false;
      }
      if (filters.mode !== "all" && normalizeText(trace.retrieval_path || trace.resolved_mode) !== filters.mode) {
        return false;
      }
      if (filters.fallback === "fallback_only" && !trace.has_fallback) {
        return false;
      }
      if (filters.fallback === "direct_only" && trace.has_fallback) {
        return false;
      }
      return true;
    });
    return sortGenericMaps(filtered, filters.sort, {
      newest: (left, right) => toTimestampValue(right.created_at) - toTimestampValue(left.created_at),
      oldest: (left, right) => toTimestampValue(left.created_at) - toTimestampValue(right.created_at),
      latency_desc: (left, right) => toNumber(right.total_latency_ms || right.search_latency_ms) - toNumber(left.total_latency_ms || left.search_latency_ms),
      latency_asc: (left, right) => toNumber(left.total_latency_ms || left.search_latency_ms) - toNumber(right.total_latency_ms || right.search_latency_ms),
    });
  }, [payload.traces, filters]);

  const fallbackCount = visibleTraces.filter((trace) => Boolean(trace.has_fallback)).length;
  const avgLatency = visibleTraces.length
    ? roundNumber(visibleTraces.reduce((total, trace) => total + toNumber(trace.total_latency_ms || trace.search_latency_ms), 0) / visibleTraces.length, 1)
    : 0;
  const hasPendingFilterChanges = !filtersMatch(filters, draftFilters);
  const groupedTraces = useMemo(() => {
    const groups: Array<{
      key: string;
      question: string;
      traces: GenericMap[];
      selected: GenericMap;
      latestCreatedAt: number;
    }> = [];
    for (const trace of visibleTraces) {
      const normalizedQuestion = normalizeText(trace.question);
      const createdAt = toTimestampValue(trace.created_at);
      const existing = groups.find(
        (group) =>
          group.key === normalizedQuestion &&
          Math.abs(group.latestCreatedAt - createdAt) <= 2 * 60 * 1000,
      );
      if (!existing) {
        groups.push({
          key: normalizedQuestion,
          question: String(trace.question || ""),
          traces: [trace],
          selected: trace,
          latestCreatedAt: createdAt,
        });
        continue;
      }
      existing.traces.push(trace);
      if (createdAt > existing.latestCreatedAt) {
        existing.latestCreatedAt = createdAt;
      }
      if (!existing.selected.answer_path && trace.answer_path) {
        existing.selected = trace;
      } else if (existing.selected.answer_path === trace.answer_path && createdAt > toTimestampValue(existing.selected.created_at)) {
        existing.selected = trace;
      }
    }
    return groups.map((group) => ({
      ...group,
      traces: [...group.traces].sort((left, right) => toTimestampValue(right.created_at) - toTimestampValue(left.created_at)),
    }));
  }, [visibleTraces]);

  useEffect(() => {
    setSelectedTraceId((current) => (current && groupedTraces.some((group) => String(group.selected.id) === current) ? current : String(groupedTraces[0]?.selected.id || "")));
  }, [groupedTraces]);

  function applySavedView(entry: SavedViewEntry) {
    const nextFilters = {
      query: String(entry.filters.query || ""),
      mode: String(entry.filters.mode || "all"),
      fallback: String(entry.filters.fallback || "all"),
      sort: String(entry.filters.sort || "newest"),
    };
    setDraftFilters(nextFilters);
    setFilters(nextFilters);
  }

  function saveCurrentView() {
    saveNamedView("traces", savedViewName, draftFilters, setSavedViews);
    setSavedViewName("");
  }

  function removeSavedView(entry: SavedViewEntry) {
    deleteNamedView("traces", entry.name, setSavedViews);
  }

  useEffect(() => {
    if (!selectedTraceId) {
      setTraceDetail(null);
      return;
    }
    browserFetch<{ trace: GenericMap }>(`/admin/traces/${selectedTraceId}`)
      .then((value) => setTraceDetail(value.trace))
      .catch(() => setTraceDetail(null));
  }, [selectedTraceId]);

  async function runQueryDebug() {
    setBusy(true);
    try {
      const next = await browserFetch<GenericMap>("/admin/traces/query-debug", {
        method: "POST",
        json: {
          question: debugQuestion,
          mode: debugMode,
          k: Number(debugK || 5),
        },
      });
      setDebugResult(next);
      setError("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run query debug.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="admin-route-page">
      <AdminSectionIntro
        eyebrow="Interactive"
        title="Traces"
        description="Inspect stored retrieval traces and run live query-debug experiments from the same routed operator page."
        badge={`${payload.traces.length} traces`}
      />
      {error ? <div className="error-banner">{error}</div> : null}
      <section className="admin-summary-cards">
        <SummaryMetricCard label="Visible Traces" value={formatCount(visibleTraces.length, "trace")} />
        <SummaryMetricCard label="Fallbacks" value={formatCount(fallbackCount, "trace")} tone={fallbackCount ? "is-warning" : ""} />
        <SummaryMetricCard label="Average Latency" value={visibleTraces.length ? `${avgLatency} ms` : "n/a"} />
      </section>
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Query Debug</h2>
            <p>Run an isolated retrieval trace without changing the active production defaults.</p>
          </div>
        </div>
        <div className="form-inline">
          <input value={debugQuestion} onChange={(event) => setDebugQuestion(event.target.value)} placeholder="Question to debug" />
          <select value={debugMode} onChange={(event) => setDebugMode(event.target.value)}>
            <option value="hybrid">hybrid</option>
            <option value="keyword">keyword</option>
            <option value="vector">vector</option>
            <option value="graph_hybrid">graph_hybrid</option>
          </select>
          <input value={debugK} onChange={(event) => setDebugK(event.target.value)} placeholder="Top K" />
        </div>
        <div className="toolbar-inline">
          <button type="button" className="button button-primary" disabled={busy || !debugQuestion.trim()} onClick={runQueryDebug}>
            {busy ? "Running..." : "Run query debug"}
          </button>
        </div>
        {debugResult ? <JsonPanel value={debugResult} /> : null}
      </section>
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Trace Views</h2>
            <p>Reuse filtered retrieval-debug views for fallback-heavy or high-latency investigations.</p>
          </div>
        </div>
        <div className="admin-filter-grid admin-filter-grid-4">
          <input value={draftFilters.query} onChange={(event) => setDraftFilters((current) => ({ ...current, query: event.target.value }))} placeholder="Search question, path, or fallback reason" />
          <select value={draftFilters.mode} onChange={(event) => setDraftFilters((current) => ({ ...current, mode: event.target.value }))}>
            <option value="all">All modes</option>
            <option value="hybrid">hybrid</option>
            <option value="keyword">keyword</option>
            <option value="vector">vector</option>
            <option value="graph_hybrid">graph_hybrid</option>
            <option value="full">full</option>
          </select>
          <select value={draftFilters.fallback} onChange={(event) => setDraftFilters((current) => ({ ...current, fallback: event.target.value }))}>
            <option value="all">All traces</option>
            <option value="fallback_only">Fallback only</option>
            <option value="direct_only">Direct only</option>
          </select>
          <select value={draftFilters.sort} onChange={(event) => setDraftFilters((current) => ({ ...current, sort: event.target.value }))}>
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="latency_desc">Latency high to low</option>
            <option value="latency_asc">Latency low to high</option>
          </select>
        </div>
        <div className="toolbar-inline">
          <span className={`badge ${hasPendingFilterChanges ? "is-warning" : ""}`}>{hasPendingFilterChanges ? "Unapplied filter changes" : `Showing ${visibleTraces.length} of ${payload.traces.length} traces`}</span>
          <button type="button" className="button button-primary" disabled={!hasPendingFilterChanges} onClick={() => setFilters({ ...draftFilters })}>
            Apply filters
          </button>
          <button
            type="button"
            className="button button-secondary"
            onClick={() => {
              setDraftFilters({ ...defaultFilters });
              setFilters({ ...defaultFilters });
            }}
          >
            Reset filters
          </button>
        </div>
        <SavedViewsToolbar
          viewLabel="trace"
          draftName={savedViewName}
          onDraftNameChange={setSavedViewName}
          onSave={saveCurrentView}
          savedViews={savedViews}
          onApply={applySavedView}
          onDelete={removeSavedView}
        />
      </section>
      <div className="results-grid">
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Recent Retrieval Traces**</h2>
              <p>Stored traces with readable question labels, fallback context, and latency details.</p>
            </div>
          </div>
          <div className="table-list">
            {isLoading ? <EmptyState title="Loading traces..." copy="Fetching stored retrieval traces and the latest debug-ready request records." icon="progress_activity" /> : groupedTraces.length ? groupedTraces.map((group) => (
              <article key={`${group.key}-${String(group.selected.id)}`} className="table-row">
                <div>
                  <strong>
                    <Link href={traceLinkTarget(group.selected)} className="admin-inline-link">
                      {questionPreview(group.question)}
                    </Link>
                  </strong>
                  <span className="muted-copy">{String(group.selected.retrieval_path || group.selected.resolved_mode || "hybrid")}</span>
                </div>
                <div className="table-metrics">
                  <span className={`badge ${statusTone(group.traces.some((trace) => trace.has_fallback) ? "warning" : "available")}`}>{group.traces.some((trace) => trace.has_fallback) ? "Fallback" : "Direct"}</span>
                  <span>{String(group.selected.total_latency_ms || group.selected.search_latency_ms || "-")} ms</span>
                  <button type="button" className="button button-secondary" onClick={() => setSelectedTraceId(String(group.selected.id))}>
                    Inspect
                  </button>
                </div>
              </article>
            )) : <EmptyState title="No traces matched this view." copy={payload.traces.length ? "Stored traces exist, but nothing matches the current filters. Reset filters or apply a different saved view." : "This is normal on a clean system. Ask a question in the user workspace or run query debug above to generate the first stored trace."} icon="timeline" />}
          </div>
          {groupedTraces.length ? (
            <div className="toolbar-inline" style={{ justifyContent: "flex-end" }}>
              <span className="muted-copy"><strong>**</strong> answer retrieval + <strong>*</strong> preview retrieval</span>
            </div>
          ) : null}
        </section>

        <section className="card">
          <div className="section-head">
            <div>
              <h2>{traceDetail ? `Trace #${String(traceDetail.id)}` : "Trace detail"}</h2>
              <p>Stored debug detail for the selected retrieval request.</p>
            </div>
            {traceDetail?.request_id ? <Link href={`/console/admin/audit-log`} className="admin-inline-link">Open audit log</Link> : null}
          </div>
          {!traceDetail ? <EmptyState title={isLoading ? "Loading trace detail..." : "Select a trace."} copy={isLoading ? "Waiting for the trace inventory before detail can render." : payload.traces.length ? "Choose a trace from the list to inspect the full stored retrieval payload." : "No trace detail is available yet because no retrieval traffic has been recorded."} icon={isLoading ? "progress_activity" : "article"} /> : <JsonPanel value={traceDetail} />}
        </section>
      </div>
    </div>
  );
}

export function PoliciesAdminPanel() {
  const [payload, setPayload] = useState<GenericMap | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    browserFetch<GenericMap>("/admin/profiles/metadata")
      .then((value) => {
        setPayload(value);
        setError("");
      })
      .catch((err) => {
        setPayload(null);
        setError(err instanceof Error ? err.message : "Failed to load policy metadata.");
      });
  }, []);

  return (
    <div className="admin-route-page">
      <AdminSectionIntro
        eyebrow="Read-only"
        title="Policies"
        description="Surface current retrieval, rerank, and corpus policy metadata truthfully while deeper editors remain future work."
      />
      {error ? <div className="error-banner">{error}</div> : null}
      <div className="results-grid">
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Retrieval Defaults</h2>
              <p>Live retrieval policy metadata currently exposed by the backend.</p>
            </div>
          </div>
          <JsonPanel value={payload?.retrieval_settings || {}} />
        </section>
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Rerank Defaults</h2>
              <p>Current policy visibility without implying a full editor already exists.</p>
            </div>
          </div>
          <JsonPanel value={payload?.reranker_settings || {}} />
        </section>
      </div>
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Supported Corpus Policies</h2>
            <p>Explicit policy inventory for operators reviewing domain-shaped retrieval behavior.</p>
          </div>
        </div>
        <JsonPanel value={payload?.supported_corpus_policies || []} />
      </section>
    </div>
  );
}

export function AccessAdminPanel() {
  const [payload, setPayload] = useState<GenericMap | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    browserFetch<GenericMap>("/admin/access")
      .then((value) => {
        setPayload(value);
        setError("");
      })
      .catch((err) => {
        setPayload(null);
        setError(err instanceof Error ? err.message : "Failed to load access posture.");
      });
  }, []);

  const summary = (payload?.summary || {}) as GenericMap;
  const users = (payload?.users || []) as GenericMap[];
  const groups = (payload?.groups || []) as GenericMap[];
  const sourceAcl = (payload?.source_acl || []) as GenericMap[];

  return (
    <div className="admin-route-page">
      <AdminSectionIntro
        eyebrow="Read-only"
        title="Access"
        description="Review users, groups, and document ACL posture so operators do not have to inspect the database directly."
        badge={`${formatCount(summary.group_count, "group")}`}
      />
      {error ? <div className="error-banner">{error}</div> : null}
      <section className="admin-summary-cards">
        <article className="card">
          <h2>Users</h2>
          <p>{formatCount(summary.user_count, "synced user")}</p>
        </article>
        <article className="card">
          <h2>Groups</h2>
          <p>{formatCount(summary.group_count, "group")}</p>
        </article>
        <article className="card">
          <h2>Protected Sources</h2>
          <p>{formatCount(summary.protected_source_count, "protected source")}</p>
        </article>
        <article className="card">
          <h2>Open Sources</h2>
          <p>{formatCount(summary.open_source_count, "open source")}</p>
        </article>
      </section>
      <div className="results-grid">
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Groups</h2>
              <p>Member counts and protected-source coverage by group.</p>
            </div>
          </div>
          <div className="table-list">
            {groups.length ? groups.map((group) => (
              <article key={String(group.name)} className="table-row">
                <div>
                  <strong>{String(group.name)}</strong>
                  <span className="muted-copy">{`${formatCount(group.member_count, "member")} • ${formatCount(group.source_count, "source")}`}</span>
                </div>
              </article>
            )) : <EmptyState title="No groups synced yet." copy="Groups will appear here once authenticated users and ACLs are synced." />}
          </div>
        </section>
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Users</h2>
              <p>Recent synced users and their current group memberships.</p>
            </div>
          </div>
          <div className="table-list">
            {users.length ? users.map((user) => (
              <article key={String(user.external_user_id)} className="table-row">
                <div>
                  <strong>{String(user.display_name || user.email || user.external_user_id)}</strong>
                  <span className="muted-copy">{Array.isArray(user.groups) && user.groups.length ? (user.groups as string[]).join(", ") : "No groups synced"}</span>
                </div>
                <div className="table-metrics">
                  <span>{formatTimestamp(user.updated_at)}</span>
                </div>
              </article>
            )) : <EmptyState title="No users synced yet." copy="User sync will populate after authenticated requests pass through the system." />}
          </div>
        </section>
      </div>
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Document ACL Coverage</h2>
            <p>Source-level ACL posture across the current source inventory.</p>
          </div>
        </div>
        <div className="table-list">
          {sourceAcl.length ? sourceAcl.map((item) => (
            <article key={String(item.source_id)} className="table-row">
              <div>
                <strong>{String(item.file_name)}</strong>
                <span className="muted-copy">{`${String(item.corpus_name || "No corpus")} • ${String(item.sensitivity_label || "internal")}`}</span>
              </div>
              <div className="table-metrics">
                <span>{Array.isArray(item.groups) && item.groups.length ? (item.groups as string[]).join(", ") : "No explicit ACL"}</span>
                <Link href={`/console/admin/sources?sourceId=${String(item.source_id)}`} className="admin-inline-link">Open source</Link>
              </div>
            </article>
          )) : <EmptyState title="No source ACL data yet." copy="Once sources exist, their group assignments and open/protected posture will appear here." />}
        </div>
      </section>
    </div>
  );
}

export function AuditLogAdminPanel() {
  const defaultFilters = { query: "", action: "", resourceType: "", outcome: "", actor: "", sourceId: "", jobId: "", fromTs: "", toTs: "", sort: "newest" };
  const [filters, setFilters] = useState({ ...defaultFilters });
  const [draftFilters, setDraftFilters] = useState({ ...defaultFilters });
  const [payload, setPayload] = useState<{ events: GenericMap[] }>({ events: [] });
  const [selectedEventId, setSelectedEventId] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [savedViews, setSavedViews] = useState<SavedViewEntry[]>([]);
  const [savedViewName, setSavedViewName] = useState("");

  useEffect(() => {
    setSavedViews(readSavedAdminViews("audit"));
  }, []);

  async function refresh() {
    const params = new URLSearchParams();
    setIsLoading(true);
    if (filters.action) {
      params.set("action", filters.action);
    }
    if (filters.resourceType) {
      params.set("resource_type", filters.resourceType);
    }
    if (filters.outcome) {
      params.set("outcome", filters.outcome);
    }
    if (filters.actor) {
      params.set("actor_query", filters.actor);
    }
    if (filters.sourceId) {
      params.set("source_id", filters.sourceId);
    }
    if (filters.jobId) {
      params.set("job_id", filters.jobId);
    }
    if (filters.fromTs) {
      params.set("from_ts", new Date(filters.fromTs).toISOString());
    }
    if (filters.toTs) {
      params.set("to_ts", new Date(filters.toTs).toISOString());
    }
    try {
      const next = await browserFetch<{ events: GenericMap[] }>(`/admin/audit-log${params.toString() ? `?${params.toString()}` : ""}`);
      setPayload(next);
      setError("");
      setSelectedEventId((current) => current || String(next.events?.[0]?.id || ""));
    } catch (err) {
      setPayload({ events: [] });
      setError(err instanceof Error ? err.message : "Failed to load audit log.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [filters.action, filters.resourceType, filters.outcome, filters.actor, filters.sourceId, filters.jobId, filters.fromTs, filters.toTs]);

  const visibleEvents = useMemo(() => {
    const filtered = payload.events.filter((event) => {
      if (!matchesQuery(filters.query, [event.action, event.resource_name, event.resource_id, event.actor_email, event.actor_external_user_id, event.resource_type])) {
        return false;
      }
      return true;
    });
    return sortGenericMaps(filtered, filters.sort, {
      newest: (left, right) => toTimestampValue(right.created_at) - toTimestampValue(left.created_at),
      oldest: (left, right) => toTimestampValue(left.created_at) - toTimestampValue(right.created_at),
      action: (left, right) => String(left.action || "").localeCompare(String(right.action || "")),
    });
  }, [payload.events, filters.query, filters.actor, filters.sort]);

  const selectedEvent = useMemo(
    () => visibleEvents.find((item) => String(item.id) === selectedEventId) || null,
    [visibleEvents, selectedEventId],
  );

  const failedEvents = visibleEvents.filter((event) => normalizeText(event.outcome) === "failed").length;
  const hasPendingFilterChanges = !filtersMatch(filters, draftFilters);

  useEffect(() => {
    setSelectedEventId((current) => (current && visibleEvents.some((event) => String(event.id) === current) ? current : String(visibleEvents[0]?.id || "")));
  }, [visibleEvents]);

  function applySavedView(entry: SavedViewEntry) {
    const nextFilters = {
      query: String(entry.filters.query || ""),
      action: String(entry.filters.action || ""),
      resourceType: String(entry.filters.resourceType || ""),
      outcome: String(entry.filters.outcome || ""),
      actor: String(entry.filters.actor || ""),
      sourceId: String(entry.filters.sourceId || ""),
      jobId: String(entry.filters.jobId || ""),
      fromTs: String(entry.filters.fromTs || ""),
      toTs: String(entry.filters.toTs || ""),
      sort: String(entry.filters.sort || "newest"),
    };
    setDraftFilters(nextFilters);
    setFilters(nextFilters);
  }

  function saveCurrentView() {
    saveNamedView("audit", savedViewName, draftFilters, setSavedViews);
    setSavedViewName("");
  }

  function removeSavedView(entry: SavedViewEntry) {
    deleteNamedView("audit", entry.name, setSavedViews);
  }

  function exportAuditLog() {
    const params = new URLSearchParams();
    if (filters.action) {
      params.set("action", filters.action);
    }
    if (filters.resourceType) {
      params.set("resource_type", filters.resourceType);
    }
    if (filters.outcome) {
      params.set("outcome", filters.outcome);
    }
    if (filters.actor) {
      params.set("actor_query", filters.actor);
    }
    if (filters.sourceId) {
      params.set("source_id", filters.sourceId);
    }
    if (filters.jobId) {
      params.set("job_id", filters.jobId);
    }
    if (filters.fromTs) {
      params.set("from_ts", new Date(filters.fromTs).toISOString());
    }
    if (filters.toTs) {
      params.set("to_ts", new Date(filters.toTs).toISOString());
    }
    window.open(browserApiUrl(`/admin/audit-log/export${params.toString() ? `?${params.toString()}` : ""}`), "_blank", "noopener,noreferrer");
  }

  return (
    <div className="admin-route-page">
      <AdminSectionIntro
        eyebrow="Interactive"
        title="Audit Log"
        description="Append-only admin event history with actor, action, target, and before/after context."
        badge={`${payload.events.length} events`}
      />
      {error ? <div className="error-banner">{error}</div> : null}
      <section className="admin-summary-cards">
        <SummaryMetricCard label="Visible Events" value={formatCount(visibleEvents.length, "event")} />
        <SummaryMetricCard label="Failed Outcomes" value={formatCount(failedEvents, "event")} tone={failedEvents ? "is-danger" : ""} />
      </section>
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Filters</h2>
            <p>Filter the stored admin audit stream by action, resource type, and outcome.</p>
          </div>
        </div>
        <div className="admin-filter-grid admin-filter-grid-3">
          <input value={draftFilters.query} onChange={(event) => setDraftFilters((current) => ({ ...current, query: event.target.value }))} placeholder="Search action, actor, or resource" />
          <input value={draftFilters.action} onChange={(event) => setDraftFilters((current) => ({ ...current, action: event.target.value }))} placeholder="Action, e.g. profile.activate" />
          <input value={draftFilters.resourceType} onChange={(event) => setDraftFilters((current) => ({ ...current, resourceType: event.target.value }))} placeholder="Resource type, e.g. source" />
        </div>
        <div className="admin-filter-grid admin-filter-grid-3">
          <input value={draftFilters.actor} onChange={(event) => setDraftFilters((current) => ({ ...current, actor: event.target.value }))} placeholder="Actor email or id" />
          <input value={draftFilters.sourceId} onChange={(event) => setDraftFilters((current) => ({ ...current, sourceId: event.target.value }))} placeholder="Source id" />
          <input value={draftFilters.jobId} onChange={(event) => setDraftFilters((current) => ({ ...current, jobId: event.target.value }))} placeholder="Job id" />
        </div>
        <div className="admin-filter-grid admin-filter-grid-3">
          <input type="datetime-local" value={draftFilters.fromTs} onChange={(event) => setDraftFilters((current) => ({ ...current, fromTs: event.target.value }))} />
          <input type="datetime-local" value={draftFilters.toTs} onChange={(event) => setDraftFilters((current) => ({ ...current, toTs: event.target.value }))} />
          <select value={draftFilters.outcome} onChange={(event) => setDraftFilters((current) => ({ ...current, outcome: event.target.value }))}>
            <option value="">Any outcome</option>
            <option value="completed">completed</option>
            <option value="failed">failed</option>
          </select>
          <select value={draftFilters.sort} onChange={(event) => setDraftFilters((current) => ({ ...current, sort: event.target.value }))}>
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="action">Action</option>
          </select>
        </div>
        <div className="toolbar-inline">
          <span className={`badge ${hasPendingFilterChanges ? "is-warning" : ""}`}>{hasPendingFilterChanges ? "Unapplied filter changes" : `Showing ${visibleEvents.length} of ${payload.events.length} events`}</span>
          <button type="button" className="button button-primary" disabled={!hasPendingFilterChanges} onClick={() => setFilters({ ...draftFilters })}>
            Apply filters
          </button>
          <button type="button" className="button button-secondary" onClick={exportAuditLog}>
            Export JSONL
          </button>
          <button
            type="button"
            className="button button-secondary"
            onClick={() => {
              setDraftFilters({ ...defaultFilters });
              setFilters({ ...defaultFilters });
            }}
          >
            Reset filters
          </button>
        </div>
        <SavedViewsToolbar
          viewLabel="audit"
          draftName={savedViewName}
          onDraftNameChange={setSavedViewName}
          onSave={saveCurrentView}
          savedViews={savedViews}
          onApply={applySavedView}
          onDelete={removeSavedView}
        />
      </section>
      <div className="results-grid">
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Event Stream</h2>
              <p>Stored audit events for admin-originated control-plane actions.</p>
            </div>
          </div>
          <div className="table-list">
            {isLoading ? <EmptyState title="Loading audit log..." copy="Fetching stored admin events with the current server-side filters applied." icon="progress_activity" /> : visibleEvents.length ? visibleEvents.map((event) => (
              <article key={String(event.id)} className="table-row">
                <div>
                  <strong>{String(event.action)}</strong>
                  <span className="muted-copy">{`${String(event.actor_email || event.actor_external_user_id || "unknown actor")} • ${String(event.resource_name || event.resource_id || "resource")}`}</span>
                </div>
                <div className="table-metrics">
                  <span className={`badge ${statusTone(event.outcome)}`}>{String(event.outcome || "completed")}</span>
                  <span>{formatTimestamp(event.created_at)}</span>
                  <button type="button" className="button button-secondary" onClick={() => setSelectedEventId(String(event.id))}>
                    Inspect
                  </button>
                </div>
              </article>
            )) : <EmptyState title="No audit events matched." copy={payload.events.length ? "Audit events exist, but nothing matches the current query or saved view. Reset filters to reopen the broader stream." : "Admin mutations will appear here once operators perform profile, corpus, source, job, or eval actions."} />}
          </div>
        </section>

        <section className="card">
          <div className="section-head">
            <div>
              <h2>{selectedEvent ? `Event #${String(selectedEvent.id)}` : "Event detail"}</h2>
              <p>Stored actor, target, and before/after payload for the selected audit event.</p>
            </div>
          </div>
          {!selectedEvent ? <EmptyState title="Select an audit event." copy="Choose an event from the stream to inspect its stored before/after context." /> : <JsonPanel value={selectedEvent} />}
        </section>
      </div>
    </div>
  );
}
