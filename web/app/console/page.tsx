import { redirect } from "next/navigation";

import { hasAdminRole, requireViewer } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function ConsoleIndexPage() {
  const viewer = await requireViewer("/console");
  redirect(hasAdminRole(viewer) ? "/console/admin" : "/console/workspace/chat");
}
