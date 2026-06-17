# M1 — Profiles And Retrieval Controls

**Date:** 2026-04-01
**Gate:** 1 — Configurability without UI

## What changed

Introduced a DB-backed profile system that replaces hardcoded `.env` settings for embedding, reranker, LLM, and retrieval configuration. Profiles are stored in PostgreSQL (`profiles` + `active_profiles` tables) and seeded from the current `.env` on first migration.

## New capabilities

- **EmbeddingProfile** — switch embedding model/dimension/batch-size by config; re-index with new model.
- **RerankerProfile** — toggle reranker on/off, set model/top_n/score_threshold.
- **LLMProfile** — switch provider/model/temperature/timeout without code changes.
- **RetrievalProfile** — configure default mode, candidate caps, hybrid alpha, deep-research defaults, fusion method placeholder.
- **EvalPack** — dataset registry (name → cases path + description).

## Admin endpoints

- `GET /admin/profiles?profile_type=...` — list all profiles with active annotation.
- `POST /admin/profiles/active` — switch the active profile for a given type.

## Architecture

- **Resolver pattern:** each consumer calls `get_effective_*()` which reads the active profile from DB (with 5s TTL cache), validates via Pydantic, and falls back to `settings` if no profile found.
- **Migration:** MIG-P005 creates tables; MIG-P006 seeds defaults idempotently.
- **Backward compatible:** all existing endpoints work identically; profiles overlay the same values previously read from `settings`.

## Rollback

Revert to pre-M1 git tag. The `profiles`/`active_profiles` tables are inert if the resolver code is absent — existing `settings` fallback takes over.
