# M10.1.4 — Placeholder And CTA Hygiene Across Public And Console Surfaces

- Replaced dead-end footer hash links with real lightweight `/privacy`, `/terms`, `/security`, and `/status` routes used across the public, login, user, and admin surfaces.
- Removed or relabeled misleading public CTAs so `register`, demo, free-trial, and video-tour surfaces reflect the repo’s actual private-beta and local-validation motion.
- Disabled decorative notification, settings, and embedded-video buttons with explicit explanations instead of leaving them clickable without behavior.
- Simplified shared public navigation so visible header links point to real routes rather than missing in-page sections.
- Verification:
  - `pnpm --dir web build`
  - click-through audit of visible CTA/button/link affordances via route and text sweep
