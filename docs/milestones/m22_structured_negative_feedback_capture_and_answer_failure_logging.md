# M22 — Structured Negative Feedback Capture And Answer Failure Logging

## Change Note

- Added a dedicated `negative_feedback_events` artifact for structured thumbs-down feedback with question, answer text, selected reason, optional note, actor, citations, chunk/source ids, profile snapshot, and request metadata.
- Extended `/feedback` so helpful feedback stays lightweight while `not_helpful` feedback requires a structured reason and continues to feed existing `query_feedback` and `query_events` paths.
- Added admin visibility for structured answer failures and reason counts through the existing Actions workflow.
- Updated the chat workspace so thumbs-down opens a guided reason form instead of immediately writing a generic negative event.

## Validation

- Added smoke coverage for helpful feedback compatibility, structured negative-feedback validation, persistence, query-mining event compatibility, and admin listing.
- Re-run checks should include baseline smoke, M16 feedback/no-evidence regression, M20 query-mining regression, admin ops smoke, and migration validation.
