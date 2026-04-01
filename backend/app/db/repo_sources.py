import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.db.db import engine


_RESERVED_METADATA_SECTIONS = {"graph", "temporal", "lazy_enrichment"}


@dataclass
class SourceRow:
    id: int
    file_name: str
    storage_path: str
    source_type: str
    mime_type: Optional[str]
    hash_sha256: str
    sensitivity_label: str
    file_size_bytes: Optional[int]
    ingestion_status: str
    enrichment_status: str
    source_metadata_json: Dict


def _row_to_source(row) -> SourceRow:
    return SourceRow(*row)


def get_source_by_storage_path(storage_path: str) -> Optional[SourceRow]:
    sql = text(
        """
        SELECT id, file_name, storage_path, source_type, mime_type, hash_sha256,
               sensitivity_label, file_size_bytes, ingestion_status, enrichment_status, source_metadata_json
        FROM sources
        WHERE storage_path = :storage_path
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"storage_path": storage_path}).first()
    if not row:
        return None
    return _row_to_source(row)


def get_source_by_id(source_id: int) -> Optional[SourceRow]:
    sql = text(
        """
        SELECT id, file_name, storage_path, source_type, mime_type, hash_sha256,
               sensitivity_label, file_size_bytes, ingestion_status, enrichment_status, source_metadata_json
        FROM sources
        WHERE id = :source_id
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"source_id": source_id}).first()
    if not row:
        return None
    return _row_to_source(row)


def get_sources_by_ids(source_ids: List[int]) -> Dict[int, SourceRow]:
    if not source_ids:
        return {}

    sql = text(
        """
        SELECT id, file_name, storage_path, source_type, mime_type, hash_sha256,
               sensitivity_label, file_size_bytes, ingestion_status, enrichment_status, source_metadata_json
        FROM sources
        WHERE id = ANY(:source_ids)
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"source_ids": list(source_ids)}).fetchall()
    return {row[0]: _row_to_source(row) for row in rows}


def find_source_by_name_and_hash(file_name: str, hash_sha256: str) -> Optional[SourceRow]:
    sql = text(
        """
        SELECT id, file_name, storage_path, source_type, mime_type, hash_sha256,
               sensitivity_label, file_size_bytes, ingestion_status, enrichment_status, source_metadata_json
        FROM sources
        WHERE file_name = :file_name AND hash_sha256 = :hash_sha256
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"file_name": file_name, "hash_sha256": hash_sha256}).first()
    if not row:
        return None
    return _row_to_source(row)


def get_latest_source_by_name(file_name: str) -> Optional[SourceRow]:
    sql = text(
        """
        SELECT id, file_name, storage_path, source_type, mime_type, hash_sha256,
               sensitivity_label, file_size_bytes, ingestion_status, enrichment_status, source_metadata_json
        FROM sources
        WHERE file_name = :file_name
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"file_name": file_name}).first()
    if not row:
        return None
    return _row_to_source(row)


def upsert_source(
    *,
    storage_path: str,
    file_name: str,
    source_type: str,
    hash_sha256: str,
    mime_type: Optional[str] = None,
    sensitivity_label: str = "internal",
    file_size_bytes: Optional[int] = None,
    ingestion_status: str = "pending",
    enrichment_status: str = "not_started",
    source_metadata_json: Optional[Dict] = None,
) -> int:
    sql = text(
        """
        INSERT INTO sources (
            storage_path, file_name, source_type, sensitivity_label, mime_type, hash_sha256,
            file_size_bytes, ingestion_status, enrichment_status, source_metadata_json
        )
        VALUES (
            :storage_path, :file_name, :source_type, :sensitivity_label, :mime_type, :hash_sha256,
            :file_size_bytes, :ingestion_status, :enrichment_status, CAST(:source_metadata_json AS jsonb)
        )
        ON CONFLICT (storage_path) DO UPDATE
        SET file_name = EXCLUDED.file_name,
            source_type = EXCLUDED.source_type,
            sensitivity_label = EXCLUDED.sensitivity_label,
            mime_type = EXCLUDED.mime_type,
            hash_sha256 = EXCLUDED.hash_sha256,
            file_size_bytes = EXCLUDED.file_size_bytes,
            ingestion_status = EXCLUDED.ingestion_status,
            enrichment_status = EXCLUDED.enrichment_status,
            source_metadata_json = EXCLUDED.source_metadata_json,
            updated_at = now()
        RETURNING id
        """
    )
    params = {
        "storage_path": storage_path,
        "file_name": file_name,
        "source_type": source_type,
        "sensitivity_label": sensitivity_label,
        "mime_type": mime_type,
        "hash_sha256": hash_sha256,
        "file_size_bytes": file_size_bytes,
        "ingestion_status": ingestion_status,
        "enrichment_status": enrichment_status,
        "source_metadata_json": json.dumps(source_metadata_json or {}),
    }
    with engine.begin() as conn:
        return conn.execute(sql, params).scalar_one()


def list_sources() -> List[SourceRow]:
    sql = text(
        """
        SELECT id, file_name, storage_path, source_type, mime_type, hash_sha256,
               sensitivity_label, file_size_bytes, ingestion_status, enrichment_status, source_metadata_json
        FROM sources
        ORDER BY created_at DESC, id DESC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()
    return [_row_to_source(row) for row in rows]


def update_source_admin_fields(
    source_id: int,
    *,
    file_name: Optional[str] = None,
    sensitivity_label: Optional[str] = None,
    source_metadata_json: Optional[Dict] = None,
) -> bool:
    updates = []
    params: Dict[str, Any] = {"source_id": source_id}
    if file_name is not None:
        updates.append("file_name = :file_name")
        params["file_name"] = file_name
    if sensitivity_label is not None:
        updates.append("sensitivity_label = :sensitivity_label")
        params["sensitivity_label"] = sensitivity_label
    if source_metadata_json is not None:
        updates.append("source_metadata_json = CAST(:source_metadata_json AS jsonb)")
        params["source_metadata_json"] = json.dumps(source_metadata_json)
    if not updates:
        return False

    updates.append("updated_at = now()")
    sql = text(f"UPDATE sources SET {', '.join(updates)} WHERE id = :source_id")
    with engine.begin() as conn:
        result = conn.execute(sql, params)
    return result.rowcount > 0


def delete_source(source_id: int) -> bool:
    sql = text("DELETE FROM sources WHERE id = :source_id")
    with engine.begin() as conn:
        result = conn.execute(sql, {"source_id": source_id})
    return result.rowcount > 0


def update_source_status(source_id: int, *, ingestion_status: Optional[str] = None, enrichment_status: Optional[str] = None) -> None:
    updates = []
    params = {"source_id": source_id}
    if ingestion_status is not None:
        updates.append("ingestion_status = :ingestion_status")
        params["ingestion_status"] = ingestion_status
    if enrichment_status is not None:
        updates.append("enrichment_status = :enrichment_status")
        params["enrichment_status"] = enrichment_status
    if not updates:
        return

    updates.append("updated_at = now()")
    sql = text(f"UPDATE sources SET {', '.join(updates)} WHERE id = :source_id")
    with engine.begin() as conn:
        conn.execute(sql, params)


def _deep_merge_metadata(current_value: Any, patch_value: Any) -> Any:
    if isinstance(current_value, dict) and isinstance(patch_value, dict):
        merged = dict(current_value)
        for key, value in patch_value.items():
            merged[key] = _deep_merge_metadata(merged.get(key), value)
        return merged
    return patch_value


def _normalize_source_metadata(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _validate_metadata_patch(metadata_patch: Dict[str, Any]) -> None:
    if not isinstance(metadata_patch, dict):
        raise TypeError("source metadata patch must be a dict")

    for section_name in _RESERVED_METADATA_SECTIONS:
        if section_name in metadata_patch and not isinstance(metadata_patch[section_name], dict):
            raise ValueError(f"source metadata section '{section_name}' must be a dict")


def _merge_source_metadata(current_metadata: Any, metadata_patch: Dict[str, Any]) -> Dict[str, Any]:
    _validate_metadata_patch(metadata_patch)
    current = _normalize_source_metadata(current_metadata)
    return _deep_merge_metadata(current, metadata_patch)


def merge_source_metadata(source_id: int, metadata_patch: Dict) -> None:
    current = get_source_by_id(source_id)
    if current is None:
        return

    # Source metadata holds multiple independent internal contracts
    # (graph, temporal, lazy_enrichment, upload metadata, etc.). Merge
    # dict patches recursively so one nested update does not overwrite
    # unrelated sibling fields under the same top-level section.
    merged = _merge_source_metadata(current.source_metadata_json, metadata_patch)

    sql = text(
        """
        UPDATE sources
        SET source_metadata_json = CAST(:source_metadata_json AS jsonb),
            updated_at = now()
        WHERE id = :source_id
        """
    )
    with engine.begin() as conn:
        conn.execute(
            sql,
            {"source_id": source_id, "source_metadata_json": json.dumps(merged)},
        )


def remove_source_metadata_sections(source_id: int, section_names: List[str]) -> None:
    current = get_source_by_id(source_id)
    if current is None:
        return

    metadata = _normalize_source_metadata(current.source_metadata_json)
    for section_name in section_names:
        metadata.pop(section_name, None)

    sql = text(
        """
        UPDATE sources
        SET source_metadata_json = CAST(:source_metadata_json AS jsonb),
            updated_at = now()
        WHERE id = :source_id
        """
    )
    with engine.begin() as conn:
        conn.execute(
            sql,
            {"source_id": source_id, "source_metadata_json": json.dumps(metadata)},
        )


def update_source_graph_metadata(source_id: int, graph_metadata: Dict) -> None:
    merge_source_metadata(source_id, {"graph": graph_metadata})


def update_source_temporal_metadata(source_id: int, temporal_metadata: Dict) -> None:
    merge_source_metadata(source_id, {"temporal": temporal_metadata})


def record_lazy_enrichment_trace(source_id: int, trace_metadata: Dict) -> None:
    merge_source_metadata(source_id, {"lazy_enrichment": trace_metadata})
