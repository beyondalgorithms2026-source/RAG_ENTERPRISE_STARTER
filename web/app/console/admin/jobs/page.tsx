import { JobsAdminPanel } from "@/components/admin-panels";
import { requireAdminModule } from "@/lib/admin-modules";

export default async function AdminJobsPage() {
  await requireAdminModule("jobs");
  return <JobsAdminPanel />;
}
