## M10.1.2 — User Workspace Contract Completion

- Replaced redirect-only user routes with truthful workspace pages for search, uploads, and connectors while preserving the existing console design.
- Hardened chat thread persistence so a newly created thread is stored before route transition and no longer blanks during first-response navigation.
- Surfaced `/ask/stream` progress inside the chat UI and added explicit terminal states for success, no-evidence, and failure.
- Added citation context drill-in and direct source-file open actions so the evidence panel behaves like a working retrieval surface instead of static chrome.
- Switched single-file uploads to a queued background-ingestion contract at the HTTP boundary and reflected ingestion job stage/status in the uploads UI.
- Added local-dev retrieval bypass for the built-in test identities when no explicit ACL exists so dev uploads can be tested end to end without weakening explicit ACL behavior.
- Follow-up remediation keeps default user entry on a fresh chat state, groups retrieved sources by answer turn, makes the workspace rails sticky during long thread review, and propagates auth context into streamed ask workers.
