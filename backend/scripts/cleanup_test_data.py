import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from sqlalchemy import text


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.db import engine


def cleanup_test_data(*, storage_prefix: str, apply: bool) -> dict:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, file_name, storage_path
                FROM sources
                WHERE storage_path LIKE :pattern
                ORDER BY id ASC
                """
            ),
            {"pattern": f"{storage_prefix}%"},
        ).fetchall()

    matches = [{"source_id": row[0], "file_name": row[1], "storage_path": row[2]} for row in rows]
    result = {
        "status": "dry_run" if not apply else "completed",
        "storage_prefix": storage_prefix,
        "matched_count": len(matches),
        "matched_sources": matches,
        "deleted_count": 0,
    }
    if not apply or not matches:
        return result

    source_ids = [item["source_id"] for item in matches]
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM sources WHERE id = ANY(:source_ids)"), {"source_ids": source_ids})
    result["deleted_count"] = len(source_ids)
    return result


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Conservatively clean up test/dev source data.")
    parser.add_argument(
        "--storage-prefix",
        default="tests/",
        help="Only sources with storage_path starting with this prefix are eligible. Default: tests/",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete matching sources. Without this flag the command is a dry run.",
    )
    args = parser.parse_args(argv)

    result = cleanup_test_data(storage_prefix=args.storage_prefix, apply=args.apply)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
