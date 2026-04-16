"use client";

import Link from "next/link";
import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { browserFetch } from "@/lib/api-browser";

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
  const seconds = Number(value);
  if (!Number.isFinite(seconds)) {
    return "In progress";
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

function JsonPanel({ value }: { value: unknown }) {
  return <pre className="json-panel">{JSON.stringify(value ?? {}, null, 2)}</pre>;
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
  const [payload, setPayload] = useState<{ sources: GenericMap[] }>({ sources: [] });
  const [corporaPayload, setCorporaPayload] = useState<{ corpora: GenericMap[] }>({ corpora: [] });
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [draft, setDraft] = useState<SourceDraft>(sourceDraftFromItem(null));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [isLoading, setIsLoading] = useState(true);

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

  useEffect(() => {
    setDraft(sourceDraftFromItem(selectedSource));
  }, [selectedSource]);

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

  return (
    <div className="admin-route-page">
      <AdminSectionIntro
        eyebrow="Interactive"
        title="Sources"
        description="Inspect source-level status, corpus placement, ACL posture, and admin-triggered reindex/enrichment actions."
        badge={`${payload.sources.length} sources`}
      />
      {error ? <div className="error-banner">{error}</div> : null}
      <div className="results-grid">
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Source Inventory</h2>
              <p>Real source records with ingestion, enrichment, and access posture.</p>
            </div>
          </div>
          <div className="table-list">
            {isLoading ? <EmptyState title="Loading sources..." copy="Fetching source records, placement state, and ACL posture." icon="progress_activity" /> : payload.sources.length ? payload.sources.map((source) => (
              <article key={String(source.id)} className="table-row">
                <div>
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
            )) : <EmptyState title="No sources found." copy="This is normal on a clean install. User uploads and connector-backed sources will appear here once the first source record is created." icon="upload_file" />}
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
  const [payload, setPayload] = useState<{ ingestion_jobs: GenericMap[]; enrichment_jobs: GenericMap[] }>({ ingestion_jobs: [], enrichment_jobs: [] });
  const [selectedJobKey, setSelectedJobKey] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  async function refresh() {
    setIsLoading(true);
    try {
      const next = await browserFetch<{ ingestion_jobs: GenericMap[]; enrichment_jobs: GenericMap[] }>("/admin/jobs");
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
  const selectedJob = useMemo(
    () => jobs.find((job) => `${String(job.job_kind)}:${String(job.id)}` === selectedJobKey) || null,
    [jobs, selectedJobKey],
  );

  return (
    <div className="admin-route-page">
      <AdminSectionIntro
        eyebrow="Interactive"
        title="Jobs"
        description="Monitor ingestion and enrichment queues with real status, timing, actor, and related source context."
        badge={`${jobs.length} jobs`}
      />
      {error ? <div className="error-banner">{error}</div> : null}
      <div className="results-grid">
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Live Job Queue</h2>
              <p>Unified ingestion and enrichment view with truthful job metadata.</p>
            </div>
          </div>
          <div className="table-list">
            {isLoading ? <EmptyState title="Loading jobs..." copy="Fetching ingestion and enrichment queue state from the admin control plane." icon="progress_activity" /> : jobs.length ? jobs.map((job) => (
              <article key={`${String(job.job_kind)}:${String(job.id)}`} className="table-row">
                <div>
                  <strong>{`${String(job.job_kind)} job #${String(job.id)}`}</strong>
                  <span className="muted-copy">{`${String(job.source_file_name || "Unknown source")} • ${String(job.stage || "unknown stage")}`}</span>
                </div>
                <div className="table-metrics">
                  <span className={`badge ${statusTone(job.status)}`}>{String(job.status || "unknown")}</span>
                  <span>{String(job.triggered_by || "system")}</span>
                  <button type="button" className="button button-secondary" onClick={() => setSelectedJobKey(`${String(job.job_kind)}:${String(job.id)}`)}>
                    Inspect
                  </button>
                </div>
              </article>
            )) : <EmptyState title="No jobs recorded." copy="This is normal on a clean system. The first upload, reindex, or enrichment run will appear here as soon as the platform has indexing work to track." icon="work_history" />}
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
              <div className="toolbar-inline">
                {selectedJob.source_id ? <Link href={`/console/admin/sources?sourceId=${String(selectedJob.source_id)}`} className="admin-inline-link">Open source</Link> : null}
                {selectedJob.corpus_name ? <Link href="/console/admin/corpora" className="admin-inline-link">Open corpora</Link> : null}
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
                  source_id: selectedJob.source_id,
                  source_file_name: selectedJob.source_file_name,
                  corpus_name: selectedJob.corpus_name,
                  error_message: selectedJob.error_message,
                  job_metadata_json: selectedJob.job_metadata_json,
                }}
              />
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
      <div className="results-grid">
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Recent Retrieval Traces</h2>
              <p>Stored traces with fallback and latency context.</p>
            </div>
          </div>
          <div className="table-list">
            {isLoading ? <EmptyState title="Loading traces..." copy="Fetching stored retrieval traces and the latest debug-ready request records." icon="progress_activity" /> : payload.traces.length ? payload.traces.map((trace) => (
              <article key={String(trace.id)} className="table-row">
                <div>
                  <strong>{String(trace.request_id || trace.id)}</strong>
                  <span className="muted-copy">{String(trace.retrieval_path || trace.resolved_mode || "hybrid")}</span>
                </div>
                <div className="table-metrics">
                  <span className={`badge ${statusTone(trace.has_fallback ? "warning" : "available")}`}>{trace.has_fallback ? "Fallback" : "Direct"}</span>
                  <span>{String(trace.total_latency_ms || trace.search_latency_ms || "-")} ms</span>
                  <button type="button" className="button button-secondary" onClick={() => setSelectedTraceId(String(trace.id))}>
                    Inspect
                  </button>
                </div>
              </article>
            )) : <EmptyState title="No retrieval traces yet." copy="This is normal on a clean system. Ask a question in the user workspace or run query debug above to generate the first stored trace." icon="timeline" />}
          </div>
        </section>

        <section className="card">
          <div className="section-head">
            <div>
              <h2>{traceDetail ? `Trace #${String(traceDetail.id)}` : "Trace detail"}</h2>
              <p>Stored debug detail for the selected retrieval request.</p>
            </div>
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
  const [filters, setFilters] = useState({ action: "", resourceType: "", outcome: "" });
  const [payload, setPayload] = useState<{ events: GenericMap[] }>({ events: [] });
  const [selectedEventId, setSelectedEventId] = useState("");
  const [error, setError] = useState("");

  async function refresh() {
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
    try {
      const next = await browserFetch<{ events: GenericMap[] }>(`/admin/audit-log${params.toString() ? `?${params.toString()}` : ""}`);
      setPayload(next);
      setError("");
      setSelectedEventId((current) => current || String(next.events?.[0]?.id || ""));
    } catch (err) {
      setPayload({ events: [] });
      setError(err instanceof Error ? err.message : "Failed to load audit log.");
    }
  }

  useEffect(() => {
    refresh();
  }, [filters.action, filters.resourceType, filters.outcome]);

  const selectedEvent = useMemo(
    () => payload.events.find((item) => String(item.id) === selectedEventId) || null,
    [payload, selectedEventId],
  );

  return (
    <div className="admin-route-page">
      <AdminSectionIntro
        eyebrow="Interactive"
        title="Audit Log"
        description="Append-only admin event history with actor, action, target, and before/after context."
        badge={`${payload.events.length} events`}
      />
      {error ? <div className="error-banner">{error}</div> : null}
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Filters</h2>
            <p>Filter the stored admin audit stream by action, resource type, and outcome.</p>
          </div>
        </div>
        <div className="form-inline">
          <input value={filters.action} onChange={(event) => setFilters((current) => ({ ...current, action: event.target.value }))} placeholder="Action, e.g. profile.activate" />
          <input value={filters.resourceType} onChange={(event) => setFilters((current) => ({ ...current, resourceType: event.target.value }))} placeholder="Resource type, e.g. source" />
          <select value={filters.outcome} onChange={(event) => setFilters((current) => ({ ...current, outcome: event.target.value }))}>
            <option value="">Any outcome</option>
            <option value="completed">completed</option>
            <option value="failed">failed</option>
          </select>
        </div>
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
            {payload.events.length ? payload.events.map((event) => (
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
            )) : <EmptyState title="No audit events matched." copy="Admin mutations will appear here once operators perform profile, corpus, source, job, or eval actions." />}
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
