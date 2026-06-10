import { AdminCachePolicyPanel } from "@/components/admin-cache-policy-panel";
import { requireAdminModule } from "@/lib/admin-modules";

export default async function AdminCachePolicyPage() {
  await requireAdminModule("profiles");
  return <AdminCachePolicyPanel />;
}
