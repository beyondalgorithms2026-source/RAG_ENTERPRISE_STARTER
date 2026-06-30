import { SourcesPage } from "@/components/sources-page";
import { requireAdminModule } from "@/lib/admin-modules";

export default async function AdminUploadsPage() {
  await requireAdminModule("uploads");
  return <SourcesPage view="uploads" canManageConnectors />;
}
