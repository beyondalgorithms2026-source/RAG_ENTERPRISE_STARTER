import { EvalsAdminPanel } from "@/components/admin-panels";
import { requireAdminModule } from "@/lib/admin-modules";

export default async function AdminEvalsPage() {
  await requireAdminModule("evals");
  return <EvalsAdminPanel />;
}
