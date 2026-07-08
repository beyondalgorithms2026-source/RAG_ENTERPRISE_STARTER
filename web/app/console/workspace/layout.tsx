import { ReactNode } from "react";

import { ConsoleShell } from "@/components/console-shell";
import { requireViewer } from "@/lib/auth";

export const dynamic = "force-dynamic";

const navItems = [
  { href: "/console/workspace", label: "Home", icon: "space_dashboard" },
  { href: "/console/workspace/chat", label: "Ask", icon: "chat" },
  { href: "/console/workspace/search", label: "Search", icon: "search" },
  { href: "/console/workspace/history", label: "History", icon: "history" },
  { href: "/console/workspace/requests", label: "Approvals", icon: "approval" },
  { href: "/console/workspace/trust", label: "Trust", icon: "verified" },
  { href: "/console/workspace/sources", label: "Sources", icon: "database" },
  { href: "/console/workspace/uploads", label: "Uploads", icon: "upload_file" },
  { href: "/console/workspace/connectors", label: "Connectors", icon: "hub" },
];

export default async function WorkspaceLayout({ children }: { children: ReactNode }) {
  const viewer = await requireViewer("/console/workspace");
  return (
    <ConsoleShell viewer={viewer} navItems={navItems} variant="workspace">
      {children}
    </ConsoleShell>
  );
}
