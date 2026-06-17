# Disable Advanced Admin Modules

Use scenario presets first:

- `research_no_auth`
- `employee_wide_rag`
- `small_enterprise_corpus_acl`
- `enterprise_oidc_acl`

Use `/console/admin/modules` for a deployment-wide runtime subset. Changes are high-impact, audited, and require a separate approval actor where production segregation of duties is enabled.

Resolution precedence is:

1. Runtime override saved by the module manager.
2. `ADMIN_MODULES_ENABLED`.
3. The active scenario preset.

Reset the runtime override in the module manager to return to environment or scenario behavior. `overview` is always enabled so the module manager cannot lock itself out.

Disabled modules are hidden from navigation and direct admin API access returns `403 module_disabled`. This is single-deployment composition, not per-user or per-tenant authorization. Prefer scenario presets; arbitrary custom subsets can disable a dependency used by another panel.

After changing modules, verify:

- `/admin/modules` shows the expected inventory.
- `/admin/modules` reports the expected `source`, preset, and runtime override.
- Hidden UI routes redirect to admin overview.
- Disabled API routes return `403`.
- Source/corpus admin still works if those modules remain enabled.
