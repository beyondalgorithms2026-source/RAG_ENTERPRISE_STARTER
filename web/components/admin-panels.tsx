"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { browserFetch } from "@/lib/api-browser";

type GenericMap = Record<string, unknown>;

type AdminSectionIntroProps = {
  eyebrow: string;
  title: string;
  description: string;
  badge?: string;
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

function statusTone(value: unknown) {
  const normalized = String(value || "").toLowerCase();
  if (["completed", "embedded", "indexed", "active", "available"].includes(normalized)) {
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

function EmptyState({ title, copy }: { title: string; copy: string }) {
  return (
    <div className="admin-empty-state">
      <span className="material-symbols-outlined">inbox</span>
      <strong>{title}</strong>
      <p>{copy}</p>
    </div>
  );
}

export function CorporaAdminPanel() {
  const [payload, setPayload] = useState<{ corpora: GenericMap[]; sources: GenericMap[]; unassigned_source_count: number } | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function refresh() {
    try {
      setPayload(await browserFetch<{ corpora: GenericMap[]; sources: GenericMap[]; unassigned_source_count: number }>("/admin/corpora"));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load corpora.");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create corpus.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="admin-route-page">
      <AdminSectionIntro
        eyebrow="Interactive"
        title="Corpora"
        description="Create and inspect corpus groupings, review source distribution, and orient operators before deeper corpus actions arrive."
        badge={`${payload?.corpora?.length || 0} corpora`}
      />
      <section className="admin-route-grid">
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Create Corpus</h2>
              <p>Current backend support already allows corpus creation without code edits.</p>
            </div>
          </div>
          <form className="admin-form-grid" onSubmit={createCorpus}>
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Corpus name" />
            <input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Description" />
            <button className="button button-primary" type="submit" disabled={isSubmitting || !name.trim()}>
              {isSubmitting ? "Creating..." : "Create corpus"}
            </button>
          </form>
          {error ? <div className="error-banner">{error}</div> : null}
        </section>

        <section className="card">
          <div className="section-head">
            <div>
              <h2>Corpus Inventory</h2>
              <p>Live corpus definitions and source counts from the admin API.</p>
            </div>
            <span className="badge">{formatCount(payload?.unassigned_source_count, "unassigned source")}</span>
          </div>
          <div className="table-list">
            {payload?.corpora?.length ? payload.corpora.map((corpus) => (
              <article key={String(corpus.name)} className="table-row">
                <div>
                  <strong>{String(corpus.name)}</strong>
                  <span className="muted-copy">{String(corpus.description || "No description yet.")}</span>
                </div>
                <div className="table-metrics">
                  <span>{formatCount(corpus.source_count, "source")}</span>
                  <span>{formatTimestamp(corpus.updated_at)}</span>
                </div>
              </article>
            )) : <EmptyState title="No corpora yet." copy="Create the first corpus here to move beyond a single global source bucket." />}
          </div>
        </section>
      </section>
    </div>
  );
}

export function JobsAdminPanel() {
  const [payload, setPayload] = useState<{ ingestion_jobs: GenericMap[]; enrichment_jobs: GenericMap[] } | null>(null);
  const [error, setError] = useState("");

  async function refresh() {
    try {
      setPayload(await browserFetch<{ ingestion_jobs: GenericMap[]; enrichment_jobs: GenericMap[] }>("/admin/jobs"));
      setError("");
    } catch (err) {
      setPayload({ ingestion_jobs: [], enrichment_jobs: [] });
      setError(err instanceof Error ? err.message : "Failed to load job state.");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const totalJobs = (payload?.ingestion_jobs.length || 0) + (payload?.enrichment_jobs.length || 0);

  return (
    <div className="admin-route-page">
      <AdminSectionIntro
        eyebrow="Interactive"
        title="Jobs"
        description="Monitor ingestion and enrichment activity from a routed operator page instead of bouncing back to overview."
        badge={`${totalJobs} jobs`}
      />
      {error ? <div className="error-banner">{error}</div> : null}
      <div className="results-grid">
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Ingestion Jobs</h2>
              <p>Current upload, parse, chunk, and embedding stages.</p>
            </div>
          </div>
          <div className="table-list">
            {payload?.ingestion_jobs.length ? payload.ingestion_jobs.map((job) => (
              <article key={`ingestion-${String(job.id)}`} className="table-row">
                <div>
                  <strong>{`Job #${String(job.id)}`}</strong>
                  <span className="muted-copy">{`Stage: ${String(job.stage || "unknown")}`}</span>
                </div>
                <div className="table-metrics">
                  <span className={`badge ${statusTone(job.status)}`}>{String(job.status || "unknown")}</span>
                  <span>{`Source ${String(job.source_id ?? "-")}`}</span>
                </div>
              </article>
            )) : <EmptyState title="No ingestion jobs recorded." copy="Upload or reindex activity will appear here when the ingestion pipeline runs." />}
          </div>
        </section>

        <section className="card">
          <div className="section-head">
            <div>
              <h2>Enrichment Jobs</h2>
              <p>Graph, temporal, and follow-on enrichment work when enabled.</p>
            </div>
          </div>
          <div className="table-list">
            {payload?.enrichment_jobs.length ? payload.enrichment_jobs.map((job) => (
              <article key={`enrichment-${String(job.id)}`} className="table-row">
                <div>
                  <strong>{`Job #${String(job.id)}`}</strong>
                  <span className="muted-copy">{`Stage: ${String(job.stage || "unknown")}`}</span>
                </div>
                <div className="table-metrics">
                  <span className={`badge ${statusTone(job.status)}`}>{String(job.status || "unknown")}</span>
                  <span>{`Source ${String(job.source_id ?? "-")}`}</span>
                </div>
              </article>
            )) : <EmptyState title="No enrichment jobs recorded." copy="This remains truthful even when enrichment is disabled by configuration." />}
          </div>
        </section>
      </div>
    </div>
  );
}

export function ProfilesAdminPanel() {
  const [payload, setPayload] = useState<{ profiles: GenericMap[] } | null>(null);
  const [error, setError] = useState("");
  const [activating, setActivating] = useState("");

  async function refresh() {
    try {
      setPayload(await browserFetch<{ profiles: GenericMap[] }>("/admin/profiles"));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load profiles.");
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
        description="Review and activate embedding, retrieval, reranker, and LLM profiles from a dedicated control-plane page."
        badge={`${payload?.profiles?.length || 0} profiles`}
      />
      {error ? <div className="error-banner">{error}</div> : null}
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Profile Registry</h2>
            <p>Current backend support already allows activation from this page.</p>
          </div>
        </div>
        <div className="table-list">
          {payload?.profiles?.length ? payload.profiles.map((profile) => {
            const profileType = String(profile.profile_type);
            const profileName = String(profile.name);
            const key = `${profileType}:${profileName}`;
            return (
              <article key={key} className="table-row">
                <div>
                  <strong>{`${profileType} / ${profileName}`}</strong>
                  <span className="muted-copy">{profile.is_active ? "Active profile" : "Available for activation"}</span>
                </div>
                <button
                  type="button"
                  className="button button-secondary"
                  disabled={Boolean(profile.is_active) || activating === key}
                  onClick={() => activate(profileType, profileName)}
                >
                  {profile.is_active ? "Active" : activating === key ? "Activating..." : "Activate"}
                </button>
              </article>
            );
          }) : <EmptyState title="No profiles found." copy="Profile metadata should appear here once the backend registry is seeded." />}
        </div>
      </section>
    </div>
  );
}

export function EvalsAdminPanel() {
  const [reports, setReports] = useState<{ reports: GenericMap[] } | null>(null);
  const [running, setRunning] = useState<string>("");
  const [error, setError] = useState("");

  async function refresh() {
    try {
      setReports(await browserFetch<{ reports: GenericMap[] }>("/admin/eval/reports"));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load eval reports.");
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

  return (
    <div className="admin-route-page">
      <AdminSectionIntro
        eyebrow="Interactive"
        title="Evals"
        description="Trigger retrieval checks and review report availability from a routed operator surface."
        badge={`${reports?.reports?.length || 0} report slots`}
      />
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Run Eval Packs</h2>
            <p>Current control-plane support already exposes retrieval and benchmark runs here.</p>
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
        {error ? <div className="error-banner">{error}</div> : null}
      </section>
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Report Inventory</h2>
            <p>Available and missing report files are surfaced here without pretending comparison UX is deeper than it is today.</p>
          </div>
        </div>
        <div className="table-list">
          {reports?.reports?.length ? reports.reports.map((report) => (
            <article key={String(report.kind)} className="table-row">
              <div>
                <strong>{String(report.kind)}</strong>
                <span className="muted-copy">{String(report.path || "No report path")}</span>
              </div>
              <div className="table-metrics">
                <span className={`badge ${statusTone(report.exists ? "available" : "missing")}`}>{report.exists ? "Available" : "Missing"}</span>
                <span>{`${String((report.summary as GenericMap | undefined)?.pass_rate_percent ?? "-")}% pass`}</span>
              </div>
            </article>
          )) : <EmptyState title="No report metadata available." copy="Run an eval above to populate this routed page." />}
        </div>
      </section>
    </div>
  );
}

export function TracesAdminPanel() {
  const [payload, setPayload] = useState<{ traces: GenericMap[]; active_profiles?: GenericMap; retrieval_settings?: GenericMap } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    browserFetch<{ traces: GenericMap[]; active_profiles?: GenericMap; retrieval_settings?: GenericMap }>("/admin/traces")
      .then((value) => {
        setPayload(value);
        setError("");
      })
      .catch((err) => {
        setPayload({ traces: [] });
        setError(err instanceof Error ? err.message : "Failed to load traces.");
      });
  }, []);

  return (
    <div className="admin-route-page">
      <AdminSectionIntro
        eyebrow="Interactive"
        title="Traces"
        description="Inspect routed retrieval traces from a dedicated page instead of the overview table alone."
        badge={`${payload?.traces?.length || 0} traces`}
      />
      {error ? <div className="error-banner">{error}</div> : null}
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Recent Retrieval Traces</h2>
            <p>Current backend support allows live trace listing; deeper per-trace workflow can grow later without collapsing this route.</p>
          </div>
        </div>
        <div className="table-list">
          {payload?.traces?.length ? payload.traces.map((trace) => (
            <article key={String(trace.id)} className="table-row">
              <div>
                <strong>{String(trace.request_id || trace.id)}</strong>
                <span className="muted-copy">{String(trace.retrieval_path || trace.resolved_mode || "hybrid")}</span>
              </div>
              <div className="table-metrics">
                <span>{formatTimestamp(trace.created_at)}</span>
                <span>{`${String(trace.total_latency_ms ?? trace.search_latency_ms ?? "-")} ms`}</span>
              </div>
            </article>
          )) : <EmptyState title="No retrieval traces yet." copy="Ask or search activity with trace capture enabled will appear here." />}
        </div>
      </section>
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
        description="Surface current retrieval, rerank, and corpus policy metadata truthfully while deeper editing controls stay mapped to later milestones."
      />
      {error ? <div className="error-banner">{error}</div> : null}
      <div className="results-grid">
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Retrieval Defaults</h2>
              <p>Live policy metadata already exposed by the backend.</p>
            </div>
          </div>
          <pre className="json-panel">{JSON.stringify(payload?.retrieval_settings || {}, null, 2)}</pre>
        </section>
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Rerank Defaults</h2>
              <p>Current policy layer visibility without pretending a full editor exists yet.</p>
            </div>
          </div>
          <pre className="json-panel">{JSON.stringify(payload?.reranker_settings || {}, null, 2)}</pre>
        </section>
      </div>
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Supported Corpus Policies</h2>
            <p>Explicit policy inventory for operators reviewing domain-shaped retrieval behavior.</p>
          </div>
        </div>
        <pre className="json-panel">{JSON.stringify(payload?.supported_corpus_policies || [], null, 2)}</pre>
      </section>
    </div>
  );
}

export function AuditLogAdminPanel() {
  const [payload, setPayload] = useState<{ traces: GenericMap[]; ingestion_jobs: GenericMap[]; enrichment_jobs: GenericMap[] } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      browserFetch<{ traces: GenericMap[] }>("/admin/traces"),
      browserFetch<{ ingestion_jobs: GenericMap[]; enrichment_jobs: GenericMap[] }>("/admin/jobs"),
    ])
      .then(([traces, jobs]) => {
        setPayload({
          traces: traces.traces || [],
          ingestion_jobs: jobs.ingestion_jobs || [],
          enrichment_jobs: jobs.enrichment_jobs || [],
        });
        setError("");
      })
      .catch((err) => {
        setPayload({ traces: [], ingestion_jobs: [], enrichment_jobs: [] });
        setError(err instanceof Error ? err.message : "Failed to load current audit surfaces.");
      });
  }, []);

  const auditHighlights = useMemo(() => [
    {
      title: "Current coverage",
      body: "Authenticated search, ACL-sensitive retrieval, job state, and trace inspection are already present today.",
    },
    {
      title: "Truthful limitation",
      body: "A dedicated append-only audit viewer remains a later milestone, so this page stays a live summary instead of pretending to be a full audit workflow.",
    },
    {
      title: "Operator next step",
      body: "Use Jobs and Traces for today’s live inspection paths; upgrade to richer audit filtering lands later without removing this route.",
    },
  ], []);

  return (
    <div className="admin-route-page">
      <AdminSectionIntro
        eyebrow="Live summary"
        title="Audit Log"
        description="Keep the audit destination real and useful today, while being explicit that the deeper viewer lands in a later milestone."
      />
      {error ? <div className="error-banner">{error}</div> : null}
      <div className="admin-summary-cards">
        <article className="card">
          <h2>Search & Trace Events</h2>
          <p>{formatCount(payload?.traces.length, "trace event")} currently inspectable through the trace APIs and UI.</p>
          <Link href="/console/admin/traces" className="admin-inline-link">Open traces</Link>
        </article>
        <article className="card">
          <h2>Ingestion Activity</h2>
          <p>{formatCount(payload?.ingestion_jobs.length, "ingestion job")} and {formatCount(payload?.enrichment_jobs.length, "enrichment job")} visible from today’s job state APIs.</p>
          <Link href="/console/admin/jobs" className="admin-inline-link">Open jobs</Link>
        </article>
      </div>
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Current Audit Surface</h2>
            <p>This route is intentionally honest: useful now, fuller later.</p>
          </div>
        </div>
        <div className="table-list">
          {auditHighlights.map((item) => (
            <article key={item.title} className="table-row">
              <div>
                <strong>{item.title}</strong>
                <span className="muted-copy">{item.body}</span>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
