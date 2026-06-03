# Validation: research_no_auth

- Run backend smoke search/ask on public trusted data.
- Confirm upload is allowed only when `AUTH_NONE_ALLOW_UPLOAD=true`.
- Confirm `/admin/modules` hides access, actions, connectors, governance, profiles, policies, and tuning.
- Confirm disabled module direct API calls return `403 module_disabled`.
- Confirm citation provenance remains present for answers.
