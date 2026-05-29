# M18 — Query Transformation Layer

Implemented an optional, trace-visible query transformation layer.

- Added rewrite, expansion, and HyDE-style query variant controls to the retrieval profile contract.
- Added a deterministic transformation service that is disabled by default.
- Retrieval traces now include original query, effective query, generated variants, strategy, latency, and fallback metadata.
- Added admin visibility for transformation posture in the tuning ops guardrail panel.
- Added smoke coverage proving default-off behavior and trace-visible enabled behavior.

