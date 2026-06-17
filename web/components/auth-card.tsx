import { MaterialIcon } from "@/components/icons";
import Link from "next/link";

import { buildLoginHref } from "@/lib/auth";
import { DevLoginForm } from "@/components/dev-login-form";

export function AuthCard({
  title,
  description,
  nextPath,
  secondaryHref,
  secondaryLabel,
  showDevLogin = false,
  devLoginPreferred = false,
  ssoAvailable = true,
  infoMessage,
}: {
  title: string;
  description: string;
  nextPath: string;
  secondaryHref: string;
  secondaryLabel: string;
  showDevLogin?: boolean;
  devLoginPreferred?: boolean;
  ssoAvailable?: boolean;
  infoMessage: string;
}) {
  const primaryHref = devLoginPreferred ? "#local-dev-login" : buildLoginHref(nextPath);
  const primaryLabel = devLoginPreferred ? "Continue With Local Dev Login" : "Continue With SSO";
  const devSummaryLabel = devLoginPreferred ? "Local Dev Login (Recommended For This Environment)" : "Local Dev Login";

  return (
    <main className="login-shell">
      <div className="login-background">
        <div className="login-background-orb login-background-left" />
        <div className="login-background-orb login-background-right" />
      </div>
      <div className="login-layout">
        <div className="login-brand-block">
          <span className="login-brand-kicker">Enterprise Console</span>
          <div className="login-brand-row">
            <div className="login-brand-mark">
              <MaterialIcon name="dataset" className="icon-fill" />
            </div>
            <span className="login-brand-name">RAG Enterprise</span>
          </div>
        </div>

        <section className="login-card">
          <div className="login-card-head">
            <h1>{title}</h1>
            <p>{description}</p>
          </div>
          <div className="login-card-actions">
            <a className="stitch-button stitch-button-primary stitch-button-block" href={primaryHref}>
              <MaterialIcon name="identity_platform" />
              {primaryLabel}
            </a>
            <Link className="stitch-button stitch-button-secondary stitch-button-block" href={secondaryHref}>
              {secondaryLabel}
            </Link>
            <Link className="stitch-button stitch-button-secondary stitch-button-block" href="/">
              Back To Homepage
            </Link>
          </div>
          <div className="login-note-card">
            <MaterialIcon name="info" />
            <p>{infoMessage}</p>
          </div>
        </section>

        {showDevLogin ? (
          <section className="login-dev-card" id="local-dev-login">
            <details open={devLoginPreferred}>
              <summary>
                <MaterialIcon name="code" />
                {devSummaryLabel}
              </summary>
              <DevLoginForm nextPath={nextPath} />
            </details>
          </section>
        ) : null}

        <footer className="login-footer-links">
          <Link href="/privacy">Privacy</Link>
          <span />
          <Link href="/terms">Terms</Link>
          <span />
          <Link href="/security">Security</Link>
        </footer>

        <div className="login-floating-art">
          <div className="media-placeholder" aria-hidden="true" />
        </div>
      </div>
    </main>
  );
}
