import { AdminProvidersPanel } from "@/components/admin-providers-panel";
import { requireAdminModule } from "@/lib/admin-modules";

export default async function AdminProvidersPage() {
  await requireAdminModule("providers");
  return <AdminProvidersPanel />;
}
