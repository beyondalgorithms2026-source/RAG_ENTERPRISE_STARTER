"""Plan or apply the one-time cleanup of duplicated public-demo seed sources.

Dry-run is the default. Apply mode is intentionally guarded by the observed hosted
41-row/14-identity public precondition and a separately created backup reference.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.db.db import engine


def _path_fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _canonical_identity(row: dict[str, Any]) -> str:
    metadata = row.get("source_metadata_json") or {}
    return str(metadata.get("source_file") or row["file_name"])


def _survivor_key(row: dict[str, Any]) -> tuple[int, int, int, int]:
    chunk_count = int(row.get("chunk_count") or 0)
    embedded_count = int(row.get("embedded_chunk_count") or 0)
    return (
        int(row.get("ingestion_status") == "embedded" and chunk_count > 0),
        int(chunk_count > 0 and embedded_count == chunk_count),
        chunk_count,
        int(row["id"]),
    )


def build_cleanup_plan(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[_canonical_identity(row)].append(row)

    duplicate_groups = []
    delete_ids: list[int] = []
    survivor_ids: list[int] = []
    for identity, members in sorted(groups.items()):
        survivor = max(members, key=_survivor_key)
        survivor_ids.append(int(survivor["id"]))
        removals = [item for item in members if item["id"] != survivor["id"]]
        delete_ids.extend(int(item["id"]) for item in removals)
        duplicate_groups.append(
            {
                "canonical_source": identity,
                "source_count": len(members),
                "survivor_id": int(survivor["id"]),
                "survivor_complete": bool(
                    survivor.get("ingestion_status") == "embedded"
                    and int(survivor.get("chunk_count") or 0) > 0
                    and int(survivor.get("embedded_chunk_count") or 0)
                    == int(survivor.get("chunk_count") or 0)
                ),
                "remove_ids": [int(item["id"]) for item in removals],
                "dependent_chunks_to_remove": sum(
                    int(item.get("chunk_count") or 0) for item in removals
                ),
                "dependent_acls_to_remove": sum(
                    int(item.get("acl_count") or 0) for item in removals
                ),
                "storage_roots": [
                    {
                        "source_id": int(item["id"]),
                        "path_fingerprint": _path_fingerprint(str(item["storage_path"])),
                        "file_name": Path(str(item["storage_path"])).name,
                    }
                    for item in sorted(members, key=lambda item: int(item["id"]))
                ],
            }
        )

    public_rows = [row for row in rows if row.get("sensitivity_label") == "public"]
    public_identities = {_canonical_identity(row) for row in public_rows}
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "dry_run",
        "seed_pack": "public_demo",
        "observed": {
            "total_seed_rows": len(rows),
            "canonical_identities": len(groups),
            "anonymous_visible_rows": len(public_rows),
            "anonymous_visible_identities": len(public_identities),
        },
        "survivor_ids": survivor_ids,
        "delete_ids": sorted(delete_ids),
        "rows_to_remove": len(delete_ids),
        "duplicate_groups": duplicate_groups,
    }


def _load_rows(conn) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(
            text(
                """
                SELECT s.id, s.file_name, s.storage_path, s.hash_sha256,
                       s.sensitivity_label, s.ingestion_status, s.source_metadata_json,
                       (SELECT COUNT(*) FROM chunks c WHERE c.source_id = s.id) AS chunk_count,
                       (SELECT COUNT(*) FROM chunks c
                         WHERE c.source_id = s.id AND c.embedding IS NOT NULL) AS embedded_chunk_count,
                       (SELECT COUNT(*) FROM document_acl da WHERE da.source_id = s.id) AS acl_count
                FROM sources s
                WHERE s.source_metadata_json->>'seed_pack' = 'public_demo'
                ORDER BY s.id
                """
            )
        ).mappings()
    ]


def _assert_apply_preconditions(
    plan: dict[str, Any], *, expected_visible_rows: int, expected_visible_identities: int
) -> None:
    observed = plan["observed"]
    if observed["anonymous_visible_rows"] != expected_visible_rows:
        raise RuntimeError("hosted anonymous-visible row precondition changed; refusing cleanup")
    if observed["anonymous_visible_identities"] != expected_visible_identities:
        raise RuntimeError("hosted public identity precondition changed; refusing cleanup")
    incomplete = [
        group["canonical_source"]
        for group in plan["duplicate_groups"]
        if not group["survivor_complete"]
    ]
    if incomplete:
        raise RuntimeError("at least one canonical survivor is not completely embedded")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--manifest-out", type=Path)
    parser.add_argument("--backup-reference")
    parser.add_argument("--expected-visible-rows", type=int, default=41)
    parser.add_argument("--expected-visible-identities", type=int, default=14)
    args = parser.parse_args()
    if args.apply and not (args.backup_reference or "").strip():
        parser.error("--apply requires --backup-reference from a completed database backup")

    with engine.begin() as conn:
        plan = build_cleanup_plan(_load_rows(conn))
        if args.apply:
            _assert_apply_preconditions(
                plan,
                expected_visible_rows=args.expected_visible_rows,
                expected_visible_identities=args.expected_visible_identities,
            )
            locked = {
                int(row[0])
                for row in conn.execute(
                    text("SELECT id FROM sources WHERE id = ANY(:ids) FOR UPDATE"),
                    {"ids": plan["delete_ids"]},
                )
            }
            if locked != set(plan["delete_ids"]):
                raise RuntimeError("cleanup targets changed after planning; refusing cleanup")
            conn.execute(
                text("DELETE FROM sources WHERE id = ANY(:ids)"),
                {"ids": plan["delete_ids"]},
            )
            plan["mode"] = "applied"
            plan["backup_reference"] = args.backup_reference

    rendered = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    if args.manifest_out:
        args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
