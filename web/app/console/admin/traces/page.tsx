import { TracesAdminPanel } from "@/components/admin-panels";
import { requireAdminModule } from "@/lib/admin-modules";

export default async function AdminTracesPage() {
  await requireAdminModule("traces");
  return <TracesAdminPanel />;
}
