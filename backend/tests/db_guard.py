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

These tests insert and delete rows. A developer's backend/.env may point DATABASE_URL at
a hosted database, so the guard refuses any non-local host before connecting. Set
RAG_TEST_ALLOW_REMOTE_DB=1 only for a disposable remote database.
"""

from __future__ import annotations

import os
import unittest
from urllib.parse import urlsplit

LOCAL_DB_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "postgres", "db"})

_status: tuple[bool, str] | None = None


def remote_database_reason(database_url: str) -> str:
    """Return why the URL is not safe for tests to write to, or "" when it is local."""
    if os.environ.get("RAG_TEST_ALLOW_REMOTE_DB") == "1":
        return ""
    host = (urlsplit(database_url).hostname or "").lower()
    if host in LOCAL_DB_HOSTS or host.endswith(".localhost"):
        return ""
    return (
        f"DATABASE_URL points at non-local host {host or '(none)'!r}; these tests write "
        "data, so they refuse to run there. Set RAG_TEST_ALLOW_REMOTE_DB=1 only for a "
        "disposable database."
    )


def database_status() -> tuple[bool, str]:
    """Return (available, reason). Cached: probe the database once per process."""
    global _status
    if _status is not None:
        return _status

    from app.core.config import settings

    refusal = remote_database_reason(settings.DATABASE_URL)
    if refusal:
        _status = (False, refusal)
        return _status

    try:
        from app.db.db import engine
        from sqlalchemy import text

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        _status = (True, "")
    except Exception as exc:
        _status = (False, f"{type(exc).__name__}: {str(exc).splitlines()[0][:160]}")
    return _status


def require_database() -> None:
    """Skip the calling test module or class when no database is reachable."""
    available, reason = database_status()
    if available:
        return
    if os.environ.get("RAG_REQUIRE_DB") == "1":
        raise AssertionError(f"RAG_REQUIRE_DB=1 but the database is not usable: {reason}")
    raise unittest.SkipTest(
        f"requires a live migrated Postgres (start it with `docker compose up -d` "
        f"and run `python -m app.db.migrate`). Probe failed: {reason}"
    )
