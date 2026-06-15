import { redirect } from "next/navigation";

import { serverFetch } from "./api-server";

export type AdminNavItem = {
  module: string;
  href: string;
  label: string;
  icon: string;
  description?: string;
};

export type AdminModulesPayload = {
  scenario_profile: string;
  enabled_modules: string[];
  disabled_modules: string[];
  navigation: AdminNavItem[];
};

const enterpriseNavigation: AdminNavItem[] = [
  { module: "overview", href: "/console/admin", label: "Overview", icon: "space_dashboard" },
  { module: "overview", href: "/console/admin/health", label: "Health", icon: "health_and_safety" },
  { module: "overview", href: "/console/admin/cost", label: "Cost", icon: "payments" },
  { module: "governance", href: "/console/admin/flywheel", label: "Flywheel", icon: "autorenew" },
  { module: "sources", href: "/console/admin/sources", label: "Sources", icon: "description" },
  { module: "connectors", href: "/console/admin/connectors", label: "Connectors", icon: "hub" },
  { module: "actions", href: "/console/admin/actions", label: "Actions", icon: "approval" },
  { module: "corpora", href: "/console/admin/corpora", label: "Corpora", icon: "folder_shared" },
  { module: "jobs", href: "/console/admin/jobs", label: "Jobs", icon: "work_history" },
  { module: "profiles", href: "/console/admin/profiles", label: "Profiles", icon: "account_circle" },
  { module: "profiles", href: "/console/admin/embedding", label: "Embedding", icon: "swap_horiz" },
  { module: "evals", href: "/console/admin/evals", label: "Evals", icon: "analytics" },
  { module: "traces", href: "/console/admin/traces", label: "Traces", icon: "timeline" },
  { module: "policies", href: "/console/admin/policies", label: "Policies", icon: "policy" },
  { module: "policies", href: "/console/admin/providers", label: "Providers", icon: "dns" },
  { module: "access", href: "/console/admin/access", label: "Access", icon: "shield_lock" },
  { module: "audit", href: "/console/admin/audit-log", label: "Audit Log", icon: "receipt_long" },
];

export async function getAdminModules(): Promise<AdminModulesPayload> {
  try {
    return await serverFetch<AdminModulesPayload>("/admin/modules");
  } catch {
    return {
      scenario_profile: "enterprise_oidc_acl",
      enabled_modules: enterpriseNavigation.map((item) => item.module),
      disabled_modules: [],
      navigation: enterpriseNavigation,
    };
  }
}

export async function requireAdminModule(module: string): Promise<void> {
  const payload = await getAdminModules();
  if (!payload.enabled_modules.includes(module)) {
    redirect(`/console/admin?module_unavailable=${encodeURIComponent(module)}`);
  }
}
