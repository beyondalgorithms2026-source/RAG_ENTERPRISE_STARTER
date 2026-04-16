"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { browserFetch } from "@/lib/api-browser";

type GenericMap = Record<string, unknown>;

function formatMetric(value: unknown, suffix = "") {
  if (value === null || value === undefined || value === "") {
    return "Unavailable";
  }
  if (typeof value === "number") {
    return `${value}${suffix}`;
  }
  return `${String(value)}${suffix}`;
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

export function AdminDashboard() {
  const [payload, setPayload] = useState<GenericMap | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    browserFetch<GenericMap>("/admin/overview")
      .then((value) => {
        setPayload(value);
        setError("");
      })
      .catch((err) => {
        setPayload(null);
        setError(err instanceof Error ? err.message : "Failed to load admin overview.");
      });
  }, []);

  const summary = (payload?.summary || {}) as GenericMap;
  const alerts = (payload?.alerts || []) as GenericMap[];
  const recentTraces = (payload?.recent_traces || []) as GenericMap[];
  const recentAuditEvents = (payload?.recent_audit_events || []) as GenericMap[];
  const isFirstRun =
    Number(summary.corpora_count || 0) === 0
    && Number(summary.source_count || 0) === 0
    && Number(summary.active_job_count || 0) === 0
    && recentTraces.length === 0
    && recentAuditEvents.length === 0;

  return (
    <div className="admin-dashboard">
      <section className="admin-dashboard-head">
        <h1>System Overview</h1>
        <p>Truthful health, queue, quality, and audit visibility for the enterprise admin workspace.</p>
      </section>

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="admin-stat-grid">
        <article className="admin-stat-card">
          <div className="admin-stat-head">
            <span className="material-symbols-outlined">folder_zip</span>
            <span>Live</span>
          </div>
          <h3>{formatMetric(summary.corpora_count)}</h3>
          <p>Active Corpora</p>
        </article>
        <article className="admin-stat-card">
          <div className="admin-stat-head">
            <span className="material-symbols-outlined">database</span>
            <span>Inventory</span>
          </div>
          <h3>{formatMetric(summary.source_count)}</h3>
          <p>Registered Sources</p>
        </article>
        <article className="admin-stat-card">
          <div className="admin-stat-head">
            <span className="material-symbols-outlined">work_history</span>
            <span>Queue</span>
          </div>
          <h3>{formatMetric(summary.active_job_count)}</h3>
          <p>Active Jobs</p>
        </article>
        <article className="admin-stat-card">
          <div className="admin-stat-head">
            <span className="material-symbols-outlined">verified</span>
            <span>{String(summary.latest_eval_kind || "No eval")}</span>
          </div>
          <h3>{summary.latest_eval_pass_rate === null || summary.latest_eval_pass_rate === undefined ? "Unavailable" : `${String(summary.latest_eval_pass_rate)}%`}</h3>
          <p>Last Eval Pass Rate</p>
        </article>
      </section>

      <section className="admin-content-grid">
        <div className="admin-traces-pane">
          <div className="admin-section-head">
            <h2>Recent Traces</h2>
            <Link href="/console/admin/traces" className="admin-inline-link">Open traces</Link>
          </div>
          <div className="admin-traces-table">
            {recentTraces.length ? (
              <table>
                <thead>
                  <tr>
                    <th>Request</th>
                    <th>Mode</th>
                    <th>Latency</th>
                    <th>Recorded</th>
                  </tr>
                </thead>
                <tbody>
                  {recentTraces.map((trace) => (
                    <tr key={String(trace.id)}>
                      <td>
                        <div className="admin-trace-intent">
                          <strong>{String(trace.request_id || trace.id)}</strong>
                          <span>{String(trace.fallback_reason || "No fallback recorded")}</span>
                        </div>
                      </td>
                      <td>{String(trace.retrieval_path || trace.resolved_mode || "hybrid")}</td>
                      <td>{formatMetric(trace.total_latency_ms, " ms")}</td>
                      <td>{formatTimestamp(trace.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="admin-empty-state">
                <span className="material-symbols-outlined">timeline</span>
                <strong>No traces recorded yet.</strong>
                <p>{isFirstRun ? "This is normal on a clean install. Retrieval traces will appear after the first search, chat question, or query-debug run." : "Retrieval traces will appear here after search or ask traffic flows through the system."}</p>
              </div>
            )}
          </div>
        </div>

        <aside className="admin-side-stack">
          {isFirstRun ? (
            <article className="admin-notification-card">
              <h3>First-Run Checklist</h3>
              <div className="admin-notification-list">
                <Link href="/console/admin/corpora" className="admin-action-link">
                  <strong>Create the first corpus</strong>
                  <span>Start the operator setup by defining at least one corpus for source placement.</span>
                </Link>
                <Link href="/console/admin/sources" className="admin-action-link">
                  <strong>Wait for the first source</strong>
                  <span>After a user upload, confirm the source record appears and eventually reaches an indexed ready state.</span>
                </Link>
                <Link href="/console/admin/traces" className="admin-action-link">
                  <strong>Generate a trace</strong>
                  <span>Ask a question or run query debug so retrieval traces become available for inspection.</span>
                </Link>
                <Link href="/console/admin/evals" className="admin-action-link">
                  <strong>Run the first eval</strong>
                  <span>Establish a baseline report after the first corpus and source setup is complete.</span>
                </Link>
              </div>
            </article>
          ) : null}

          <article className="admin-notification-card">
            <h3>System Alerts</h3>
            <div className="admin-notification-list">
              {alerts.length ? alerts.map((item) => (
                <Link key={`${String(item.title)}-${String(item.href)}`} href={String(item.href || "/console/admin")} className="admin-action-link">
                  <strong>{String(item.title)}</strong>
                  <span>{String(item.body)}</span>
                </Link>
              )) : (
                <div className="admin-empty-state">
                  <span className="material-symbols-outlined">verified</span>
                  <strong>No active alerts.</strong>
                  <p>{isFirstRun ? "This is normal on a clean install. Alerts will appear once there are failed jobs, missing eval baselines, or source-placement gaps to surface." : "The current overview contract does not see failed jobs, missing evals, or corpus-placement gaps right now."}</p>
                </div>
              )}
            </div>
          </article>

          <article className="admin-notification-card">
            <h3>Recent Audit Events</h3>
            <div className="admin-notification-list">
              {recentAuditEvents.length ? recentAuditEvents.map((event) => (
                <Link key={String(event.id)} href="/console/admin/audit-log" className="admin-action-link">
                  <strong>{String(event.action)}</strong>
                  <span>{`${String(event.actor_email || event.actor_external_user_id || "unknown actor")} • ${formatTimestamp(event.created_at)}`}</span>
                </Link>
              )) : (
                <div className="admin-empty-state">
                  <span className="material-symbols-outlined">receipt_long</span>
                  <strong>No audit events yet.</strong>
                  <p>{isFirstRun ? "This is normal before the first admin action. Profile, corpus, source, job, and eval changes will start building the audit trail once operators begin working." : "Admin-originated profile, corpus, source, job, and eval actions will appear here once they happen."}</p>
                </div>
              )}
            </div>
          </article>

          <article className="admin-notification-card">
            <h3>Operator Quick Actions</h3>
            <div className="admin-notification-list">
              <Link href="/console/admin/sources" className="admin-action-link">
                <strong>Inspect sources</strong>
                <span>Review source status, corpus placement, ACL groups, and reindex/enrichment actions.</span>
              </Link>
              <Link href="/console/admin/jobs" className="admin-action-link">
                <strong>Inspect jobs</strong>
                <span>Open the live ingestion and enrichment queue with timing and failure context.</span>
              </Link>
              <Link href="/console/admin/audit-log" className="admin-action-link">
                <strong>Review audit log</strong>
                <span>Inspect stored admin mutations with actor, action, and before/after context.</span>
              </Link>
            </div>
          </article>

          <article className="admin-notification-card">
            <h3>Approval Inbox</h3>
            <div className="admin-notification-list">
              <div className="admin-empty-state">
                <span className="material-symbols-outlined">approval</span>
                <strong>No approval queue wired yet.</strong>
                <p>This milestone keeps approvals as a truthful summary/stub only. Full approval workflows land in M15; for now, operators review jobs, access posture, and audit evidence directly.</p>
              </div>
            </div>
          </article>
        </aside>
      </section>
    </div>
  );
}
