# M17.b.2 — Interactive Sandbox Controls And Side-By-Side Compare

- Added admin sandbox compare execution at `POST /admin/tuning/compare` without mutating production `active_profiles`.
- Reused temporary profile override patterns so live and candidate runs execute through the normal retrieval and answer path while preserving ACL-safe SQL trimming and citations.
- Extended LLM profile/runtime handling with `top_p` so candidate compare can vary both `temperature` and `top_p`.
- Implemented answer-time context cap handling for the sandbox `Chunk Size` control. This trims prompt context per retrieved chunk and does not rechunk or reindex stored corpus data.
- Kept embedding selection visible in the lab, but returns a structured warning state when the candidate embedding differs from live:
  - compare remains truthful instead of mixing embedding spaces in the same indexed dataset
  - future enhancement can support file-, corpus-, or folder-level shadow embedding experiments
- Reworked the Profiles tuning page so:
  - sliders and governed selectors now drive live candidate state
  - `Run Sandbox Test` and `Run Compare` execute the real compare endpoint
  - live and candidate answers render side by side with citations, latency, retrieval-path details, and delta summary tiles
  - small helper text explains that chunk size is an answer-time context cap only

## Re-run checks

- `python -m unittest tests.test_smoke_admin_ops.SmokeTestAdminOps.test_m17_b_2_interactive_sandbox_compare_and_embedding_scope_warning`
- `python -m unittest tests.test_smoke_admin_ops.SmokeTestAdminOps.test_m17_b_1_live_configuration_candidate_drafts_and_approved_registry`
- `python -m compileall backend/app`
- `pnpm exec tsc --noEmit`
