import Link from "next/link";

function PublicHeader({ activeProduct = false }: { activeProduct?: boolean }) {
  return (
    <header className="public-header">
      <div className="public-header-inner">
        <div className="public-header-left">
          <Link href="/" className="public-brand">
            RAG Enterprise
          </Link>
          <nav className="public-nav-links">
            <a className={activeProduct ? "is-active" : undefined} href="#product">
              Product
            </a>
            <a href="#solutions">Solutions</a>
            <a href="#docs">Docs</a>
            <a href="#pricing">Pricing</a>
          </nav>
        </div>
        <div className="public-header-actions">
          <Link href="/login" className="public-login-link">
            Console Login
          </Link>
          <Link href="/get-a-demo" className="stitch-button stitch-button-primary stitch-button-small">
            Register
          </Link>
        </div>
      </div>
    </header>
  );
}

function PublicFooter({ compact = false }: { compact?: boolean }) {
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
          <a href="#privacy">Privacy</a>
          <a href="#terms">Terms</a>
          <a href="#security">Security</a>
          <a href="#status">Status</a>
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
                <span key={index} className="material-symbols-outlined icon-fill">
                  star
                </span>
              ))}
            </div>
            <blockquote>
              "RAG Enterprise has transformed how our retrieval teams access cross-functional data, cutting our hallucination rates by nearly 40%."
            </blockquote>
            <div className="demo-quote-author">
              <img
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuCfeat5KrjH9euP2bwb6M7b9vdkM4G3VuGQZ0yJXX8DKrTNS0rJuDDW35MgRnL17eP6MPejOMSST29ySfGdc46QNPrjYnapGsRxGKP4_JZ4oM0z_m2rvpMoauW9sX7RTKJgmWPltfVGFfi_a6YhA6ErOUXSCR7BBROknxPp_nongwWCmIO-WYoeAkbIe_dVWUw2g7Ac3ntfQZOHlBdsbCti-WaS-pTVqiKIFd7x29z3AEZ5rw06D11bS32GXQepLbi5vISJ5JDSJbE"
                alt="Chief Data Officer portrait"
              />
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
            <form className="demo-form" action="#">
              <div className="demo-form-grid">
                <label>
                  <span>First name</span>
                  <input placeholder="John" />
                </label>
                <label>
                  <span>Last name</span>
                  <input placeholder="Doe" />
                </label>
              </div>
              <label>
                <span>Work email</span>
                <input placeholder="john@company.com" type="email" />
              </label>
              <div className="demo-form-grid">
                <label>
                  <span>Company</span>
                  <input placeholder="Acme Corp" />
                </label>
                <label>
                  <span>Company Size</span>
                  <select defaultValue="1-50 employees">
                    <option>1-50 employees</option>
                    <option>51-250 employees</option>
                    <option>251-1000 employees</option>
                    <option>1000+ employees</option>
                  </select>
                </label>
              </div>
              <label>
                <span>Country</span>
                <select defaultValue="United States">
                  <option>United States</option>
                  <option>United Kingdom</option>
                  <option>Germany</option>
                  <option>Singapore</option>
                  <option>Other</option>
                </select>
              </label>
              <label>
                <span>What sparked your interest?</span>
                <textarea placeholder="Tell us about your retrieval challenges..." rows={4} />
              </label>
              <button type="button" className="stitch-button stitch-button-primary stitch-button-block">
                Submit Request
              </button>
              <p className="demo-form-note">
                By submitting this form, you agree to our <a href="#privacy">Privacy Policy</a>
              </p>
            </form>
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
      <PublicHeader activeProduct />
      <main className="video-page">
        <section className="video-hero">
          <span className="video-announcement">
            <span className="material-symbols-outlined icon-fill">bolt</span>
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
                <span className="material-symbols-outlined">lock</span>
                rag-enterprise.ai/walkthrough
              </div>
            </div>
            <div className="video-player-stage">
              <img
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuDuE0xXq0Ra72GXBBm4WEAO0ZDMbKw_-N75lyPiojP3Jub933ARZ5WffhfhfN-ZA-HqOZxShJzjnXb5cDQDEWqgMn-A4USTEJ5YXxFDeKR560kzi3YSSCCjDG71Xe3kWGQjC3Dksq0yMWkb4AzG24G8OVw7ZvcOcM0DzZS_DCFl3xwGaPReNgrn7uobkDGwMt1iNcjI-z40iz5IZI1sEIRxFryl_WQlfL-33Om4hMHBmIh1ewbDCidMsJql6XrEKHEreqnOo1apeE0"
                alt="Dashboard display"
              />
              <button type="button" className="video-play-button">
                <span className="material-symbols-outlined icon-fill">play_arrow</span>
              </button>
              <div className="video-progress">
                <span>02:45 / 04:20</span>
                <div className="video-progress-bar">
                  <div />
                </div>
                <span className="material-symbols-outlined">fullscreen</span>
              </div>
            </div>
            <div className="video-floating-chip video-floating-left">
              <div className="video-floating-head">
                <div className="video-floating-icon">
                  <span className="material-symbols-outlined">chat</span>
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
              <span className="material-symbols-outlined icon-fill">verified_user</span>
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
            <button type="button" className="video-inline-link">
              View all 120+ integrations
              <span className="material-symbols-outlined">arrow_forward</span>
            </button>
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
                <span className="material-symbols-outlined">{icon}</span>
                <p>{label}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="video-feature-grid">
          <article className="video-feature-card video-feature-card-wide">
            <div className="video-feature-icon">
              <span className="material-symbols-outlined">search_insights</span>
            </div>
            <h3>Semantic Context Discovery</h3>
            <p>
              Our RAG engine doesn't just look for words; it understands the intent behind your query and finds the most relevant passage across millions of files.
            </p>
            <div className="video-avatar-row">
              <div className="video-avatar-stack">
                <img
                  src="https://lh3.googleusercontent.com/aida-public/AB6AXuBq3cRxRyQKuzdvjZzDNu7lLM5EZZPsVv_Nk6hXtBX5rk3p-zez8_H9_aQrDhkjiWWIJFydUoiFwKWBNmVbCiQNHsbqZq6Kevw2KErmDrwV3WcFqnQzfS_7-gMcS8RKlu9gd5g3zMpcmPqQNh3ujKVaAhkbEmIDWpbH0N_sDb_Qf4l51nx1rcCNQHr70-xRlad7CE_AHla5Wi2-IcrxlHYmW2XeHAHf5EiLIqBrL-qUG0OSlsNzoBZc_Qp7J5Vpr0ZoOHx4RvGuGys"
                  alt="Trusted team member"
                />
                <img
                  src="https://lh3.googleusercontent.com/aida-public/AB6AXuBgqEen8MQEpr1bv5oOh-3UKuqBllrb9QKwcGzpU_kiSHUEqZJO3I_71_i1ew5R342Xehx2edX6L3dPO8YyUy9c59uAxKuqQgDuFh8Kdueat6LG652b6o__v5zu_z_MWx7a3esXlGUlJ31LFJe4-U1fGHyMyiNpZOz7zIjJ-_8bti4VqOtAlR-QL0slUcMh6RdJBUv0lSdx-esARDhfGFk3r_xWhPPihFAmY42zOj-wsHfzxiYzkVhLzlRgjVQ2ccTqCF86eBHPMdY"
                  alt="Trusted team member"
                />
                <img
                  src="https://lh3.googleusercontent.com/aida-public/AB6AXuD03NNZJ9dUcaubLVHxeahjPyN_nxpYHDLgVhusHGzkwPcBesPUpECIsFW-oAIx60ASWmU7-fcOXvw50eFt5VFBDalnuCVlJ2KTxYA0WbdBbMJ1jUzZbk9GOJW1PLe5QABREkzmFZa22XEXke1-irO3XY3xAwaXrS5YpM1m0_DePJ_-fBIaIjWuILVAA7HUhVObAESlOfjf3_1muUYVYg7v5-LKoieUhUgMHeQs-GJ_DOLRyxqk18E96XUX8l_iTDqnGm3b1ZqyA_4"
                  alt="Trusted team member"
                />
              </div>
              <span>Trusted by 500+ Engineering Teams</span>
            </div>
          </article>
          <article className="video-feature-card video-feature-card-lime">
            <span className="material-symbols-outlined icon-fill">security</span>
            <h3>Enterprise Security</h3>
            <p>SOC2 Type II compliant. Your data is encrypted at rest and never used for training foundation models.</p>
          </article>
          <article className="video-feature-card video-feature-card-primary">
            <span className="material-symbols-outlined icon-fill">bolt</span>
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
                <span className="material-symbols-outlined">link</span>
                policy_v2.pdf
              </div>
            </div>
          </article>
        </section>

        <section className="video-final-cta">
          <h2>Ready to unify your enterprise knowledge?</h2>
          <div className="video-final-actions">
            <button type="button" className="stitch-button stitch-button-primary">
              Start Free Trial
            </button>
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
