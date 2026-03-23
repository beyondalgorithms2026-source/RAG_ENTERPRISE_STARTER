import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.jobs import admin_reindex_source


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Safely rebuild ingestion artifacts for an existing source.")
    parser.add_argument("--source-id", type=int, required=True, help="Existing source id to reindex.")
    parser.add_argument("--force", action="store_true", help="Allow rerun when the source is marked processing.")
    args = parser.parse_args(argv)

    try:
        result = admin_reindex_source(source_id=args.source_id, force=args.force)
    except Exception as exc:
        print(json.dumps({"status": "error", "source_id": args.source_id, "error": str(exc)}, indent=2))
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
