import { CorporaAdminPanel } from "@/components/admin-panels";
import { requireAdminModule } from "@/lib/admin-modules";

export default async function AdminCorporaPage() {
  await requireAdminModule("corpora");
  return <CorporaAdminPanel />;
}
