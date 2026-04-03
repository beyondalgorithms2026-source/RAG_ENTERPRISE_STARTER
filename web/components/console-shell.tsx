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
  const isSourcesSurface = pathname.startsWith("/console/workspace/sources");
  const brandAvatar = variant === "admin"
    ? "https://lh3.googleusercontent.com/aida-public/AB6AXuDDzrfI0fplKu_x0sR5zlA8iGmugYhn3F22d-IqQgfODwZm1RJyD-UzdaxUzvE52YtoSYoL3C8tPAvcx2Qx7LIACk57feFQJ7Cw1BpAoMHWSFgXl1G4R2rdhmVPg9f-aVViy3MBJPPSTc96lWhLkXmI-SlNTZXgmL8XVvvn85wqod38m2ebrX62rGP6SgmLGqz0UTLeauV_0rEwSnNS8TzucqerLolx81wW-QRAmapfiGTTbgVJTJMcllvsec7fvP3C7EM3czcwIRg"
    : "https://lh3.googleusercontent.com/aida-public/AB6AXuACPUt-vFdpDEFkTykPrDK7qWDXayI-mTENz12neiecYsTFwJcauq2SyXQIlPs1icim8vWLYPo-1eATxYkQeXUrE1bxqk93oQwngnIvnhKlzQxk8QRI97HUkzaGZjV43CgcmygoyRZLwtmXmqHStwx_LK5ISY31JrhpkesypNorp8pIGSBHx65TQ9Sa2PShgRk2KhhRNaLjKKb_hrddPTJZhA5qk17WxUp4Mjjf3ENB2PbD4fnxXXRYKiwow_MZXjn4J7Qw-dz5kw8";

  if (variant === "admin") {
    return (
      <div className="admin-shell">
        <aside className="admin-sidebar">
          <div className="admin-sidebar-head">
            <h2>Admin</h2>
            <p>Management</p>
          </div>
          <nav className="admin-sidebar-nav">
            {navItems.map((item) => (
              <Link
                key={item.label}
                href={item.href}
                className={`admin-sidebar-link ${
                  pathname === item.href || (pathname === "/console/admin" && item.href === "/console/admin/corpora") ? "is-active" : ""
                }`}
              >
                <span className="material-symbols-outlined">{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            ))}
          </nav>
          <div className="admin-user-card">
            <img src={brandAvatar} alt={viewer.name || viewer.email || viewer.user_id} />
            <div>
              <strong>{viewer.name || viewer.email || viewer.user_id}</strong>
              <span>{hasAdminRole(viewer) ? "SYSTEM ADMIN" : viewer.roles.join(", ").toUpperCase()}</span>
            </div>
            <span className="material-symbols-outlined">unfold_more</span>
          </div>
          <div className="admin-logout-wrap">
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
              <button type="button" className="admin-icon-button" aria-label="Notifications">
                <span className="material-symbols-outlined">notifications</span>
              </button>
              <button type="button" className="admin-icon-button" aria-label="Settings">
                <span className="material-symbols-outlined">settings</span>
              </button>
              <Link href="/console/admin" className="stitch-button stitch-button-primary stitch-button-small">
                <span className="material-symbols-outlined">add</span>
                New Corpura
              </Link>
            </div>
          </header>
          <div className="admin-main-content">{children}</div>
          <footer className="console-footer">
            <span>Built for enterprise retrieval teams</span>
            <div>
              <a href="#privacy">Privacy</a>
              <a href="#terms">Terms</a>
              <a href="#security">Security</a>
              <a href="#status">Status</a>
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
              <button type="button" className="is-active">
                Ask
              </button>
              <button type="button">Search</button>
            </div>
          )}
        </div>
        <div className="workspace-topbar-actions">
          <button type="button" className="workspace-icon-button" aria-label="Notifications">
            <span className="material-symbols-outlined">notifications</span>
          </button>
          <button type="button" className="workspace-icon-button" aria-label="Settings">
            <span className="material-symbols-outlined">settings</span>
          </button>
          <div className="workspace-avatar">
            <img src={brandAvatar} alt={viewer.name || viewer.email || viewer.user_id} />
          </div>
        </div>
      </header>

      <div className="workspace-body">
        <aside className="workspace-sidebar">
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
            <div className="workspace-storage-card">
              <div className="workspace-storage-head">
                <span>Storage</span>
                <strong>64%</strong>
              </div>
              <div className="workspace-storage-bar">
                <div />
              </div>
            </div>
          ) : (
            <div className="workspace-thread-card">
              <span>Recent Threads</span>
              <div>
                {recentThreads.length === 0 ? (
                  <p className="workspace-thread-empty">Ask your first grounded question.</p>
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
          <div className="workspace-sidebar-footer">
            <span>Built for enterprise retrieval teams</span>
            <LogoutButton />
          </div>
        </aside>
        <div className="workspace-content">{children}</div>
      </div>
    </div>
  );
}
