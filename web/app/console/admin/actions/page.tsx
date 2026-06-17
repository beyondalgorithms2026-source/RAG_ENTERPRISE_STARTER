import { AdminActionsPanel } from "@/components/admin-actions-panel";
import { requireAdminModule } from "@/lib/admin-modules";

export default async function AdminActionsPage() {
  await requireAdminModule("actions");
  return <AdminActionsPanel />;
}
