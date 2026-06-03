import { AccessRequestsAdminPanel } from "@/components/access-admin-panel";
import { requireAdminModule } from "@/lib/admin-modules";

export default async function AdminAccessPage() {
  await requireAdminModule("access");
  return <AccessRequestsAdminPanel />;
}
