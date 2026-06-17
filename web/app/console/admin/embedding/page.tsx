import { AdminEmbeddingPanel } from "@/components/admin-embedding-panel";
import { requireAdminModule } from "@/lib/admin-modules";

export default async function AdminEmbeddingPage() {
  await requireAdminModule("embedding");
  return <AdminEmbeddingPanel />;
}
