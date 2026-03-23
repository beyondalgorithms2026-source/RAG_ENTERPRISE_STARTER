import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.enrichment import admin_rerun_enrichment


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Safely rerun enrichment for an existing source.")
    parser.add_argument("--source-id", type=int, required=True, help="Existing source id to enrich.")
    parser.add_argument("--force", action="store_true", help="Allow rerun when the source is marked processing.")
    args = parser.parse_args(argv)

    try:
        result = admin_rerun_enrichment(source_id=args.source_id, force=args.force)
    except Exception as exc:
        print(json.dumps({"status": "error", "source_id": args.source_id, "error": str(exc)}, indent=2))
        return 1

    payload = {
        "status": "completed",
        "source_id": args.source_id,
        "job_id": result.job_id,
        "reason": result.reason,
        "chunk_updates": result.chunk_updates,
        "entities_extracted": result.entities_extracted,
        "relations_extracted": result.relations_extracted,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
