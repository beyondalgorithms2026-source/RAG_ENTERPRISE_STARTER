"use client";

import { FormEvent, useEffect, useState } from "react";

import { browserFetch } from "@/lib/api-browser";

type GenericMap = Record<string, unknown>;

export function CorporaAdminPanel() {
  const [payload, setPayload] = useState<{ corpora: GenericMap[]; sources: GenericMap[]; unassigned_source_count: number } | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");

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
    await browserFetch("/admin/corpora", {
      method: "POST",
      json: { name, description, metadata_json: {} },
    });
    setName("");
    setDescription("");
    refresh();
  }

  return (
    <div className="page-stack">
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Corpora</h2>
            <p>Manage corpora, source grouping, and sensitivity-aware organization.</p>
          </div>
          <span className="badge">{payload?.corpora?.length || 0} corpora</span>
        </div>
        <form className="form-inline" onSubmit={createCorpus}>
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Corpus name" />
          <input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Description" />
          <button className="button button-primary" type="submit">
            Create
          </button>
        </form>
      </section>
      <section className="card">
        {error ? <div className="error-banner">{error}</div> : null}
        <div className="table-list">
          {(payload?.corpora || []).map((corpus) => (
            <article key={String(corpus.name)} className="table-row">
              <div>
                <strong>{String(corpus.name)}</strong>
                <span className="muted-copy">{String(corpus.description || "")}</span>
              </div>
              <div className="table-metrics">
                <span>{String(corpus.source_count)} sources</span>
                <span>{String(corpus.updated_at)}</span>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

export function JobsAdminPanel() {
  const [payload, setPayload] = useState<{ ingestion_jobs: GenericMap[]; enrichment_jobs: GenericMap[] } | null>(null);

  useEffect(() => {
    browserFetch<{ ingestion_jobs: GenericMap[]; enrichment_jobs: GenericMap[] }>("/admin/jobs")
      .then(setPayload)
      .catch(() => setPayload({ ingestion_jobs: [], enrichment_jobs: [] }));
  }, []);

  return (
    <div className="results-grid">
      <section className="card">
        <div className="section-head">
          <h2>Ingestion Jobs</h2>
        </div>
        <div className="table-list">
          {(payload?.ingestion_jobs || []).map((job) => (
            <article key={String(job.id)} className="table-row">
              <div>
                <strong>Job #{String(job.id)}</strong>
                <span className="muted-copy">{String(job.stage)}</span>
              </div>
              <div className="table-metrics">
                <span>{String(job.status)}</span>
                <span>source {String(job.source_id ?? "-")}</span>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="card">
        <div className="section-head">
          <h2>Enrichment Jobs</h2>
        </div>
        <div className="table-list">
          {(payload?.enrichment_jobs || []).map((job) => (
            <article key={String(job.id)} className="table-row">
              <div>
                <strong>Job #{String(job.id)}</strong>
                <span className="muted-copy">{String(job.stage)}</span>
              </div>
              <div className="table-metrics">
                <span>{String(job.status)}</span>
                <span>source {String(job.source_id ?? "-")}</span>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

export function ProfilesAdminPanel() {
  const [payload, setPayload] = useState<{ profiles: GenericMap[] } | null>(null);

  async function refresh() {
    setPayload(await browserFetch<{ profiles: GenericMap[] }>("/admin/profiles"));
  }

  useEffect(() => {
    refresh();
  }, []);

  async function activate(profileType: string, profileName: string) {
    await browserFetch("/admin/profiles/active", {
      method: "POST",
      json: { profile_type: profileType, profile_name: profileName },
    });
    refresh();
  }

  return (
    <section className="card">
      <div className="section-head">
        <h2>Profiles</h2>
      </div>
      <div className="table-list">
        {(payload?.profiles || []).map((profile) => (
          <article key={`${String(profile.profile_type)}-${String(profile.name)}`} className="table-row">
            <div>
              <strong>
                {String(profile.profile_type)} / {String(profile.name)}
              </strong>
              <span className="muted-copy">{profile.is_active ? "Active profile" : "Inactive profile"}</span>
            </div>
            <button
              type="button"
              className="button button-secondary"
              disabled={Boolean(profile.is_active)}
              onClick={() => activate(String(profile.profile_type), String(profile.name))}
            >
              {profile.is_active ? "Active" : "Activate"}
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}

export function EvalsAdminPanel() {
  const [reports, setReports] = useState<{ reports: GenericMap[] } | null>(null);
  const [running, setRunning] = useState<string>("");

  async function refresh() {
    setReports(await browserFetch<{ reports: GenericMap[] }>("/admin/eval/reports"));
  }

  useEffect(() => {
    refresh();
  }, []);

  async function run(kind: string) {
    setRunning(kind);
    await browserFetch("/admin/eval/run", { method: "POST", json: { report_kind: kind } });
    setRunning("");
    refresh();
  }

  return (
    <div className="page-stack">
      <section className="card">
        <div className="section-head">
          <h2>Eval Reports</h2>
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
      <section className="card">
        <div className="table-list">
          {(reports?.reports || []).map((report) => (
            <article key={String(report.kind)} className="table-row">
              <div>
                <strong>{String(report.kind)}</strong>
                <span className="muted-copy">{String(report.path)}</span>
              </div>
              <div className="table-metrics">
                <span>{report.exists ? "Available" : "Missing"}</span>
                <span>{String((report.summary as GenericMap | undefined)?.pass_rate_percent ?? "-")}%</span>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

export function TracesAdminPanel() {
  const [payload, setPayload] = useState<{ traces: GenericMap[] } | null>(null);

  useEffect(() => {
    browserFetch<{ traces: GenericMap[] }>("/admin/traces")
      .then(setPayload)
      .catch(() => setPayload({ traces: [] }));
  }, []);

  return (
    <section className="card">
      <div className="section-head">
        <h2>Retrieval Traces</h2>
      </div>
      <div className="table-list">
        {(payload?.traces || []).map((trace) => (
          <article key={String(trace.id)} className="table-row">
            <div>
              <strong>{String(trace.request_id)}</strong>
              <span className="muted-copy">{String(trace.retrieval_path || trace.resolved_mode || "")}</span>
            </div>
            <div className="table-metrics">
              <span>{String(trace.created_at || "")}</span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export function PoliciesAdminPanel() {
  const [payload, setPayload] = useState<GenericMap | null>(null);

  useEffect(() => {
    browserFetch<GenericMap>("/admin/profiles/metadata").then(setPayload).catch(() => setPayload(null));
  }, []);

  return (
    <div className="results-grid">
      <section className="card">
        <div className="section-head">
          <h2>Retrieval Defaults</h2>
        </div>
        <pre className="json-panel">{JSON.stringify(payload?.retrieval_settings || {}, null, 2)}</pre>
      </section>
      <section className="card">
        <div className="section-head">
          <h2>Corpus Policies</h2>
        </div>
        <pre className="json-panel">{JSON.stringify(payload?.supported_corpus_policies || [], null, 2)}</pre>
      </section>
    </div>
  );
}
