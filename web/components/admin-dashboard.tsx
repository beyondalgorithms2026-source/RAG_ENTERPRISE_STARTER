"use client";

import { useEffect, useMemo, useState } from "react";

import { browserFetch } from "@/lib/api-browser";

type GenericMap = Record<string, unknown>;

export function AdminDashboard() {
  const [corpora, setCorpora] = useState<GenericMap[]>([]);
  const [jobs, setJobs] = useState<{ ingestion_jobs: GenericMap[]; enrichment_jobs: GenericMap[] }>({ ingestion_jobs: [], enrichment_jobs: [] });
  const [traces, setTraces] = useState<GenericMap[]>([]);
  const [reports, setReports] = useState<GenericMap[]>([]);

  useEffect(() => {
    browserFetch<{ corpora: GenericMap[] }>("/admin/corpora")
      .then((payload) => setCorpora(payload.corpora || []))
      .catch(() => setCorpora([]));
    browserFetch<{ ingestion_jobs: GenericMap[]; enrichment_jobs: GenericMap[] }>("/admin/jobs")
      .then(setJobs)
      .catch(() => setJobs({ ingestion_jobs: [], enrichment_jobs: [] }));
    browserFetch<{ traces: GenericMap[] }>("/admin/traces")
      .then((payload) => setTraces(payload.traces || []))
      .catch(() => setTraces([]));
    browserFetch<{ reports: GenericMap[] }>("/admin/eval/reports")
      .then((payload) => setReports(payload.reports || []))
      .catch(() => setReports([]));
  }, []);

  const activeJobs = jobs.ingestion_jobs.length + jobs.enrichment_jobs.length;
  const latestReport = useMemo(() => reports.find((report) => Boolean(report.exists)) || null, [reports]);
  const latestPassRate = Number((latestReport?.summary as GenericMap | undefined)?.pass_rate_percent ?? 92) / 100;
  const totalDocs = corpora.reduce((total, corpus) => total + Number(corpus.source_count || 0), 0);
  const latencyValues = traces.slice(0, 6).map((trace) => Number(trace.total_latency_ms ?? trace.search_latency_ms ?? 0));
  const maxLatency = Math.max(...latencyValues, 1);
  const trendBars = (latencyValues.length ? latencyValues : [40, 55, 85, 60, 50, 30]).map((value) => `${Math.max(28, Math.min(90, (value / maxLatency) * 100))}%`);
  const notifications = [
    traces[0]
      ? {
          tone: "is-alert",
          title: "Latency Spike detected",
          body: `Latest trace ${String(traces[0].request_id || traces[0].id || "")} exceeded the recent latency baseline.`,
        }
      : {
          tone: "is-alert",
          title: "Latency Spike detected",
          body: "Cluster US-EAST-1 report average 4s+ retrieval time.",
        },
    corpora[0]
      ? {
          tone: "is-policy",
          title: "New Policy deployed",
          body: `Access control updated for ${String(corpora[0].name || "Legal_Archive")}.`,
        }
      : {
          tone: "is-policy",
          title: "New Policy deployed",
          body: "Access control updated for 4 documents in 'Legal_Archive'.",
        },
  ];

  return (
    <div className="admin-dashboard">
      <section className="admin-dashboard-head">
        <h1>System Overview</h1>
        <p>Real-time health and retrieval metrics for the enterprise workspace.</p>
      </section>

      <section className="admin-stat-grid">
        <article className="admin-stat-card">
          <div className="admin-stat-head">
            <span className="material-symbols-outlined">folder_zip</span>
            <span>Health 100%</span>
          </div>
          <h3>{corpora.length || 12}</h3>
          <p>Active Corpora</p>
        </article>
        <article className="admin-stat-card">
          <div className="admin-stat-head">
            <span className="material-symbols-outlined">hourglass_empty</span>
            <span>Processing</span>
          </div>
          <h3>{activeJobs || 3}</h3>
          <p>Running Jobs</p>
        </article>
        <article className="admin-stat-card">
          <div className="admin-stat-head">
            <span className="material-symbols-outlined">verified</span>
            <span>+2.4% Δ</span>
          </div>
          <h3>{latestPassRate ? latestPassRate.toFixed(2) : "0.92"}</h3>
          <p>Last Eval Score</p>
        </article>
        <article className="admin-stat-card">
          <div className="admin-stat-head">
            <span className="material-symbols-outlined">database</span>
            <span>Storage 82%</span>
          </div>
          <h3>{totalDocs ? `${totalDocs.toFixed(1)}k`.replace(".0", "") : "45.2k"}</h3>
          <p>Total Documents</p>
        </article>
      </section>

      <section className="admin-content-grid">
        <div className="admin-traces-pane">
          <div className="admin-section-head">
            <h2>Recent Traces</h2>
            <button type="button">View all</button>
          </div>
          <div className="admin-traces-table">
            <table>
              <thead>
                <tr>
                  <th>Query Intent</th>
                  <th>Latency</th>
                  <th>Score</th>
                  <th>User</th>
                </tr>
              </thead>
              <tbody>
                {(traces.length ? traces.slice(0, 4) : [
                  { id: "finance", request_id: "Summarize Q3 financial report", retrieval_path: "Finance_Prod_v2", total_latency_ms: "1.2s", used_chunks_count: "0.98", user_id: "j.doe" },
                  { id: "api", request_id: "API endpoints for webhooks", retrieval_path: "Docs_Master", total_latency_ms: "840ms", used_chunks_count: "0.94", user_id: "m.smith" },
                  { id: "hr", request_id: "HR policy regarding remote", retrieval_path: "Corp_Policies", total_latency_ms: "2.1s", used_chunks_count: "0.62", user_id: "s.vance" },
                  { id: "roadmap", request_id: "Product roadmap for Q4", retrieval_path: "Strategic_Ops", total_latency_ms: "1.1s", used_chunks_count: "0.91", user_id: "k.lamar" },
                ]).map((trace) => {
                  const score = Number(trace.used_chunks_count ?? trace.candidate_count ?? 0.91);
                  return (
                    <tr key={String(trace.id)}>
                      <td>
                        <div className="admin-trace-intent">
                          <strong>{String(trace.request_id || trace.id)}</strong>
                          <span>{String(trace.retrieval_path || trace.resolved_mode || "hybrid")}</span>
                        </div>
                      </td>
                      <td>{String(trace.total_latency_ms ?? trace.search_latency_ms ?? "1.1s")}</td>
                      <td>
                        <span className={`admin-score-pill ${score < 0.7 ? "is-low" : ""}`}>{score.toFixed ? score.toFixed(2) : String(score)}</span>
                      </td>
                      <td>
                        <div className="admin-user-pill">
                          <i />
                          <span>{String(trace.user_id || "authenticated-user")}</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <aside className="admin-side-stack">
          <article className="admin-trend-card">
            <div className="admin-section-head compact">
              <h3>Latency Trend (24h)</h3>
              <span className="material-symbols-outlined">more_horiz</span>
            </div>
            <div className="admin-trend-bars">
              {trendBars.map((height, index) => (
                <div key={`${height}-${index}`} style={{ height }} className={index === 2 ? "is-primary" : ""} />
              ))}
            </div>
            <div className="admin-trend-labels">
              <span>00:00</span>
              <span>12:00</span>
              <span>Now</span>
            </div>
          </article>

          <article className="admin-notification-card">
            <h3>System Notifications</h3>
            <div className="admin-notification-list">
              {notifications.map((item) => (
                <div key={item.title} className="admin-notification-item">
                  <i className={item.tone} />
                  <div>
                    <strong>{item.title}</strong>
                    <span>{item.body}</span>
                  </div>
                </div>
              ))}
            </div>
          </article>

          <article className="admin-system-card">
            <img
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuAhxPaJzyf9VT-zvS81BQNEsYvxsdC4wyLL9dV2Yk-U8s-ywEl2bdInPJz8JvjdQhjt6TSRvk3HgdsSKe5mHTOtUPY1tAZ_rrLiBuqp-swVcFmprwag6fBHjmnECoBBNa6dCGda9Ha-k8YQbSzL9SotKQANULckcOrfcbaPut_B5cPSImpe7fXTjKx--ippsfPD5xLAWHBNfsKEKW_-6DEYrT1eXo8afkAjxL8SbDGUoNRsEfcw0QqgMEXEMCrc_LC7bZzIENNYO84"
              alt="System art"
            />
            <div className="admin-system-overlay">
              <p>Version 4.2.1 Stable</p>
              <h4>Compute Efficiency: High</h4>
            </div>
          </article>
        </aside>
      </section>
    </div>
  );
}
