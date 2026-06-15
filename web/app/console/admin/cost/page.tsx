import { AdminCostPanel } from "@/components/admin-cost-panel";
import { requireAdminModule } from "@/lib/admin-modules";

export default async function AdminCostPage() {
  await requireAdminModule("cost");
  return <AdminCostPanel />;
}
