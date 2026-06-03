# Disable Advanced Admin Modules

Use scenario presets first:

- `research_no_auth`
- `employee_wide_rag`
- `small_enterprise_corpus_acl`
- `enterprise_oidc_acl`

Use `ADMIN_MODULES_ENABLED` only when a scenario needs a deliberate custom subset. Disabled modules are hidden from navigation and direct admin API access returns `403 module_disabled`.

After changing modules, verify:

- `/admin/modules` shows the expected inventory.
- Hidden UI routes redirect to admin overview.
- Disabled API routes return `403`.
- Source/corpus admin still works if those modules remain enabled.
