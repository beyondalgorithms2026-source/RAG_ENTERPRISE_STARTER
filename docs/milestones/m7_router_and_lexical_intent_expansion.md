# M7 — Router And Lexical Intent Expansion

- Expanded lexical-first routing for quote-like exact lookups, identifier/code lookups, and date-heavy lexical queries.
- Kept semantic-first queries on the default hybrid path and preserved the existing graph/temporal readiness fallbacks.
- Added structured route metadata to retrieval traces and eval trace output: route class, preferred mode, and per-signal route details.
- Added a small router benchmark fixture pack covering quote, code, semantic, and temporal query sets.
