# M6 — Hybrid Fusion Upgrade

- Kept linear hybrid fusion as the default baseline behavior.
- Added configurable `fusion_method` support for `linear` and `rrf`, plus explicit `rrf_k` retrieval settings.
- Wired hybrid, deep-research hybrid, and deep lookup merge paths to honor the active fusion config.
- Extended score diagnostics and retrieval traces with fusion method, rank inputs, and linear/RRF component scores for debugging.
- Updated benchmark fixtures so selected lexical and semantic-style cases can compare `linear` vs `rrf` in reports.
