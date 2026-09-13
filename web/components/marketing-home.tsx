import { MaterialIcon } from "@/components/icons";
import { PublicFooter, PublicHeader } from "@/components/public-pages";
import Link from "next/link";

const starterQuestions = [
  "What is the cash-advance limit and clearance deadline?",
  "Who may lead a Major or Critical incident?",
  "When is Security review required for a software pilot?",
  "What is the password-length requirement?",
];

export function MarketingHome() {
  return (
    <div className="public-shell">
      <PublicHeader activeProduct />

      <main className="marketing-page">
        <section className="marketing-hero" id="product">
          <div className="marketing-copy">
            <div className="marketing-kicker">
              <MaterialIcon name="search_spark" />
              Governed retrieval demonstration
            </div>
            <h1>Ask synthetic enterprise documents. Inspect the evidence.</h1>
            <p>
              A working three-repository RAG system with PostgreSQL/pgvector retrieval,
              SQL-level document authorization, citations, recovery, evaluation, and
              explicit refusal behavior.
            </p>
            <div className="marketing-actions">
              <Link href="/login" className="stitch-button stitch-button-primary">
                Open the demo console
              </Link>
              <Link href="/status" className="stitch-button stitch-button-secondary">
                View measured status
              </Link>
            </div>
            <div className="marketing-chip-row">
              <span><i /> Synthetic data only</span>
              <span><i /> Source-backed answers</span>
              <span><i /> SQL ACL boundary</span>
              <span><i /> Public evaluation evidence</span>
            </div>
          </div>

          <div className="marketing-preview-wrap">
            <div className="marketing-preview-card">
              <div className="marketing-browser-top">
                <div className="marketing-browser-dots"><span /><span /><span /></div>
                <div className="marketing-browser-security">
                  <MaterialIcon name="security" />
                  Synthetic Northwind corpus
                </div>
              </div>
              <div className="marketing-preview-thread">
                <div className="marketing-preview-question">
                  <div className="marketing-preview-avatar"><MaterialIcon name="person" /></div>
                  <div className="marketing-preview-bubble">
                    What is the cash-advance limit and clearance deadline?
                  </div>
                </div>
                <div className="marketing-preview-answer">
                  <div className="marketing-ai-avatar">
                    <MaterialIcon name="auto_awesome" className="icon-fill" />
                  </div>
                  <div className="marketing-answer-card">
                    <div className="marketing-answer-eyebrow">Source-backed example</div>
                    <p>
                      Cash advances are limited to <strong>€300 per employee</strong> and
                      must be cleared within <strong>10 Working Days</strong> after the trip.
                    </p>
                    <div className="marketing-answer-grid">
                      <div><span>Evidence</span><strong>Operations Manual §2.4</strong></div>
                      <div><span>Corpus</span><strong>Public synthetic demo</strong></div>
                      <div><span>Claim type</span><strong>Document fact</strong></div>
                    </div>
                  </div>
                </div>
                <div className="marketing-preview-tags">
                  <span className="is-lime">Illustrative answer</span>
                  <span>Verify in the live console</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="marketing-feature-section" id="solutions">
          <div className="marketing-feature-head">
            <span>Measured proof</span>
            <h2>Approved quality and live runtime are reported separately.</h2>
          </div>
          <div className="marketing-feature-grid">
            <article className="marketing-feature-card marketing-feature-card-wide">
              <span className="marketing-feature-index">01</span>
              <h3>Approved baseline v1</h3>
              <p>
                The current approved full-stack snapshot records 25/25 cases, 5/5
                required refusals, and a passing live RT-06 denied/authorized control.
                The 90-case v2 suite is not presented as approved until calibration ends.
              </p>
              <a
                href="https://beyondalgorithms2026-source.github.io/RAG_ENTERPRISE_LANGGRAPH_APP/evaluation/"
                className="marketing-inline-link"
              >
                Inspect the published evidence <MaterialIcon name="arrow_forward" />
              </a>
            </article>

            <article className="marketing-feature-card marketing-feature-card-soft">
              <span className="marketing-feature-index">02</span>
              <h3>Operations Manual v3.2</h3>
              <p>
                Source 28 is a fictional, public demonstration manual effective
                1 September 2026. It contains no real company, employee, customer, or
                private data and is parsed with the production Markdown pipeline.
              </p>
            </article>

            <article className="marketing-feature-card marketing-feature-card-elevated">
              <div className="marketing-feature-copy">
                <span className="marketing-feature-index">03</span>
                <h3>Live runtime metrics</h3>
                <p>
                  The status page reads a sanitized 24-hour endpoint. It shows sample
                  size and readiness before interpreting latency, cost, or recovery.
                </p>
                <Link href="/status" className="marketing-inline-link">
                  Open runtime status <MaterialIcon name="arrow_forward" />
                </Link>
              </div>
              <div className="marketing-health-card">
                <div className="marketing-health-head">
                  <span>Measurement rules</span>
                  <span className="marketing-live-pill">No sample values</span>
                </div>
                <div className="marketing-health-row"><span>Window</span><strong>24 hours</strong></div>
                <div className="marketing-health-row"><span>Minimum sample</span><strong>5 queries</strong></div>
                <div className="marketing-health-row"><span>Cache</span><strong>60 seconds</strong></div>
              </div>
            </article>
          </div>
        </section>

        <section className="marketing-feature-section">
          <div className="marketing-feature-head">
            <span>Starter questions</span>
            <h2>Begin with facts that have deterministic source truth.</h2>
          </div>
          <div className="marketing-feature-grid">
            {starterQuestions.map((question, index) => (
              <article className="marketing-feature-card" key={question}>
                <span className="marketing-feature-index">{String(index + 1).padStart(2, "0")}</span>
                <h3>{question}</h3>
                <p>Ask this in the console and inspect the cited section and evidence.</p>
              </article>
            ))}
          </div>
        </section>

        <section className="marketing-cta-band">
          <h2>Explore the system as a demonstration, not a compliance claim.</h2>
          <p>
            Capabilities and measurements shown here are limited to the checked-in
            synthetic corpus and the currently configured deployment.
          </p>
          <div className="marketing-actions">
            <Link href="/login" className="stitch-button stitch-button-white">
              Open console login
            </Link>
            <Link href="/status" className="stitch-button stitch-button-outline-light">
              Review status
            </Link>
          </div>
        </section>
      </main>

      <PublicFooter />
    </div>
  );
}
