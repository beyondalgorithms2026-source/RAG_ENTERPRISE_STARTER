"""Skip guard for tests that require a live, migrated Postgres.

Most of this suite exercises retrieval, ACL trimming and ingestion against a real
database with pgvector. That is the right way to test SQL-level access control -
an ACL bug that only appears against a real query planner is exactly the bug that
matters - but it means those tests cannot run in a clean CI container.

Without a guard the suite hard-fails on connection errors, which is indistinguishable
from the suite genuinely failing. With it, the offline-passing count is honest and CI
reports skips as skips.

Set RAG_REQUIRE_DB=1 to turn the skip into a hard failure, so a CI job that is
*supposed* to have a database cannot silently pass by skipping everything.
"""

from __future__ import annotations

import os
import unittest

_status: tuple[bool, str] | None = None


def database_status() -> tuple[bool, str]:
    """Return (available, reason). Cached: probe the database once per process."""
    global _status
    if _status is not None:
        return _status

    try:
        from sqlalchemy import text

        from app.db.db import engine

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        _status = (True, "")
    except Exception as exc:  # noqa: BLE001 - any failure means unavailable
        _status = (False, f"{type(exc).__name__}: {str(exc).splitlines()[0][:160]}")
    return _status


def require_database() -> None:
    """Skip the calling test module or class when no database is reachable."""
    available, reason = database_status()
    if available:
        return
    if os.environ.get("RAG_REQUIRE_DB") == "1":
        raise AssertionError(
            f"RAG_REQUIRE_DB=1 but the database is unreachable: {reason}"
        )
    raise unittest.SkipTest(
        f"requires a live migrated Postgres (start it with `docker compose up -d` "
        f"and run `python -m app.db.migrate`). Probe failed: {reason}"
    )
