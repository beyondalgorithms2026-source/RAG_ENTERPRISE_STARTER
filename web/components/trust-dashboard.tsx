"use client";

import { MaterialIcon } from "@/components/icons";
import Link from "next/link";

/**
 * Trust & evaluation dashboard (user-facing). Live eval runs are admin-gated,
 * so this surface presents the committed flagship-pack baseline (real, from
 * the repo's eval evidence) plus a clearly-labelled sample run structure that
 * demonstrates the pass / fail / manual-review gate without claiming live
 * backend numbers.
 */

const BASELINE = [
  { label: "Recall@5", value: "0.505", note: "400 graded retrieval cases", icon: "manage_search" },
  { label: "Faithfulness", value: "Pass", note: "citation-grounded answers", icon: "fact_check", good: true },
  { label: "MRR", value: "0.850", note: "first relevant result rank", icon: "timeline" },
  { label: "nDCG@10", value: "0.766", note: "ranking quality", icon: "analytics" },
];

// Demo-safe sample distribution (labelled): shows the review workflow shape.
const SAMPLE_DISTRIBUTION = [
  { key: "pass", label: "Pass", count: 322, className: "is-pass" },
  { key: "manual", label: "Manual review", count: 41, className: "is-manual" },
  { key: "fail", label: "Fail", count: 37, className: "is-fail" },
];

const SAMPLE_RUNS = [
  { id: "run-014", scope: "Flagship pack · candidate profile", verdict: "pass", passRate: "84%", latency: "1.9s p50", cost: "$0.004/q", when: "Sample" },
  { id: "run-013", scope: "Flagship pack · live profile", verdict: "pass", passRate: "81%", latency: "2.1s p50", cost: "$0.004/q", when: "Sample" },
  { id: "run-012", scope: "Degraded control (gate check)", verdict: "fail", passRate: "48%", latency: "1.7s p50", cost: "$0.003/q", when: "Sample" },
];

export function TrustDashboard() {
  const total = SAMPLE_DISTRIBUTION.reduce((sum, part) => sum + part.count, 0);
  return (
    <div className="v2-page">
      <header className="v2-page-head">
        <div>
          <p className="v2-kicker">Trust &amp; evaluation</p>
          <h1>Answers are promoted only when the eval gate passes.</h1>
          <p className="v2-page-sub">
            Retrieval changes must beat a graded eval pack before promotion; degraded configurations are unpromotable by design.
            Feedback-derived cases stay quarantined until a human reviews them.
          </p>
        </div>
      </header>

      <section className="v2-metric-row" aria-label="Committed eval baseline">
        <header className="v2-row-head">
          <h2>Committed baseline</h2>
          <span className="v2-row-note">Flagship 400-case eval pack · committed evidence</span>
        </header>
        <div className="v2-metric-grid">
          {BASELINE.map((metric) => (
            <article key={metric.label} className="v2-metric-card">
              <span className="v2-metric-label">
                <MaterialIcon name={metric.icon} /> {metric.label}
              </span>
              <strong className={metric.good ? "v2-metric-good" : undefined}>{metric.value}</strong>
              <span className="v2-metric-note">{metric.note}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="v2-panel" aria-label="Case outcome distribution">
        <header className="v2-panel-head">
          <h2>Case outcomes</h2>
          <span className="v2-demo-chip" title="Illustrative structure — live per-run outcomes are produced by admin eval runs.">Sample data</span>
        </header>
        <div className="v2-dist-bar" role="img" aria-label={`Sample distribution: ${SAMPLE_DISTRIBUTION.map((part) => `${part.label} ${part.count}`).join(", ")}`}>
          {SAMPLE_DISTRIBUTION.map((part) => (
            <span key={part.key} className={`v2-dist-segment ${part.className}`} style={{ flexGrow: part.count }} />
          ))}
        </div>
        <div className="v2-dist-legend">
          {SAMPLE_DISTRIBUTION.map((part) => (
            <span key={part.key} className="v2-dist-key">
              <span className={`v2-dist-swatch ${part.className}`} aria-hidden="true" />
              {part.label} · {part.count} ({Math.round((part.count / total) * 100)}%)
            </span>
          ))}
        </div>
      </section>

      <section className="v2-panel" aria-label="Recent eval runs">
        <header className="v2-panel-head">
          <h2>Eval runs</h2>
          <span className="v2-demo-chip" title="Illustrative structure — live runs execute via the admin tuning console.">Sample data</span>
        </header>
        <div className="v2-run-list">
          {SAMPLE_RUNS.map((run) => (
            <article key={run.id} className="v2-run-card">
              <span className={`v2-status-chip ${run.verdict === "pass" ? "is-pass" : "is-fail"}`}>
                <MaterialIcon name={run.verdict === "pass" ? "check" : "close"} />
                {run.verdict === "pass" ? "Pass" : "Fail"}
              </span>
              <div className="v2-run-body">
                <strong>{run.scope}</strong>
                <span>
                  {run.passRate} pass rate · {run.latency} · {run.cost}
                </span>
              </div>
              <span className="v2-run-when">{run.when}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="v2-metric-row" aria-label="How the gate works">
        <header className="v2-row-head">
          <h2>How the gate works</h2>
        </header>
        <div className="v2-gate-grid">
          <article className="v2-gate-card">
            <MaterialIcon name="experiment" />
            <strong>Eval before promotion</strong>
            <p>Candidate retrieval profiles must post a fresh passing eval run before they can be promoted to live.</p>
          </article>
          <article className="v2-gate-card">
            <MaterialIcon name="lock" />
            <strong>Feedback quarantine</strong>
            <p>Cases proposed from user feedback never gate a promotion until a human reviews and labels them.</p>
          </article>
          <article className="v2-gate-card">
            <MaterialIcon name="shield_check" />
            <strong>Degraded control</strong>
            <p>A deliberately broken configuration is kept in the pack — if it ever passes, the gate itself is broken.</p>
          </article>
          <article className="v2-gate-card">
            <MaterialIcon name="timeline" />
            <strong>Traced decisions</strong>
            <p>Routing, rerank, recovery, and cache decisions land in traces reviewable from the admin console.</p>
          </article>
        </div>
        <p className="v2-footnote">
          Live eval runs, pass-rate trends, and cost governance run in the <Link href="/console/admin">admin console</Link> (admin role required).
        </p>
      </section>
    </div>
  );
}
