// Pure admin-navigation types + grouping. No server-only imports, so this is
// safe to import from client components (e.g. console-shell).

export type AdminNavItem = {
  module: string;
  href: string;
  label: string;
  icon: string;
  description?: string;
};

export type AdminNavSection = { key: string; label: string; items: AdminNavItem[] };

// Group the flat admin navigation into labelled sections (Overview pinned).
const ADMIN_NAV_SECTIONS: { key: string; label: string; modules: string[] }[] = [
  { key: "operate", label: "Operate", modules: ["health", "cost", "flywheel", "jobs", "traces"] },
  { key: "retrieval", label: "Retrieval", modules: ["profiles", "embedding", "evals"] },
  { key: "data", label: "Data", modules: ["uploads", "sources", "connectors", "corpora"] },
  { key: "governance", label: "Governance", modules: ["actions", "policies", "providers", "access", "audit"] },
];

export function groupAdminNav(navigation: AdminNavItem[]): { pinned: AdminNavItem[]; sections: AdminNavSection[] } {
  const pinned = navigation.filter((item) => item.module === "overview");
  const sections: AdminNavSection[] = ADMIN_NAV_SECTIONS.map((section) => ({
    key: section.key,
    label: section.label,
    items: navigation.filter((item) => section.modules.includes(item.module)),
  })).filter((section) => section.items.length > 0);
  const claimed = new Set([...pinned, ...sections.flatMap((section) => section.items)]);
  const leftover = navigation.filter((item) => !claimed.has(item));
  if (leftover.length) {
    sections.push({ key: "more", label: "More", items: leftover });
  }
  return { pinned, sections };
}
