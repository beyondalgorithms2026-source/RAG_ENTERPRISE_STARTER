"use client";

import { BrandLogo, MaterialIcon, Monogram } from "@/components/icons";
import Link from "next/link";
import type { FormEvent, ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";

import { LogoutButton } from "@/components/logout-button";
import { groupAdminNav, type AdminNavItem } from "@/lib/admin-nav";
import { browserApiUrl } from "@/lib/api-browser";
import { hasAdminRole, type Viewer } from "@/lib/viewer";
import { useEffect, useRef, useState } from "react";

type NavItem = {
  href: string;
  label: string;
  icon: string;
  module?: string;
};

// Consistent "coming soon" treatment for controls that are intentionally not
// wired yet — preserved (not removed) so they can be implemented in a later
// release. See web/DESIGN.md (Coming-soon pattern).
const COMING_SOON_TITLE = "Coming in a later release.";
function comingSoonProps(name: string) {
  return { disabled: true, "aria-label": `${name} (coming soon)`, title: COMING_SOON_TITLE, "data-coming-soon": "true" } as const;
}

type HealthState = "checking" | "ok" | "degraded";

/** Live backend reachability chip fed by GET /health (no auth required). */
function useBackendHealth(enabled: boolean) {
  const [health, setHealth] = useState<HealthState>("checking");
  const [retrievalMode, setRetrievalMode] = useState<string>("");
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    fetch(browserApiUrl("/health"))
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then((payload: { status?: string; retrieval_defaults?: { mode?: string } }) => {
        if (cancelled) return;
        setHealth(payload.status === "ok" ? "ok" : "degraded");
        setRetrievalMode(payload.retrieval_defaults?.mode ?? "");
      })
      .catch(() => {
        if (!cancelled) setHealth("degraded");
      });
    return () => {
      cancelled = true;
    };
  }, [enabled]);
  return { health, retrievalMode };
}

export function ConsoleShell({
  viewer,
  navItems,
  variant,
  children,
}: {
  viewer: Viewer;
  navItems: NavItem[];
  variant: "workspace" | "admin";
  children: ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsedNavSections, setCollapsedNavSections] = useState<Record<string, boolean>>({});
  // Mobile nav drawer (≤820px): the nav column becomes a fixed overlay opened
  // by the topbar toggle. Closed on route change / Escape / backdrop click.
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState("");
  const sidebarRef = useRef<HTMLElement | null>(null);
  const adminNav = variant === "admin" ? groupAdminNav(navItems as AdminNavItem[]) : null;
  const { health, retrievalMode } = useBackendHealth(variant === "workspace");

  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (mobileNavOpen) sidebarRef.current?.focus();
  }, [mobileNavOpen]);

  useEffect(() => {
    if (!mobileNavOpen) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setMobileNavOpen(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [mobileNavOpen]);

  const viewerPrimary = viewer.name || viewer.email || viewer.user_id;
  const viewerSecondary = viewer.email || viewer.user_id;
  const viewerRoleLabel = viewer.roles.length ? viewer.roles.join(", ").toUpperCase() : "USER";

  const navToggleButton = (
    <button
      type="button"
      className="shell-nav-toggle"
      aria-expanded={mobileNavOpen}
      aria-label={mobileNavOpen ? "Close navigation" : "Open navigation"}
      onClick={() => setMobileNavOpen((open) => !open)}
    >
      <MaterialIcon name={mobileNavOpen ? "close" : "menu"} />
    </button>
  );
  const navBackdrop = mobileNavOpen ? (
    <button
      type="button"
      className="shell-nav-backdrop"
      aria-label="Close navigation"
      onClick={() => setMobileNavOpen(false)}
    />
  ) : null;

  if (variant === "admin") {
    return (
      <div className="admin-shell">
        <a href="#console-main" className="skip-link">Skip to content</a>
        {navBackdrop}
        <aside className={`admin-sidebar ${mobileNavOpen ? "is-mobile-open" : ""}`} ref={sidebarRef} tabIndex={-1}>
          <div className="admin-sidebar-head">
            <div className="brand-lockup">
              <BrandLogo />
              <h2>RAG Enterprise</h2>
            </div>
            <p>Admin Console</p>
          </div>
          <div className="admin-sidebar-scroll">
            <nav className="admin-sidebar-nav">
              {adminNav?.pinned.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`admin-sidebar-link ${pathname === item.href ? "is-active" : ""}`}
                >
                  <MaterialIcon name={item.icon} />
                  <span>{item.label}</span>
                </Link>
              ))}
              {adminNav?.sections.map((section) => {
                const collapsed = collapsedNavSections[section.key] ?? false;
                return (
                  <div key={section.key} className="admin-sidebar-group">
                    <button
                      type="button"
                      className="admin-sidebar-section"
                      aria-expanded={!collapsed}
                      onClick={() => setCollapsedNavSections((current) => ({ ...current, [section.key]: !collapsed }))}
                    >
                      <span>{section.label}</span>
                      <span className="admin-sidebar-section-symbol" aria-hidden="true">{collapsed ? "+" : "−"}</span>
                    </button>
                    {!collapsed
                      ? section.items.map((item) => (
                          <Link
                            key={item.href}
                            href={item.href}
                            className={`admin-sidebar-link ${pathname.startsWith(item.href) ? "is-active" : ""}`}
                          >
                            <MaterialIcon name={item.icon} />
                            <span>{item.label}</span>
                          </Link>
                        ))
                      : null}
                  </div>
                );
              })}
            </nav>
          </div>
          <div className="admin-sidebar-footer">
            <div className="admin-user-card">
              <Monogram seed={viewerPrimary} />
              <div>
                <strong>{viewerPrimary}</strong>
                <span>{hasAdminRole(viewer) ? "SYSTEM ADMIN" : viewerRoleLabel}</span>
              </div>
            </div>
            <span>Built for enterprise retrieval teams</span>
            <LogoutButton />
          </div>
        </aside>

        <main className="admin-main">
          <header className="admin-topbar">
            {navToggleButton}
            <div className="admin-command" data-coming-soon="true" title={COMING_SOON_TITLE}>
              <MaterialIcon name="search" />
              <input readOnly value="Search traces, corpora, or jobs (⌘K)" aria-label="Admin command search (coming soon)" tabIndex={-1} />
              <span className="coming-soon-badge">Soon</span>
            </div>
            <div className="admin-topbar-actions">
              <div className="console-viewer-chip" title={viewerSecondary}>
                <div className="console-viewer-chip-copy">
                  <strong>{viewerPrimary}</strong>
                  <span>{viewerSecondary}</span>
                </div>
              </div>
              <Link href="/console/admin/access" className="admin-icon-button" aria-label="Notifications" title="Open access requests and notifications.">
                <MaterialIcon name="notifications" />
              </Link>
              <button type="button" className="admin-icon-button is-coming-soon" {...comingSoonProps("Settings")}>
                <MaterialIcon name="settings" />
              </button>
              <Link href="/console/admin/corpora" className="stitch-button stitch-button-primary stitch-button-small">
                <MaterialIcon name="add" />
                New Corpus
              </Link>
            </div>
          </header>
          <div className="admin-main-content" id="console-main">{children}</div>
          <footer className="console-footer">
            <span>Built for enterprise retrieval teams</span>
            <div>
              <Link href="/privacy">Privacy</Link>
              <Link href="/terms">Terms</Link>
              <Link href="/security">Security</Link>
              <Link href="/status">Status</Link>
            </div>
          </footer>
        </main>
      </div>
    );
  }

  // V2 workspace shell: dark icon rail + top command bar (see web/DESIGN.md §7,
  // "V2 workflow console"). The rail is the only persistent chrome; workflow
  // surfaces own the rest of the viewport.
  const isRouteActive = (href: string) =>
    href === "/console/workspace" ? pathname === href : pathname.startsWith(href);

  function submitCommand(event: FormEvent) {
    event.preventDefault();
    const value = commandQuery.trim();
    if (!value) return;
    setCommandQuery("");
    router.push(`/console/workspace/chat?q=${encodeURIComponent(value)}`);
  }

  return (
    <div className="v2-shell">
      <a href="#console-main" className="skip-link">Skip to content</a>
      {navBackdrop}
      <aside className={`v2-rail ${mobileNavOpen ? "is-mobile-open" : ""}`} ref={sidebarRef} tabIndex={-1} aria-label="Workspace navigation">
        <Link href="/console/workspace" className="v2-rail-brand" aria-label="RAG Enterprise home">
          <BrandLogo />
        </Link>
        <nav className="v2-rail-nav">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`v2-rail-link ${isRouteActive(item.href) ? "is-active" : ""}`}
              aria-current={isRouteActive(item.href) ? "page" : undefined}
            >
              <MaterialIcon name={item.icon} />
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>
        <div className="v2-rail-foot">
          <Monogram seed={viewerPrimary} title={`${viewerPrimary} · ${viewerSecondary}`} />
          <button
            type="button"
            className="v2-rail-link v2-rail-logout"
            onClick={() => window.location.assign(browserApiUrl("/auth/logout"))}
          >
            <MaterialIcon name="logout" />
            <span>Log out</span>
          </button>
        </div>
      </aside>

      <div className="v2-main">
        <header className="v2-topbar">
          {navToggleButton}
          <form className="v2-command" onSubmit={submitCommand} role="search">
            <MaterialIcon name="search" />
            <input
              value={commandQuery}
              onChange={(event) => setCommandQuery(event.target.value)}
              placeholder="Ask a governed question across your sources..."
              aria-label="Ask a governed question"
            />
            <button type="submit" className="v2-command-go" aria-label="Ask">
              <MaterialIcon name="arrow_forward" />
            </button>
          </form>
          <div className="v2-topbar-status">
            <span className="v2-chip is-on" title="Access trimming is enforced inside retrieval SQL for every query.">
              <MaterialIcon name="shield_check" />
              ACL enforced
            </span>
            <span
              className={`v2-chip ${health === "ok" ? "is-on" : health === "checking" ? "is-wait" : "is-alert"}`}
              title={health === "ok" ? `Backend healthy · default retrieval: ${retrievalMode || "—"}` : health === "checking" ? "Checking backend health..." : "Backend unreachable or degraded."}
              role="status"
            >
              <MaterialIcon name={health === "ok" ? "check" : health === "checking" ? "progress_activity" : "warning"} className={health === "checking" ? "spin" : undefined} />
              {health === "ok" ? `Retrieval ${retrievalMode || "ready"}` : health === "checking" ? "Checking" : "Degraded"}
            </span>
            <Link href="/console/workspace/requests" className="workspace-icon-button" aria-label="Approvals and notifications" title="Open approvals and notifications.">
              <MaterialIcon name="notifications" />
            </Link>
          </div>
        </header>
        <div className="v2-content" id="console-main">{children}</div>
      </div>
    </div>
  );
}
