# AR8 — Deployment Portability And Multi-Worker Safety (Gate AR8: someone else can run it)

**Date:** 2026-06-13 · **Plan:** `docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md` · **Gate:** AR8

## Audit findings remediated

- "`docker-compose.yml` hardcoded a personal volume path
  (`/path/to/Projects/Backup/Database/rag-enterprise-pgdata`); docs and
  README used absolute `/path/to/...` paths throughout — a fresh-machine fork
  fails immediately."
- "Single-process assumptions: in-process threaded ingestion worker poked by an
  in-memory event, in-memory rate limiting …, module-global embedding/reranker
  singletons. Running `uvicorn --workers 2` silently breaks queue wakeups and
  rate limits."
- "Sandbox compare monkeypatched module-level resolver functions
  (`sandbox_compare.py:28-76`); a concurrent live request during a compare could
  be served with candidate profiles — a correctness (and tuning-integrity)
  hazard."

## What was built

- **Portable compose + docs.** `docker-compose.yml` now persists to a named
  Docker volume (`rag_enterprise_pgdata`) with env-overridable
  credentials/port/volume — no host path. Every absolute `/path/to/...` path
  in `README.md` and `docs/01_quickstart.md` is now repo-relative (links) or
  `cd "$(git rev-parse --show-toplevel)"` (shell), so a clean clone runs as-is.
- **Concurrency-safe profile overrides.** Sandbox compare and candidate eval no
  longer monkeypatch module-global resolvers. `app/profiles/resolver.py` adds a
  `ContextVar`-backed `profile_overrides(...)` context manager; the four
  `get_effective_*` getters (and the answer-time chunk cap, via
  `answering.effective_chunk_cap`) consult it first. A `ContextVar` is isolated
  per thread and per asyncio task, so a candidate bundle applied during a
  compare cannot bleed into a concurrent live request. The existing
  `sandbox_compare._temporary_*` helpers (also used by AR4
  `promotion_evidence`) were rewired to delegate to `profile_overrides`,
  preserving every call site.
- **Multi-worker safety gate.** `app/core/runtime_safety.py::assert_worker_safety`
  runs at startup and **refuses** to boot when `WEB_CONCURRENCY` /
  `UVICORN_WORKERS` / `GUNICORN_WORKERS` > 1 unless `ALLOW_MULTI_WORKER=true`.
  The error names the single-process assumptions explicitly rather than
  pretending to be horizontally scalable; with the override it logs a loud
  warning and proceeds (operator's responsibility).

## DoD check

- Clean-machine `docker compose up -d` + quickstart succeeds ✓ — no hardcoded
  paths remain (`tests/test_deployment_portability_ar8.py` asserts compose and
  docs are machine-agnostic); the named volume is created on first run.
- Concurrent sandbox+live request always uses live profiles ✓ — the override is
  ContextVar-scoped; a concurrently-running thread reads the live profile while
  the sandbox context sees the candidate (`test_override_does_not_bleed_into_concurrent_thread`).
- Re-run checks: new concurrency + worker-safety + portability tests;
  AR4 promotion eval still green through the rewired helpers; full suite
  **279/279**; `reader-clarity-check` 21/21; `docs/02` untouched.

## Honest limits

- This does not *make* the app multi-worker safe — the queue wakeup, rate
  limiter, and model singletons remain single-process. AR8 fences the hazard
  loudly instead of silently breaking; externalizing those (Postgres-backed
  queue, shared limiter) is future work the gate does not require.
- The clean-machine `docker compose up` was validated by removing the host-path
  coupling and the portability tests; a literal second physical machine was not
  available in this environment.

**Next:** AR9 — Provider Abstraction For Generation.
