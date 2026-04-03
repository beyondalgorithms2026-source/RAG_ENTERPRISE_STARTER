export type Viewer = {
  user_id: string;
  email?: string | null;
  name?: string | null;
  roles: string[];
  groups: string[];
  issuer?: string | null;
  raw_claims?: Record<string, unknown>;
};

export function hasAdminRole(viewer: Viewer | null): boolean {
  return Boolean(viewer?.roles?.some((role) => role.toLowerCase() === "admin" || role.toLowerCase() === "approver"));
}
