import csv
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT
from app.db.repo_acl import ensure_group, replace_source_acl, replace_user_memberships, upsert_auth_user
from app.db.repo_access_requests import upsert_source_access_contacts
from app.db.repo_chunks import delete_chunks_for_source, insert_chunks
from app.db.repo_sources import get_source_by_storage_path, upsert_source


DEFAULT_PACK_DIR = Path(REPO_ROOT) / "backend" / "tests" / "fixtures" / "enterprise_acl"


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _csv_split(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _normalize_source_metadata(row: dict[str, str]) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "seed_source_key": row["source_key"].strip(),
        "corpus": row.get("corpus_name", "").strip() or None,
        "source_class": row.get("source_class", "").strip() or None,
        "seed_pack": "enterprise_acl",
    }
    if row.get("classification"):
        metadata["classification"] = row["classification"].strip()
    if row.get("notes"):
        metadata["notes"] = row["notes"].strip()
    if row.get("owner_external_user_id") or row.get("owner_email") or row.get("owner_display_name"):
        metadata["source_owner"] = {
            "contact_external_user_id": row.get("owner_external_user_id") or None,
            "contact_email": (row.get("owner_email") or "").strip().lower() or None,
            "contact_display_name": row.get("owner_display_name") or None,
        }
    return {key: value for key, value in metadata.items() if value is not None}


def _seed_user_metadata(row: dict[str, str]) -> dict[str, Any]:
    return {
        "roles": _csv_split(row.get("roles", "")),
        "department": row.get("department", "").strip() or None,
        "function": row.get("function", "").strip() or None,
        "manager_email": (row.get("manager_email") or "").strip().lower() or None,
        "manager_display_name": row.get("manager_display_name", "").strip() or None,
        "manager_external_user_id": row.get("manager_external_user_id", "").strip() or None,
        "seed_pack": "enterprise_acl",
        "seed_role": row.get("seed_role", "").strip() or None,
        "blocked_test_user": (row.get("blocked_test_user") or "").strip().lower() == "true",
    }


def seed_enterprise_acl_pack(pack_dir: Path = DEFAULT_PACK_DIR) -> dict[str, Any]:
    users = _csv_rows(pack_dir / "users.csv")
    groups = _csv_rows(pack_dir / "groups.csv")
    memberships = _csv_rows(pack_dir / "memberships.csv")
    sources = _csv_rows(pack_dir / "sources.csv")
    source_acl_rows = _csv_rows(pack_dir / "source_acl.csv")
    source_contacts = _csv_rows(pack_dir / "source_contacts.csv")

    for row in groups:
        group_name = row.get("name", "").strip()
        if group_name:
            ensure_group(group_name)

    for row in users:
        external_user_id = row.get("external_user_id", "").strip()
        if not external_user_id:
            continue
        upsert_auth_user(
            external_user_id=external_user_id,
            email=(row.get("email") or "").strip().lower() or None,
            display_name=row.get("display_name") or None,
            provider_issuer="local-dev-enterprise-seed",
            user_metadata_json=_seed_user_metadata(row),
        )

    membership_map: dict[str, list[str]] = {}
    for row in memberships:
        external_user_id = row.get("external_user_id", "").strip()
        group_name = row.get("group_name", "").strip()
        if external_user_id and group_name:
            membership_map.setdefault(external_user_id, []).append(group_name)
    for external_user_id, group_names in membership_map.items():
        replace_user_memberships(external_user_id=external_user_id, group_names=group_names)

    source_id_by_key: dict[str, int] = {}
    for row in sources:
        source_key = row.get("source_key", "").strip()
        storage_path = row.get("storage_path", "").strip()
        if not source_key or not storage_path:
            continue
        content_text = row.get("content_text", "").strip()
        source_id = upsert_source(
            storage_path=storage_path,
            file_name=row.get("file_name", "").strip() or source_key,
            source_type=row.get("source_type", "").strip() or "pdf",
            mime_type=row.get("mime_type", "").strip() or None,
            sensitivity_label=row.get("sensitivity_label", "").strip() or "internal",
            hash_sha256=sha256(f"{source_key}:{storage_path}:{content_text}".encode("utf-8")).hexdigest(),
            file_size_bytes=max(len(content_text.encode("utf-8")), 1),
            ingestion_status="embedded",
            enrichment_status="not_started",
            source_metadata_json=_normalize_source_metadata(row),
        )
        source_id_by_key[source_key] = source_id
        delete_chunks_for_source(source_id)
        if content_text:
            insert_chunks(
                source_id,
                [
                    {
                        "chunk_index": 0,
                        "heading": row.get("heading", "").strip() or row.get("file_name", "").strip() or source_key,
                        "section_path": "seed:1",
                        "chunk_text": content_text,
                        "token_count": len(content_text.split()),
                        "locator_json": {"seed_source_key": source_key, "page": 1},
                        "provenance_json": {"seed_pack": "enterprise_acl", "source_key": source_key},
                    }
                ],
            )

    source_acl_map: dict[str, list[str]] = {}
    for row in source_acl_rows:
        source_key = row.get("source_key", "").strip()
        group_name = row.get("group_name", "").strip()
        if source_key and group_name:
            source_acl_map.setdefault(source_key, []).append(group_name)
    for source_key, group_names in source_acl_map.items():
        source_id = source_id_by_key.get(source_key)
        if source_id is not None:
            replace_source_acl(source_id=source_id, group_names=group_names)

    contacts_by_source: dict[str, list[dict[str, Any]]] = {}
    for row in source_contacts:
        source_key = row.get("source_key", "").strip()
        if not source_key:
            continue
        contacts_by_source.setdefault(source_key, []).append(
            {
                "contact_role": (row.get("contact_role") or "").strip().lower(),
                "contact_external_user_id": row.get("contact_external_user_id") or None,
                "contact_email": (row.get("contact_email") or "").strip().lower() or None,
                "contact_display_name": row.get("contact_display_name") or None,
                "contact_metadata_json": {
                    "seed_pack": "enterprise_acl",
                    "seed_source_key": source_key,
                },
            }
        )
    for source_key, contacts in contacts_by_source.items():
        source_id = source_id_by_key.get(source_key)
        if source_id is not None:
            upsert_source_access_contacts(source_id, contacts)

    return {
        "pack_dir": str(pack_dir.relative_to(Path(REPO_ROOT))),
        "users": len(users),
        "groups": len(groups),
        "memberships": len(membership_map),
        "sources": len(source_id_by_key),
        "source_acl_mappings": sum(len(values) for values in source_acl_map.values()),
        "source_contacts": sum(len(values) for values in contacts_by_source.values()),
    }


def main() -> None:
    summary = seed_enterprise_acl_pack()
    print(summary)


if __name__ == "__main__":
    main()
