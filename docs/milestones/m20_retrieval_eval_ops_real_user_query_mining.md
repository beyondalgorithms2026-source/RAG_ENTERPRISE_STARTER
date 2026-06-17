# M20 — Retrieval Eval Ops And Real User Query Mining

Implemented real-query evidence capture and eval-pack derivation.

- Added query event storage for failed, no-evidence, feedback, retry, and completed answer paths.
- Feedback and answer flows now record query events for later retrieval improvement analysis.
- Added failure clustering, annotation, and derived eval-pack creation APIs.
- Added admin tuning-lab visibility for query mining event, cluster, and eval-pack counts.
- Added smoke coverage for query event capture, cluster creation, annotation, and derived eval-pack generation.

