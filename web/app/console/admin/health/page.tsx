import { AdminHealthPanel } from "@/components/admin-health-panel";
import { requireAdminModule } from "@/lib/admin-modules";

export default async function AdminHealthPage() {
  await requireAdminModule("health");
  return <AdminHealthPanel />;
}
