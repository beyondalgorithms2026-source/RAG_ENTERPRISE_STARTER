import { ReactNode } from "react";

import { ConsoleShell } from "@/components/console-shell";
import { requireAdminViewer } from "@/lib/auth";

export const dynamic = "force-dynamic";

const navItems = [
  { href: "/console/admin/corpora", label: "Corpora", icon: "folder_shared" },
  { href: "/console/admin/jobs", label: "Jobs", icon: "work_history" },
  { href: "/console/admin/profiles", label: "Profiles", icon: "account_circle" },
  { href: "/console/admin/evals", label: "Evals", icon: "analytics" },
  { href: "/console/admin/traces", label: "Traces", icon: "timeline" },
  { href: "/console/admin/policies", label: "Policies", icon: "policy" },
  { href: "/console/admin/audit-log", label: "Audit Log", icon: "receipt_long" },
];

export default async function AdminLayout({ children }: { children: ReactNode }) {
  const viewer = await requireAdminViewer("/console/admin");
  return (
    <ConsoleShell viewer={viewer} navItems={navItems} variant="admin">
      {children}
    </ConsoleShell>
  );
}
