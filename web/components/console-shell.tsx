"use client";

import { BrandLogo, MaterialIcon, Monogram } from "@/components/icons";
import Link from "next/link";
import { ReactNode } from "react";
import { usePathname } from "next/navigation";

import { LogoutButton } from "@/components/logout-button";
import { groupAdminNav, type AdminNavItem } from "@/lib/admin-nav";
import { hasAdminRole, type Viewer } from "@/lib/viewer";
import { readThreads, THREADS_UPDATED_EVENT } from "@/lib/workspace";
import { useEffect, useState } from "react";

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
  const [recentThreads, setRecentThreads] = useState<{ id: string; title: string }[]>([]);
  const [collapsedNavSections, setCollapsedNavSections] = useState<Record<string, boolean>>({});
  const adminNav = variant === "admin" ? groupAdminNav(navItems as AdminNavItem[]) : null;

  useEffect(() => {
    function refreshThreads() {
      setRecentThreads(
        readThreads()
          .slice(0, 3)
          .map((thread) => ({ id: thread.id, title: thread.title })),
      );
    }
    refreshThreads();
    window.addEventListener(THREADS_UPDATED_EVENT, refreshThreads);
    window.addEventListener("storage", refreshThreads);
    return () => {
      window.removeEventListener(THREADS_UPDATED_EVENT, refreshThreads);
      window.removeEventListener("storage", refreshThreads);
    };
  }, []);

  const isSourcesSurface =
    pathname.startsWith("/console/workspace/sources") ||
    pathname.startsWith("/console/workspace/uploads") ||
    pathname.startsWith("/console/workspace/connectors");
  const viewerPrimary = viewer.name || viewer.email || viewer.user_id;
  const viewerSecondary = viewer.email || viewer.user_id;
  const viewerRoleLabel = viewer.roles.length ? viewer.roles.join(", ").toUpperCase() : "USER";

  if (variant === "admin") {
    return (
      <div className="admin-shell">
        <aside className="admin-sidebar">
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
          <div className="admin-main-content">{children}</div>
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

  return (
    <div className="workspace-shell">
      <header className="workspace-topbar">
        <div className="workspace-topbar-left">
          <Link href="/" className="workspace-brand">
            <BrandLogo />
            <span>RAG Enterprise</span>
          </Link>
          {isSourcesSurface ? (
            <div className="workspace-search-input" data-coming-soon="true" title={COMING_SOON_TITLE}>
              <MaterialIcon name="search" />
              <input readOnly value="Search workspace..." aria-label="Workspace search (coming soon)" tabIndex={-1} />
              <span className="coming-soon-badge">Soon</span>
            </div>
          ) : null}
        </div>
        <div className="workspace-topbar-actions">
          <div className="console-viewer-chip" title={viewerSecondary}>
            <div className="console-viewer-chip-copy">
              <strong>{viewerPrimary}</strong>
              <span>{viewerSecondary}</span>
            </div>
          </div>
          <Link href="/console/workspace/requests" className="workspace-icon-button" aria-label="Notifications" title="Open access requests and notifications.">
            <MaterialIcon name="notifications" />
          </Link>
          <button type="button" className="workspace-icon-button is-coming-soon" {...comingSoonProps("Settings")}>
            <MaterialIcon name="settings" />
          </button>
          <div className="workspace-avatar">
            <Monogram seed={viewerPrimary} />
          </div>
        </div>
      </header>

      <div className="workspace-body">
        <aside className="workspace-sidebar">
          <div className="workspace-sidebar-scroll">
            <div className="workspace-sidebar-head">
              <h2>Workspace</h2>
              <p>User Console</p>
            </div>
            <nav className="workspace-sidebar-nav">
              {navItems.map((item) => (
                <Link
                  key={item.label}
                  href={item.href}
                  className={`workspace-sidebar-link ${pathname.startsWith(item.href) ? "is-active" : ""}`}
                >
                  <MaterialIcon name={item.icon} />
                  <span>{item.label}</span>
                </Link>
              ))}
            </nav>
            {isSourcesSurface ? (
              <div className="workspace-storage-card workspace-guide-card">
                <span>First Run</span>
                <div>
                  <strong>Start with one upload.</strong>
                  <p className="workspace-guide-copy">Use Upload Documents, wait for the file to show as indexed, then return to Ask or Search for the first grounded run.</p>
                  <div className="workspace-guide-links">
                    <Link href="/console/workspace/uploads">Open uploads</Link>
                    <Link href="/console/workspace/chat">Open Ask</Link>
                  </div>
                </div>
              </div>
            ) : (
              <div className="workspace-thread-card">
                <span>Recent Threads</span>
                <div>
                  {recentThreads.length === 0 ? (
                    <p className="workspace-thread-empty">No saved threads yet. Ask your first grounded question and the thread will appear here after the first answer completes.</p>
                  ) : (
                    recentThreads.map((thread) => (
                      <Link
                        key={thread.id}
                        href={`/console/workspace/chat/${thread.id}`}
                        className={pathname.endsWith(thread.id) ? "is-active-thread" : ""}
                      >
                        {thread.title}
                      </Link>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
          <div className="workspace-sidebar-footer">
            <div className="workspace-viewer-summary">
              <strong>{viewerPrimary}</strong>
              <span>{viewerSecondary}</span>
            </div>
            <span>Built for enterprise retrieval teams</span>
            <LogoutButton />
          </div>
        </aside>
        <div className="workspace-content">{children}</div>
      </div>
    </div>
  );
}
