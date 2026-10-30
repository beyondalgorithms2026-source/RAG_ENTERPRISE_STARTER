"""Keep the Supabase project awake: run one small REAL query through the app's own database engine.

Supabase pauses free projects that see no database activity. A web health check does not count (/healthz never touches
the database), so schedule this once a day (Coolify Scheduled Task, cron `0 6 * * *`):

    python scripts/keepalive.py

Exit code 0 = the query ran. Exit code 1 = it failed (the message names the error type only, never the connection string).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

QUERY = "SELECT COUNT(*) FROM sources"  # a real table the app owns, so Postgres does real work


def run(engine) -> int:
    try:
        with engine.connect() as conn:
            count = conn.execute(text(QUERY)).scalar_one()
    except Exception as exc:  # any failure must turn the scheduled task red
        print(f"keepalive FAILED: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"keepalive ok: sources={count}")
    return 0


def main() -> int:
    try:
        from app.db.db import engine
    except Exception as exc:
        print(f"keepalive FAILED: could not load the database engine ({type(exc).__name__})", file=sys.stderr)
        return 1
    return run(engine)


if __name__ == "__main__":
    sys.exit(main())
