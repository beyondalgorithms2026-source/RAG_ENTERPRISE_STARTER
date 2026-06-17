import { AdminConnectorsPanel } from "@/components/admin-connectors-panel";
import { requireAdminModule } from "@/lib/admin-modules";

export default async function AdminConnectorsPage() {
  await requireAdminModule("connectors");
  return <AdminConnectorsPanel />;
}
