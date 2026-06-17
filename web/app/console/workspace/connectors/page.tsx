import { SourcesPage } from "@/components/sources-page";
import { hasAdminRole, requireViewer } from "@/lib/auth";

export default async function ConnectorsRoutePage() {
  const viewer = await requireViewer("/console/workspace/connectors");
  return <SourcesPage view="connectors" canManageConnectors={hasAdminRole(viewer)} />;
}
