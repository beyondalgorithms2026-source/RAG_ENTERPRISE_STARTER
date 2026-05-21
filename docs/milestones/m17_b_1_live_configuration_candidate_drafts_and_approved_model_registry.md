# M17.b.1 — Stitch-Faithful Tuning Lab Shell, Live Card, And Governed Registries

- Added durable `tuning_config_versions` storage for the synced production live configuration and candidate draft configurations.
- Extended the existing profile registry so approved LLM, embedding, and reranker options are seeded as governed registry-backed choices instead of freeform UI input.
- Added admin tuning endpoints for:
  - live configuration visibility
  - candidate draft create/update/list
  - approved model registry-backed selection
- Extended profile activation to refresh the synced live tuning configuration record immediately after runtime profile changes.
- Reworked the admin Profiles page into the rewritten M17.b.1 Stitch-like shell with:
  - `Production Live Configuration` as the first/highest-priority operator anchor
  - a visually distinct `Experimentation Sandbox` shell for governed draft creation
  - a branded left navigation rail plus a live spotlight card with image-like visual treatment and live metadata on the right
  - slider-style parameter controls, bottom model selectors, and a right-side candidate summary rail to match the Stitch composition more closely
  - explicit `LLM Models`, `Embedding Models`, and `Reranker Models` governed registry sections
  - a clearly separate runtime `Profile Registry` section
  - shell-only compare and footer action sections so the page reads like the full lab while compare execution and rollout remain truthfully gated

## Left intentionally for later M17.b steps

- no live-vs-candidate execution yet
- no side-by-side compare output yet
- no active `Run Sandbox Test` action yet
- no interactive `temperature`, `top_p`, chunk size, or retrieval-`k` controls yet
- no promotion or rollback workflow yet

## Re-run checks

- `python -m unittest tests.test_smoke_admin_ops.SmokeTestAdminOps.test_m17_b_1_live_configuration_candidate_drafts_and_approved_registry`
- `python -m unittest tests.test_smoke_admin_ops.SmokeTestAdminOps.test_m10_1_3_1_admin_truthful_surfaces_and_audit_log`
- `pnpm exec tsc --noEmit`
