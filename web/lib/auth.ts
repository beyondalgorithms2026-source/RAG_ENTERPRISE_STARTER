import { redirect } from "next/navigation";

import { API_BASE_URL } from "./api-base";
import { serverFetch } from "./api-server";
import { hasAdminRole, type Viewer } from "./viewer";

export { hasAdminRole, type Viewer } from "./viewer";

export async function getViewer(): Promise<Viewer | null> {
  try {
    const payload = await serverFetch<{ user: Viewer | null }>("/auth/me");
    return payload.user;
  } catch {
    return null;
  }
}

export async function requireViewer(nextPath = "/console"): Promise<Viewer> {
  const viewer = await getViewer();
  if (!viewer) {
    redirect(`/login?next=${encodeURIComponent(nextPath)}`);
  }
  return viewer;
}

export async function requireAdminViewer(nextPath = "/console/admin"): Promise<Viewer> {
  const viewer = await requireViewer(nextPath);
  if (!hasAdminRole(viewer)) {
    redirect("/console/denied");
  }
  return viewer;
}

export function buildLoginHref(nextPath: string): string {
  return `${API_BASE_URL}/auth/login?next_path=${encodeURIComponent(nextPath)}`;
}
