# M19 — Semantic Cache

Implemented a safe-by-default semantic cache foundation.

- Added cache tables for entries and hit tracking.
- Cache scope includes normalized query, ACL scope hash, active profile snapshot hash, corpus scope hash, and retrieval mode.
- Answering can serve cached answers when the active retrieval profile enables semantic cache.
- Cache invalidates on active profile changes, admin reindex actions, explicit admin clear, and TTL expiry.
- Added admin cache health and clear-cache APIs plus tuning-lab ops visibility.
- Added smoke coverage for miss/hit, mode scoping, and invalidation.

