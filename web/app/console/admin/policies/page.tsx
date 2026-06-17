import { PoliciesAdminPanel } from "@/components/admin-panels";
import { requireAdminModule } from "@/lib/admin-modules";

export default async function AdminPoliciesPage() {
  await requireAdminModule("policies");
  return <PoliciesAdminPanel />;
}
