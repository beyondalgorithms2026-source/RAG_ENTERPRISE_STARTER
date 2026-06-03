import { ReactNode } from "react";

import { ConsoleShell } from "@/components/console-shell";
import { requireAdminViewer } from "@/lib/auth";
import { getAdminModules } from "@/lib/admin-modules";

export const dynamic = "force-dynamic";

export default async function AdminLayout({ children }: { children: ReactNode }) {
  const viewer = await requireAdminViewer("/console/admin");
  const modules = await getAdminModules();
  return (
    <ConsoleShell viewer={viewer} navItems={modules.navigation} variant="admin">
      {children}
    </ConsoleShell>
  );
}
