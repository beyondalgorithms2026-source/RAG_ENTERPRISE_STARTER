import { AuditLogAdminPanel } from "@/components/admin-panels";
import { requireAdminModule } from "@/lib/admin-modules";

export default async function AdminAuditLogPage() {
  await requireAdminModule("audit");
  return <AuditLogAdminPanel />;
}
