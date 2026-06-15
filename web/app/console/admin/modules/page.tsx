import { AdminModulesPanel } from "@/components/admin-modules-panel";
import { requireAdminModule } from "@/lib/admin-modules";

export default async function AdminModulesPage() {
  await requireAdminModule("overview");
  return <AdminModulesPanel />;
}
