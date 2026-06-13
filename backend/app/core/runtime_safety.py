"""Deployment / multi-worker safety guards (AR8).

The audit found single-process assumptions that silently break under standard
deployment shapes: the in-process threaded ingestion worker is poked by an
in-memory event, rate limiting is in-memory, and the embedding/reranker
singletons are module globals. Running `uvicorn --workers 2` therefore breaks
queue wakeups and rate limits without any error. Rather than pretend to be
multi-worker safe, the app refuses to start with >1 worker unless the operator
explicitly opts in after addressing these.
"""
import os
from typing import Optional

from app.core.config import settings
from app.core.logging import logger

_WORKER_ENV_VARS = ("WEB_CONCURRENCY", "UVICORN_WORKERS", "GUNICORN_WORKERS")

SINGLE_PROCESS_ASSUMPTIONS = (
    "in-process threaded ingestion queue woken by an in-memory event",
    "in-memory per-process rate limiting",
    "module-global embedding/reranker model singletons",
)


def configured_worker_count(env: Optional[dict] = None) -> int:
    source = env if env is not None else os.environ
    counts = []
    for name in _WORKER_ENV_VARS:
        raw = str(source.get(name) or "").strip()
        if raw.isdigit():
            counts.append(int(raw))
    return max(counts) if counts else 1


def assert_worker_safety(env: Optional[dict] = None) -> int:
    """Refuse to run multi-worker unless explicitly allowed. Returns the worker
    count when safe; raises RuntimeError otherwise."""
    workers = configured_worker_count(env)
    if workers > 1 and not settings.ALLOW_MULTI_WORKER:
        raise RuntimeError(
            f"Refusing to start with {workers} web workers: this build is single-process "
            f"({'; '.join(SINGLE_PROCESS_ASSUMPTIONS)}). Run a single worker, or set "
            "ALLOW_MULTI_WORKER=true to override once these are externalized (e.g. a "
            "Postgres-backed queue and shared rate limiter)."
        )
    if workers > 1:
        logger.warning(
            "Starting with %s web workers and ALLOW_MULTI_WORKER=true; single-process "
            "assumptions (%s) are the operator's responsibility.",
            workers,
            "; ".join(SINGLE_PROCESS_ASSUMPTIONS),
        )
    return workers
