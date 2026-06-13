import { AdminFlywheelPanel } from "@/components/admin-flywheel-panel";
import { requireAdminModule } from "@/lib/admin-modules";

export default async function AdminFlywheelPage() {
  await requireAdminModule("governance");
  return <AdminFlywheelPanel />;
}
