import { ProfilesAdminPanel } from "@/components/admin-profiles-panel";
import { requireAdminModule } from "@/lib/admin-modules";

export default async function AdminProfilesPage() {
  await requireAdminModule("profiles");
  return <ProfilesAdminPanel />;
}
