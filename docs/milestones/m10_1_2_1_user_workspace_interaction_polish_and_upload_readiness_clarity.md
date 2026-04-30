## M10.1.2.1 — User Workspace Interaction Polish And Upload Readiness Clarity

- Turned answer actions into working UI controls without pulling backend feedback persistence forward.
- Added visible acknowledgement for `Copy Answer` and client-only helpful/not-helpful toggles.
- Tightened the retrieved-sources rail so older answer groups default collapsed and citation selection stays scoped to the matching answer section.
- Persisted retrieved-sources rail selection and collapse state per thread without overwriting it during refresh hydration, so reload reopens the same answer section/source instead of snapping back to the latest answer.
- Replaced the generic selected-context label with source-aware file and locator details, cleaner document-title formatting, and a separate open-file link line.
- Clarified that `chunked` is not yet searchable, while `embedded` / `indexed` means ready for grounded retrieval.
- Added plain-language upload status and polling explanations so live ingestion progress does not require reading backend logs.
