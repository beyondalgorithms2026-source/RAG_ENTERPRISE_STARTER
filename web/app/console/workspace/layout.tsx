import { ReactNode } from "react";

import { ConsoleShell } from "@/components/console-shell";
import { requireViewer } from "@/lib/auth";

export const dynamic = "force-dynamic";

const navItems = [
  { href: "/console/workspace/chat", label: "Chat", icon: "chat" },
  { href: "/console/workspace/history", label: "Search History", icon: "history" },
  { href: "/console/workspace/sources", label: "My Sources", icon: "database" },
  { href: "/console/workspace/uploads", label: "Upload Documents", icon: "upload_file" },
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
