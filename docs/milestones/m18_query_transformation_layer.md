# M18 — Query Transformation Layer

Implemented an optional, trace-visible query transformation layer.

- Added rewrite, expansion, and HyDE-style query variant controls to the retrieval profile contract.
- Added a deterministic transformation service that is disabled by default.
- Retrieval traces now include original query, effective query, generated variants, strategy, latency, and fallback metadata.
- Added admin visibility for transformation posture in the tuning ops guardrail panel.
- Added governed admin controls for retrieval-profile query transform settings, including create/update support and live retrieval posture visibility.
- Added sandbox compare visibility for retrieval transform posture so candidate retrieval profiles can be compared, promoted, and rolled back with explicit transform lineage.
- Added inline sandbox query-transform toggles layered on top of the selected retrieval profile, with promotion materializing those overrides into an explicit live retrieval profile so operators can see exactly which switches are on in production.
- Added smoke coverage proving default-off behavior and trace-visible enabled behavior.
