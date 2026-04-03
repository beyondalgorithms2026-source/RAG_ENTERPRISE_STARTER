# M10 — Next.js Enterprise Console UI

- Added a new Next.js 15 App Router frontend in `web/` as the primary UI.
- Public surface now includes a marketing homepage plus SSO-first `login` and `register` pages.
- Authenticated product routes now live under `/console/*` with role-aware redirects:
  - standard users -> `/console/workspace`
  - admins and approvers -> `/console/admin`
- User workspace includes grounded chat, enterprise search, source browsing, uploads, and connector request UI.
- Admin workspace now ships in M10 and covers corpora, jobs, profiles, evals, traces, and policy inspection.
- Backend changes were limited to CORS support for the Next.js origin and redirecting `/` to the new frontend while preserving `/frontend` as a fallback.
