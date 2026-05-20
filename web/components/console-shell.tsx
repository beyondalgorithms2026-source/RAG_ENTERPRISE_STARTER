"use client";

import Link from "next/link";
import { ReactNode } from "react";
import { usePathname } from "next/navigation";

import { LogoutButton } from "@/components/logout-button";
import { hasAdminRole, type Viewer } from "@/lib/viewer";
import { readThreads, THREADS_UPDATED_EVENT } from "@/lib/workspace";
import { useEffect, useState } from "react";

type NavItem = {
  href: string;
  label: string;
  icon: string;
};

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

  const isChatSurface = pathname.startsWith("/console/workspace/chat");
  const isSearchSurface = pathname.startsWith("/console/workspace/search");
  const isSourcesSurface =
    pathname.startsWith("/console/workspace/sources") ||
    pathname.startsWith("/console/workspace/uploads") ||
    pathname.startsWith("/console/workspace/connectors");
  const brandAvatar = variant === "admin"
    ? "https://lh3.googleusercontent.com/aida-public/AB6AXuDDzrfI0fplKu_x0sR5zlA8iGmugYhn3F22d-IqQgfODwZm1RJyD-UzdaxUzvE52YtoSYoL3C8tPAvcx2Qx7LIACk57feFQJ7Cw1BpAoMHWSFgXl1G4R2rdhmVPg9f-aVViy3MBJPPSTc96lWhLkXmI-SlNTZXgmL8XVvvn85wqod38m2ebrX62rGP6SgmLGqz0UTLeauV_0rEwSnNS8TzucqerLolx81wW-QRAmapfiGTTbgVJTJMcllvsec7fvP3C7EM3czcwIRg"
    : "https://lh3.googleusercontent.com/aida-public/AB6AXuACPUt-vFdpDEFkTykPrDK7qWDXayI-mTENz12neiecYsTFwJcauq2SyXQIlPs1icim8vWLYPo-1eATxYkQeXUrE1bxqk93oQwngnIvnhKlzQxk8QRI97HUkzaGZjV43CgcmygoyRZLwtmXmqHStwx_LK5ISY31JrhpkesypNorp8pIGSBHx65TQ9Sa2PShgRk2KhhRNaLjKKb_hrddPTJZhA5qk17WxUp4Mjjf3ENB2PbD4fnxXXRYKiwow_MZXjn4J7Qw-dz5kw8";
  const viewerPrimary = viewer.name || viewer.email || viewer.user_id;
  const viewerSecondary = viewer.email || viewer.user_id;
  const viewerRoleLabel = viewer.roles.length ? viewer.roles.join(", ").toUpperCase() : "USER";

  if (variant === "admin") {
    return (
      <div className="admin-shell">
        <aside className="admin-sidebar">
          <div className="admin-sidebar-scroll">
            <div className="admin-sidebar-head">
              <h2>RAG Enterprise</h2>
              <p>Admin Console</p>
            </div>
            <nav className="admin-sidebar-nav">
              {navItems.map((item) => (
                <Link
                  key={item.label}
                  href={item.href}
                  className={`admin-sidebar-link ${
                    pathname.startsWith(item.href) ? "is-active" : ""
                  }`}
                >
                  <span className="material-symbols-outlined">{item.icon}</span>
                  <span>{item.label}</span>
                </Link>
              ))}
            </nav>
          </div>
          <div className="admin-sidebar-footer">
            <div className="admin-user-card">
              <img src={brandAvatar} alt={viewerPrimary} />
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
            <div className="admin-command">
              <span className="material-symbols-outlined">search</span>
              <input readOnly value="Search traces, corpora, or jobs (⌘K)" aria-label="Admin command search" />
            </div>
            <div className="admin-topbar-actions">
              <div className="console-viewer-chip" title={viewerSecondary}>
                <div className="console-viewer-chip-copy">
                  <strong>{viewerPrimary}</strong>
                  <span>{viewerSecondary}</span>
                </div>
              </div>
              <Link href="/console/admin/access" className="admin-icon-button" aria-label="Notifications" title="Open access requests and notifications.">
                <span className="material-symbols-outlined">notifications</span>
              </Link>
              <button type="button" className="admin-icon-button" aria-label="Settings" disabled title="Settings are not wired yet in this milestone.">
                <span className="material-symbols-outlined">settings</span>
              </button>
              <Link href="/console/admin/corpora" className="stitch-button stitch-button-primary stitch-button-small">
                <span className="material-symbols-outlined">add</span>
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
            RAG Enterprise
          </Link>
          {isSourcesSurface ? (
            <div className="workspace-search-input">
              <span className="material-symbols-outlined">search</span>
              <input readOnly value="Search workspace..." aria-label="Workspace search" />
            </div>
          ) : (
            <div className="workspace-toggle">
              <Link href="/console/workspace/chat" className={!isSearchSurface ? "is-active" : ""}>
                Ask
              </Link>
              <Link href="/console/workspace/search" className={isSearchSurface ? "is-active" : ""}>
                Search
              </Link>
            </div>
          )}
        </div>
        <div className="workspace-topbar-actions">
          <div className="console-viewer-chip" title={viewerSecondary}>
            <div className="console-viewer-chip-copy">
              <strong>{viewerPrimary}</strong>
              <span>{viewerSecondary}</span>
            </div>
          </div>
          <Link href="/console/workspace/requests" className="workspace-icon-button" aria-label="Notifications" title="Open access requests and notifications.">
            <span className="material-symbols-outlined">notifications</span>
          </Link>
          <button type="button" className="workspace-icon-button" aria-label="Settings" disabled title="Settings are not wired yet in this milestone.">
            <span className="material-symbols-outlined">settings</span>
          </button>
          <div className="workspace-avatar">
            <img src={brandAvatar} alt={viewer.name || viewer.email || viewer.user_id} />
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
                  <span className="material-symbols-outlined">{item.icon}</span>
                  <span>{item.label}</span>
                </Link>
              ))}
            </nav>
            {isSourcesSurface ? (
              <div className="workspace-storage-card workspace-guide-card">
                <span>First Run</span>
                <div>
                  <strong>Start with one upload.</strong>
                  <p className="workspace-guide-copy">Use Upload Documents, wait for the file to show as indexed, then return to Chat or Search for the first grounded run.</p>
                  <div className="workspace-guide-links">
                    <Link href="/console/workspace/uploads">Open uploads</Link>
                    <Link href="/console/workspace/chat">Open chat</Link>
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
