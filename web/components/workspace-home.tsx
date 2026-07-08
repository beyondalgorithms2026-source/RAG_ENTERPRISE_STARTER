"use client";

import { MaterialIcon } from "@/components/icons";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { browserApiUrl, browserFetch } from "@/lib/api-browser";
import { readThreads, THREADS_UPDATED_EVENT, type ThreadRecord } from "@/lib/workspace";

type HealthPayload = {
  status?: string;
  retrieval_defaults?: { mode?: string; rerank_enabled?: boolean };
  corpus?: { total_sources?: number; embedded_sources?: number };
};

type NotificationItem = {
  id: number;
  event_type: string;
  title: string;
  body: string;
  status: string;
  created_at?: string | null;
};

function formatTime(value?: string | null) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function eventGlyph(eventType: string) {
  const value = eventType.toLowerCase();
  if (value.includes("grant") || value.includes("approve")) return "check";
  if (value.includes("deny") || value.includes("expir")) return "warning";
  if (value.includes("route")) return "swap_horiz";
  return "notifications";
}

/**
 * V2 governed-answers home: query-first entry, live governance posture, the
 * committed eval baseline, and the user's own workflow state (threads,
 * approvals, events). Everything except the labelled eval baseline is live
 * backend or local-thread data.
 */
export function WorkspaceHome() {
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [healthFailed, setHealthFailed] = useState(false);
  const [threads, setThreads] = useState<ThreadRecord[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[] | null>(null);
  const [pendingApprovals, setPendingApprovals] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(browserApiUrl("/health"))
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then((payload: HealthPayload) => {
        if (!cancelled) setHealth(payload);
      })
      .catch(() => {
        if (!cancelled) setHealthFailed(true);
      });
    browserFetch<{ notifications: NotificationItem[] }>("/me/notifications")
      .then((payload) => {
        if (!cancelled) setNotifications(payload.notifications);
      })
      .catch(() => {
        if (!cancelled) setNotifications([]);
      });
    browserFetch<{ approvals: { status: string }[] }>("/me/approvals")
      .then((payload) => {
        if (!cancelled) setPendingApprovals(payload.approvals.filter((item) => item.status === "pending").length);
      })
      .catch(() => {
        if (!cancelled) setPendingApprovals(0);
      });

    function refreshThreads() {
      setThreads(readThreads().slice(0, 4));
    }
    refreshThreads();
    window.addEventListener(THREADS_UPDATED_EVENT, refreshThreads);
    return () => {
      cancelled = true;
      window.removeEventListener(THREADS_UPDATED_EVENT, refreshThreads);
    };
  }, []);

  function ask(target: "chat" | "search") {
    const value = question.trim();
    if (!value) return;
    router.push(`/console/workspace/${target === "chat" ? "chat" : "search"}?q=${encodeURIComponent(value)}`);
  }

  const totalSources = health?.corpus?.total_sources;
  const retrievalMode = health?.retrieval_defaults?.mode;
  const recentEvents = (notifications ?? []).slice(0, 6);

  return (
    <div className="v2-page">
      <section className="v2-hero" aria-label="Ask a governed question">
        <p className="v2-kicker">Governed answers workspace</p>
        <h1>Every answer cited. Every access checked. Every step traced.</h1>
        <form
          className="v2-hero-composer"
          onSubmit={(event) => {
            event.preventDefault();
            ask("chat");
          }}
        >
          <MaterialIcon name="search" />
          <input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="e.g. What is the rent escalation clause in the 2024 lease?"
            aria-label="Question"
          />
          <div className="v2-hero-actions">
            <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" onClick={() => ask("search")} disabled={!question.trim()}>
              Search
            </button>
            <button type="submit" className="stitch-button stitch-button-primary stitch-button-small" disabled={!question.trim()}>
              Ask
              <MaterialIcon name="send" />
            </button>
          </div>
        </form>
        <div className="v2-chip-row" aria-label="Governance posture">
          <span className="v2-chip is-on" title="Access trimming is composed into every retrieval SQL query.">
            <MaterialIcon name="shield_check" />
            SQL-level ACL
          </span>
          <span className="v2-chip is-on" title="Uncited answers are refused; safe not-found beats a made-up answer.">
            <MaterialIcon name="fact_check" />
            Citations required
          </span>
          <span className="v2-chip is-on" title="Routing, fusion, rerank, and recovery decisions land in inspectable traces.">
            <MaterialIcon name="timeline" />
            Fully traced
          </span>
          {healthFailed ? (
            <span className="v2-chip is-alert" role="status">
              <MaterialIcon name="warning" />
              Backend unreachable
            </span>
          ) : health ? (
            <span className="v2-chip is-on" role="status" title={`Default retrieval: ${retrievalMode || "—"}`}>
              <MaterialIcon name="check" />
              {typeof totalSources === "number" ? `${totalSources} sources indexed` : "Backend healthy"}
            </span>
          ) : (
            <span className="v2-chip is-wait" role="status">
              <MaterialIcon name="progress_activity" className="spin" />
              Checking backend
            </span>
          )}
        </div>
      </section>

      <section className="v2-metric-row" aria-label="Retrieval quality baseline">
        <header className="v2-row-head">
          <h2>Retrieval quality baseline</h2>
          <span className="v2-row-note">Committed flagship eval-pack baseline · <Link href="/console/workspace/trust">open Trust dashboard</Link></span>
        </header>
        <div className="v2-metric-grid">
          <article className="v2-metric-card">
            <span className="v2-metric-label">Recall@5</span>
            <strong>0.505</strong>
            <span className="v2-metric-note">400 graded cases</span>
          </article>
          <article className="v2-metric-card">
            <span className="v2-metric-label">MRR</span>
            <strong>0.850</strong>
            <span className="v2-metric-note">first-relevant rank</span>
          </article>
          <article className="v2-metric-card">
            <span className="v2-metric-label">nDCG@10</span>
            <strong>0.766</strong>
            <span className="v2-metric-note">ranking quality</span>
          </article>
          <article className="v2-metric-card">
            <span className="v2-metric-label">Eval gate</span>
            <strong className="v2-metric-good">Pass</strong>
            <span className="v2-metric-note">degraded control fails</span>
          </article>
        </div>
      </section>

      <div className="v2-columns">
        <section className="v2-panel" aria-label="Recent threads">
          <header className="v2-panel-head">
            <h2>Pick up where you left off</h2>
            <Link href="/console/workspace/history">All history</Link>
          </header>
          {threads.length === 0 ? (
            <div className="v2-empty">
              <MaterialIcon name="forum" />
              <strong>No threads yet.</strong>
              <p>Ask your first question above — the thread and its cited evidence will appear here.</p>
            </div>
          ) : (
            <div className="v2-thread-list">
              {threads.map((thread) => {
                const answers = thread.messages.filter((message) => message.role === "assistant");
                const citations = answers.reduce((sum, message) => sum + (message.citations?.length ?? 0), 0);
                return (
                  <Link key={thread.id} href={`/console/workspace/chat/${thread.id}`} className="v2-thread-card">
                    <strong>{thread.title}</strong>
                    <span>
                      {answers.length} answer{answers.length === 1 ? "" : "s"} · {citations} citation{citations === 1 ? "" : "s"} · {formatTime(thread.createdAt)}
                    </span>
                  </Link>
                );
              })}
            </div>
          )}
        </section>

        <section className="v2-panel" aria-label="Governance workflow">
          <header className="v2-panel-head">
            <h2>Workflow</h2>
            <Link href="/console/workspace/requests">Approval gate</Link>
          </header>
          <Link href="/console/workspace/requests" className="v2-workflow-summary">
            <MaterialIcon name="approval" />
            <div>
              <strong>
                {pendingApprovals === null ? "Checking approvals..." : pendingApprovals === 0 ? "No reviews waiting on you" : `${pendingApprovals} review${pendingApprovals === 1 ? "" : "s"} waiting on you`}
              </strong>
              <span>Routed business approvals with reviewer notes and timed grants.</span>
            </div>
          </Link>
          {notifications === null ? (
            <div className="v2-empty" role="status">
              <MaterialIcon name="progress_activity" className="spin" />
              <strong>Loading workflow events...</strong>
            </div>
          ) : recentEvents.length === 0 ? (
            <div className="v2-empty">
              <MaterialIcon name="notifications_off" />
              <strong>No workflow events yet.</strong>
              <p>Access routing, approvals, grants, and expiries will appear here as a timestamped feed.</p>
            </div>
          ) : (
            <ol className="v2-timeline">
              {recentEvents.map((item) => (
                <li key={item.id} className="v2-timeline-item">
                  <span className={`v2-timeline-dot ${item.status !== "read" ? "is-unread" : ""}`} aria-hidden="true">
                    <MaterialIcon name={eventGlyph(item.event_type)} />
                  </span>
                  <div>
                    <strong>{item.title}</strong>
                    <p>{item.body}</p>
                    <span className="v2-timeline-time">{formatTime(item.created_at)}</span>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </div>
  );
}
