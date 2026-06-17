import { BrandLogo, MaterialIcon, Monogram } from "@/components/icons";
import Link from "next/link";

export function PublicHeader({ activeProduct = false }: { activeProduct?: boolean }) {
  return (
    <header className="public-header">
      <div className="public-header-inner">
        <div className="public-header-left">
          <Link href="/" className="public-brand">
            <BrandLogo />
            <span>RAG Enterprise</span>
          </Link>
          <nav className="public-nav-links">
            <Link className={activeProduct ? "is-active" : undefined} href="/">
              Product
            </Link>
            <Link href="/watch-video-tour">Solutions</Link>
          </nav>
        </div>
        <div className="public-header-actions">
          <Link href="/login" className="public-login-link">
            Console Login
          </Link>
          <Link href="/get-a-demo" className="stitch-button stitch-button-primary stitch-button-small">
            Request Access
          </Link>
        </div>
      </div>
    </header>
  );
}

export function PublicFooter({ compact = false }: { compact?: boolean }) {
  return (
    <footer className={`public-footer ${compact ? "is-compact" : ""}`}>
      <div className="public-footer-inner">
        <div className="public-footer-brand">
          {compact ? "© 2024 RAG ENTERPRISE. Built for enterprise retrieval teams." : (
            <>
              <span className="public-brand">RAG Enterprise</span>
              <p>Built for enterprise retrieval teams</p>
            </>
          )}
        </div>
        <div className="public-footer-links">
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
          <Link href="/security">Security</Link>
          <Link href="/status">Status</Link>
        </div>
      </div>
      {compact ? null : <div className="public-footer-copy">© 2024 RAG Enterprise. All Rights Reserved.</div>}
    </footer>
  );
}

export function DemoPage() {
  return (
    <div className="public-shell">
      <PublicHeader />
      <main className="demo-layout">
        <section className="demo-hero">
          <div className="demo-hero-content">
            <span className="demo-kicker">Enterprise AI Retrieval</span>
            <h1>Put AI to work. At work.</h1>
            <p>
              The unified knowledge layer that powers enterprise-grade RAG. Connect your data, evaluate your models, and deploy at scale.
            </p>
          </div>
          <div className="demo-quote-card">
            <div className="demo-stars">
              {Array.from({ length: 5 }).map((_, index) => (
                <MaterialIcon key={index} name="star" className="icon-fill" />
              ))}
            </div>
            <blockquote>
              "RAG Enterprise has transformed how our retrieval teams access cross-functional data, cutting our hallucination rates by nearly 40%."
            </blockquote>
            <div className="demo-quote-author">
              <Monogram seed="Chief Data Officer" />
              <div>
                <strong>Chief Data Officer</strong>
                <span>Booking.com</span>
              </div>
            </div>
          </div>
        </section>
        <section className="demo-form-panel">
          <div className="demo-form-inner">
            <div className="demo-form-head">
              <h2>Request a Personalized Demo</h2>
              <p>See how our platform fits your specific enterprise architecture.</p>
            </div>
            <div className="demo-form">
              <div className="demo-form-grid">
                <label>
                  <span>First name</span>
                  <input placeholder="John" disabled />
                </label>
                <label>
                  <span>Last name</span>
                  <input placeholder="Doe" disabled />
                </label>
              </div>
              <label>
                <span>Work email</span>
                <input placeholder="john@company.com" type="email" disabled />
              </label>
              <div className="demo-form-grid">
                <label>
                  <span>Company</span>
                  <input placeholder="Acme Corp" disabled />
                </label>
                <label>
                  <span>Company Size</span>
                  <select defaultValue="1-50 employees" disabled>
                    <option>1-50 employees</option>
                    <option>51-250 employees</option>
                    <option>251-1000 employees</option>
                    <option>1000+ employees</option>
                  </select>
                </label>
              </div>
              <label>
                <span>Country</span>
                <select defaultValue="United States" disabled>
                  <option>United States</option>
                  <option>United Kingdom</option>
                  <option>Germany</option>
                  <option>Singapore</option>
                  <option>Other</option>
                </select>
              </label>
              <label>
                <span>What sparked your interest?</span>
                <textarea placeholder="Tell us about your retrieval challenges..." rows={4} disabled />
              </label>
              <Link href="/login" className="stitch-button stitch-button-primary stitch-button-block">
                Open Console Login
              </Link>
              <p className="demo-form-note">
                This repository does not include a live CRM-backed demo intake flow. Use Console Login for local validation or request access through your enterprise onboarding path. Review our <Link href="/privacy">Privacy Policy</Link>.
              </p>
            </div>
          </div>
        </section>
      </main>
      <PublicFooter compact />
    </div>
  );
}

export function VideoTourPage() {
  return (
    <div className="public-shell">
      <PublicHeader />
      <main className="video-page">
        <section className="video-hero">
          <span className="video-announcement">
            <MaterialIcon name="bolt" className="icon-fill" />
            New Feature: Universal Semantic Search
          </span>
          <h1>
            Instantly find documents <span>across your entire stack.</span>
          </h1>
          <p>
            Stop digging through Slack threads and buried Drive folders. RAG Enterprise connects your fragmented knowledge into a single, intelligent retrieval layer.
          </p>
          <div className="video-player-shell">
            <div className="video-browser-bar">
              <div className="video-browser-dots">
                <span />
                <span />
                <span />
              </div>
              <div className="video-browser-address">
                <MaterialIcon name="lock" />
                rag-enterprise.ai/walkthrough
              </div>
            </div>
            <div className="video-player-stage">
              <div className="media-placeholder" aria-hidden="true" />
              <button type="button" className="video-play-button" disabled title="Embedded video playback is not wired in this repo yet. Use the walkthrough page content or request a live demo.">
                <MaterialIcon name="play_arrow" className="icon-fill" />
              </button>
              <div className="video-progress">
                <span>02:45 / 04:20</span>
                <div className="video-progress-bar">
                  <div />
                </div>
                <MaterialIcon name="fullscreen" />
              </div>
            </div>
            <div className="video-floating-chip video-floating-left">
              <div className="video-floating-head">
                <div className="video-floating-icon">
                  <MaterialIcon name="chat" />
                </div>
                <div>
                  <strong>Slack Integration</strong>
                  <span>3,420 channels indexed</span>
                </div>
              </div>
              <div className="video-mini-bar">
                <div />
              </div>
            </div>
            <div className="video-floating-chip video-floating-right">
              <MaterialIcon name="verified_user" className="icon-fill" />
              <p>"The accuracy of the retrieval is unmatched by anything else we've tried."</p>
              <span>— CTO, Cloudscale</span>
            </div>
          </div>
        </section>

        <section className="video-section">
          <div className="video-section-head">
            <div>
              <h2>A unified brain for all your data</h2>
              <p>Direct integrations with over 100+ enterprise tools. No migration needed, just secure read-only access.</p>
            </div>
            <Link href="/get-a-demo" className="video-inline-link">
              Request integration walkthrough
              <MaterialIcon name="arrow_forward" />
            </Link>
          </div>
          <div className="video-connector-grid">
            {[
              ["drive_file_gmail", "Drive"],
              ["forum", "Slack"],
              ["description", "Notion"],
              ["bug_report", "Jira"],
              ["database", "PostgreSQL"],
              ["terminal", "GitHub"],
            ].map(([icon, label]) => (
              <article key={label} className="video-connector-card">
                <MaterialIcon name={icon} />
                <p>{label}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="video-feature-grid">
          <article className="video-feature-card video-feature-card-wide">
            <div className="video-feature-icon">
              <MaterialIcon name="search_insights" />
            </div>
            <h3>Semantic Context Discovery</h3>
            <p>
              Our RAG engine doesn't just look for words; it understands the intent behind your query and finds the most relevant passage across millions of files.
            </p>
            <div className="video-avatar-row">
              <div className="video-avatar-stack">
                <Monogram seed="Ava Mensah" />
                <Monogram seed="Liam Park" />
                <Monogram seed="Noah Reed" />
              </div>
              <span>Trusted by 500+ Engineering Teams</span>
            </div>
          </article>
          <article className="video-feature-card video-feature-card-lime">
            <MaterialIcon name="security" className="icon-fill" />
            <h3>Enterprise Security</h3>
            <p>SOC2 Type II compliant. Your data is encrypted at rest and never used for training foundation models.</p>
          </article>
          <article className="video-feature-card video-feature-card-primary">
            <MaterialIcon name="bolt" className="icon-fill" />
            <h3>Sub-second Latency</h3>
            <p>Global vector indexing ensures search results are delivered in under 200ms anywhere in the world.</p>
          </article>
          <article className="video-feature-card video-feature-card-wide video-feature-card-citation">
            <div>
              <h3>Citations & Provenance</h3>
              <p>Every AI-generated response includes direct links to the source documents, ensuring trust and verifiability.</p>
            </div>
            <div className="video-citation-preview">
              <div className="video-citation-line short" />
              <div className="video-citation-line" />
              <div className="video-citation-line accent" />
              <div className="video-citation-chip">
                <MaterialIcon name="link" />
                policy_v2.pdf
              </div>
            </div>
          </article>
        </section>

        <section className="video-final-cta">
          <h2>Ready to unify your enterprise knowledge?</h2>
          <div className="video-final-actions">
            <Link href="/login" className="stitch-button stitch-button-primary">
              Open Console Login
            </Link>
            <Link href="/get-a-demo" className="stitch-button stitch-button-secondary">
              Schedule a Demo
            </Link>
          </div>
        </section>
      </main>
      <PublicFooter compact />
    </div>
  );
}
