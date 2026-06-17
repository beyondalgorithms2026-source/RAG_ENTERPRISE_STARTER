import { SourcesAdminPanel } from "@/components/admin-panels";
import { requireAdminModule } from "@/lib/admin-modules";

export default async function AdminSourcesPage() {
  await requireAdminModule("sources");
  return <SourcesAdminPanel />;
}
