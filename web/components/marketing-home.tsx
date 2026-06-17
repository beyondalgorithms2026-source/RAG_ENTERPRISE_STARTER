import { MaterialIcon } from "@/components/icons";
import Link from "next/link";
import { PublicFooter, PublicHeader } from "@/components/public-pages";

export function MarketingHome() {
  return (
    <div className="public-shell">
      <PublicHeader activeProduct />

      <main className="marketing-page">
        <section className="marketing-hero" id="product">
          <div className="marketing-copy">
            <div className="marketing-kicker">
              <MaterialIcon name="search_spark" />
              AI search
            </div>
            <h1>AI-powered Enterprise search</h1>
            <p>
              Glean-inspired enterprise console for grounded search, AI answers, uploads, corpus controls, and role-aware operations.
            </p>
            <div className="marketing-actions">
              <Link href="/get-a-demo" className="stitch-button stitch-button-primary">
                Get a Demo
              </Link>
              <Link href="/watch-video-tour" className="stitch-button stitch-button-secondary stitch-button-with-icon">
                <MaterialIcon name="play_circle" />
                Watch Video
              </Link>
            </div>
            <div className="marketing-chip-row">
              <span><i /> SSO-first</span>
              <span><i /> Traceable retrieval</span>
              <span><i /> ACL-safe citations</span>
              <span><i /> Admin-operable control plane</span>
            </div>
          </div>

          <div className="marketing-preview-wrap">
            <div className="marketing-preview-card">
              <div className="marketing-browser-top">
                <div className="marketing-browser-dots">
                  <span />
                  <span />
                  <span />
                </div>
                <div className="marketing-browser-security">
                  <MaterialIcon name="security" />
                  Encrypted Workspace
                </div>
              </div>
              <div className="marketing-preview-thread">
                <div className="marketing-preview-question">
                  <div className="marketing-preview-avatar">
                    <MaterialIcon name="person" />
                  </div>
                  <div className="marketing-preview-bubble">What changed in the vendor policy and who approved it?</div>
                </div>
                <div className="marketing-preview-answer">
                  <div className="marketing-ai-avatar">
                    <MaterialIcon name="auto_awesome" className="icon-fill" />
                  </div>
                  <div className="marketing-answer-card">
                    <div className="marketing-answer-eyebrow">AI Answer</div>
                    <p>
                      The vendor policy was updated to mandate <strong>SOC2 Type II</strong> certification for all SaaS partners. This change was approved by <strong>Sarah Jenkins (CISO)</strong> on Oct 12, 2023.
                    </p>
                    <div className="marketing-answer-grid">
                      <div>
                        <span>Evidence</span>
                        <strong>policy_v2.pdf</strong>
                      </div>
                      <div>
                        <span>Source</span>
                        <strong>Sharepoint/Legal</strong>
                      </div>
                      <div>
                        <span>Status</span>
                        <strong>Verified</strong>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="marketing-preview-tags">
                  <span className="is-lime">Governance: ACL-High</span>
                  <span>Retrieved: 0.2s</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="marketing-feature-section" id="solutions">
          <div className="marketing-feature-head">
            <span>Capabilities</span>
            <h2>The new standard for retrieval teams.</h2>
          </div>

          <div className="marketing-feature-grid">
            <article className="marketing-feature-card marketing-feature-card-wide">
              <span className="marketing-feature-index">01</span>
              <h3>Grounded Answers</h3>
              <p>No hallucinations. Every response is generated exclusively from your indexed corpora with direct citations to original source documents.</p>
              <div className="marketing-feature-mock-row">
                <div />
                <div />
                <div />
                <div />
              </div>
            </article>

            <article className="marketing-feature-card marketing-feature-card-soft">
              <span className="marketing-feature-index">02</span>
              <h3>Governance Built In</h3>
              <p>Inherit permissions from Google, Microsoft, and Notion automatically. Users only see what they have access to.</p>
              <div className="marketing-progress-stack">
                <div><span /></div>
                <div><span className="is-medium" /></div>
                <div><span className="is-long" /></div>
              </div>
            </article>

            <article className="marketing-feature-card marketing-feature-card-elevated">
              <div className="marketing-feature-copy">
                <span className="marketing-feature-index">03</span>
                <h3>One Console For Users And Operators</h3>
                <p>Search is for everyone; management is for you. Switch between employee search views and powerful administrative corpus controls in one interface.</p>
                <Link href="/login" className="marketing-inline-link">
                  Explore Admin View
                  <MaterialIcon name="arrow_forward" />
                </Link>
              </div>
              <div className="marketing-health-card">
                <div className="marketing-health-head">
                  <span>System Health</span>
                  <span className="marketing-live-pill">Live</span>
                </div>
                <div className="marketing-health-row">
                  <span>Retrieval Latency</span>
                  <strong>142ms</strong>
                </div>
                <div className="marketing-health-row">
                  <span>Index Freshness</span>
                  <strong>2m ago</strong>
                </div>
                <div className="marketing-health-row">
                  <span>Active Connectors</span>
                  <strong>14/14</strong>
                </div>
              </div>
            </article>
          </div>
        </section>

        <section className="marketing-cta-band">
          <div className="marketing-cta-blur marketing-cta-blur-right" />
          <div className="marketing-cta-blur marketing-cta-blur-left" />
          <h2>Ready to ground your enterprise AI?</h2>
          <p>Deploy in your VPC or use our managed cloud. SOC2 Type II, GDPR, and HIPAA compliant.</p>
          <div className="marketing-actions">
            <Link href="/login" className="stitch-button stitch-button-white">
              Open Console Login
            </Link>
            <Link href="/get-a-demo" className="stitch-button stitch-button-outline-light">
              Request Access
            </Link>
          </div>
        </section>
      </main>

      <PublicFooter />
    </div>
  );
}
