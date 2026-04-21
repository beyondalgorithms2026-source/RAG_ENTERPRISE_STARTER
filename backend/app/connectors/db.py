from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import create_engine, text

from app.adapters import ParsedSourceDocument, ParsedSourcePart
from app.corpus_policies import resolve_policy_name_from_source_metadata
from app.core.logging import log_event
from app.db.repo_acl import assign_document_acl
from app.db.repo_chunks import check_chunks_exist, delete_chunks_for_source, insert_chunks
from app.db.repo_connectors import (
    DbConnectorRow,
    get_db_connector,
    mark_db_connector_sync_completed,
    mark_db_connector_sync_failed,
    mark_db_connector_sync_started,
)
from app.db.repo_jobs import create_ingestion_job, finish_ingestion_job, update_ingestion_job
from app.db.repo_source_parts import delete_source_parts_for_source, insert_source_part
from app.db.repo_sources import get_source_by_id, update_source_status, upsert_source
from app.embedding.process import process_embeddings
from app.ingestion.chunking import chunk_parsed_document
from app.ingestion.enrichment import run_post_ingestion_enrichment


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?$")


def _validate_identifier(value: str, label: str) -> str:
    normalized = str(value or "").strip()
    if not _IDENTIFIER_RE.fullmatch(normalized):
        raise ValueError(f"Invalid {label}: {value}")
    return normalized


def _column_list(connector: DbConnectorRow) -> List[str]:
    columns = [connector.id_column, connector.updated_at_column, *connector.text_columns_json, *connector.metadata_columns_json]
    seen: set[str] = set()
    result: List[str] = []
    for column in columns:
        normalized = _validate_identifier(column, "column name")
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def _select_incremental_rows(connector: DbConnectorRow, *, row_limit: int) -> List[Dict[str, Any]]:
    table_name = _validate_identifier(connector.table_name, "table name")
    id_column = _validate_identifier(connector.id_column, "id column")
    updated_at_column = _validate_identifier(connector.updated_at_column, "updated_at column")
    columns = _column_list(connector)
    quoted_columns = ", ".join(columns)
    params: Dict[str, Any] = {"limit": max(1, min(int(row_limit or 200), 1000))}
    where_clause = ""
    if connector.last_cursor_updated_at is not None and connector.last_cursor_id is not None:
        where_clause = (
            f"WHERE {updated_at_column} > :last_cursor_updated_at "
            f"OR ({updated_at_column} = :last_cursor_updated_at AND CAST({id_column} AS TEXT) > :last_cursor_id)"
        )
        params["last_cursor_updated_at"] = connector.last_cursor_updated_at
        params["last_cursor_id"] = connector.last_cursor_id

    sql = text(
        f"""
        SELECT {quoted_columns}
        FROM {table_name}
        {where_clause}
        ORDER BY {updated_at_column} ASC, {id_column} ASC
        LIMIT :limit
        """
    )
    source_engine = create_engine(_sqlalchemy_url(connector.db_url))
    try:
        with source_engine.connect() as conn:
            rows = conn.execute(sql, params).mappings().all()
    finally:
        source_engine.dispose()
    return [dict(row) for row in rows]


def _sqlalchemy_url(db_url: str) -> str:
    if db_url.startswith("mysql://"):
        return db_url.replace("mysql://", "mysql+pymysql://", 1)
    if db_url.startswith("postgres://"):
        return db_url.replace("postgres://", "postgresql://", 1)
    return db_url


def inspect_db_connector_schema(connector: DbConnectorRow) -> Dict[str, Any]:
    source_engine = create_engine(_sqlalchemy_url(connector.db_url))
    try:
        with source_engine.connect() as conn:
            result = conn.execute(text(f"SELECT * FROM {_validate_identifier(connector.table_name, 'table name')} LIMIT 0"))
            columns = [{"name": item} for item in result.keys()]
    finally:
        source_engine.dispose()
    configured = set(_column_list(connector))
    return {
        "connector_id": connector.id,
        "table_name": connector.table_name,
        "columns": [{**column, "configured": column["name"] in configured} for column in columns],
        "configured_columns": sorted(configured),
    }


def preview_db_connector_sync(connector: DbConnectorRow, *, row_limit: int = 200) -> Dict[str, Any]:
    rows = _select_incremental_rows(connector, row_limit=row_limit)
    return {
        "connector_id": connector.id,
        "table_name": connector.table_name,
        "preview_row_count": len(rows),
        "row_limit": row_limit,
        "first_row": rows[0] if rows else None,
        "metadata_columns": connector.metadata_columns_json,
        "text_columns": connector.text_columns_json,
        "acl_group_names": connector.acl_group_names_json,
    }


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def serialize_db_row(connector: DbConnectorRow, row: Dict[str, Any]) -> ParsedSourceDocument:
    row_id = _stringify(row.get(connector.id_column))
    updated_at = _stringify(row.get(connector.updated_at_column))
    metadata = {
        "connector": "db",
        "connector_id": connector.id,
        "connection_name": connector.name,
        "connector_type": connector.connector_type,
        "table": connector.table_name,
        "row_id": row_id,
        "updated_at": updated_at,
        "corpus": connector.corpus_name,
        "corpus_policy": "db_rows",
    }
    for column in connector.metadata_columns_json:
        metadata[column] = _stringify(row.get(column))

    text_lines = [f"{connector.table_name} row {row_id}", f"{connector.updated_at_column}: {updated_at}"]
    for column in connector.text_columns_json:
        value = _stringify(row.get(column)).strip()
        if value:
            text_lines.append(f"{column}: {value}")
    for column in connector.metadata_columns_json:
        value = _stringify(row.get(column)).strip()
        if value:
            text_lines.append(f"{column}: {value}")

    return ParsedSourceDocument(
        source_type="db_row",
        title=f"{connector.table_name}#{row_id}",
        metadata=metadata,
        parts=[
            ParsedSourcePart(
                part_type="db_row",
                part_index=0,
                title=f"{connector.table_name} row {row_id}",
                locator_json=metadata,
                content_text="\n".join(text_lines),
                provenance_json={**metadata, "source": "db_connector"},
            )
        ],
    )


def _hash_row(connector: DbConnectorRow, row: Dict[str, Any]) -> str:
    payload = "|".join(_stringify(row.get(column)) for column in _column_list(connector))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _persist_source_parts(source_id: int, parsed: ParsedSourceDocument) -> Dict[int, int]:
    part_ids: Dict[int, int] = {}
    for part in parsed.parts:
        part_ids[part.part_index] = insert_source_part(
            source_id=source_id,
            part_type=part.part_type,
            part_index=part.part_index,
            title=part.title,
            locator_json=part.locator_json,
            content_text=part.content_text,
            provenance_json=part.provenance_json,
        )
    return part_ids


def _link_chunks(chunks: Iterable[Dict[str, Any]], part_ids: Dict[int, int]) -> List[Dict[str, Any]]:
    linked: List[Dict[str, Any]] = []
    for chunk in chunks:
        next_chunk = dict(chunk)
        part_index = (next_chunk.get("provenance_json") or {}).get("source_part_index")
        if part_index in part_ids:
            next_chunk["source_part_id"] = part_ids[part_index]
        linked.append(next_chunk)
    return linked


def _ingest_row(connector: DbConnectorRow, row: Dict[str, Any]) -> int:
    parsed = serialize_db_row(connector, row)
    row_id = _stringify(row.get(connector.id_column))
    updated_at = _stringify(row.get(connector.updated_at_column))
    metadata = dict(parsed.metadata)
    metadata["row_updated_at"] = updated_at
    metadata["source_row_storage_path"] = f"connector/db/{connector.id}/{connector.table_name}/{row_id}"
    hash_sha256 = _hash_row(connector, row)
    source_id = upsert_source(
        storage_path=metadata["source_row_storage_path"],
        file_name=f"{connector.name}:{connector.table_name}#{row_id}",
        source_type="db_row",
        hash_sha256=hash_sha256,
        mime_type="application/x-db-row",
        file_size_bytes=len(parsed.parts[0].content_text.encode("utf-8")),
        ingestion_status="processing",
        enrichment_status="not_started",
        source_metadata_json=metadata,
    )
    if connector.acl_group_names_json:
        assign_document_acl(source_id=source_id, group_names=connector.acl_group_names_json)

    job_id = create_ingestion_job(
        source_id=source_id,
        status="processing",
        stage="db_row_serialization",
        priority=120,
        triggered_by="db_connector",
        job_metadata_json={
            "connector_id": connector.id,
            "connection_name": connector.name,
            "table_name": connector.table_name,
            "row_id": row_id,
            "row_updated_at": updated_at,
            "queue_stage_label": "db row serialization",
        },
    )
    update_ingestion_job(job_id, status="processing", stage="chunking")
    delete_source_parts_for_source(source_id)
    if check_chunks_exist(source_id):
        delete_chunks_for_source(source_id)
    part_ids = _persist_source_parts(source_id, parsed)
    policy_name = resolve_policy_name_from_source_metadata(metadata)
    chunks = _link_chunks(chunk_parsed_document(parsed, policy_name=policy_name), part_ids)
    insert_chunks(source_id, chunks)
    update_source_status(source_id, ingestion_status="chunked")
    update_ingestion_job(job_id, status="processing", stage="embedding", job_metadata_json={"connector_id": connector.id, "actual_chunk_count": len(chunks)})
    embed_stats = process_embeddings(force=False, source_id=source_id)
    if embed_stats["chunks_embedded"] < len(chunks):
        raise RuntimeError(f"Only embedded {embed_stats['chunks_embedded']} of {len(chunks)} DB row chunk(s)")
    update_source_status(source_id, ingestion_status="embedded")
    run_post_ingestion_enrichment(source_id=source_id, source_part_count=len(part_ids), chunk_count=len(chunks), record_job=False)
    finish_ingestion_job(job_id, status="completed")
    update_ingestion_job(job_id, status="completed", stage="embedded")
    return source_id


def ingest_db_connector(connector_id: int, *, row_limit: int = 200) -> Dict[str, Any]:
    connector = get_db_connector(connector_id)
    if connector is None:
        raise ValueError(f"DB connector {connector_id} not found")
    mark_db_connector_sync_started(connector_id)
    rows_ingested = 0
    source_ids: List[int] = []
    last_updated_at: Optional[str] = None
    last_id: Optional[str] = None
    try:
        rows = _select_incremental_rows(connector, row_limit=row_limit)
        for row in rows:
            source_ids.append(_ingest_row(connector, row))
            rows_ingested += 1
            last_updated_at = _stringify(row.get(connector.updated_at_column)) or last_updated_at
            last_id = _stringify(row.get(connector.id_column)) or last_id
        mark_db_connector_sync_completed(
            connector_id=connector_id,
            last_cursor_updated_at=last_updated_at,
            last_cursor_id=last_id,
            rows_ingested=rows_ingested,
        )
        log_event("connector.db.sync.completed", source_id=source_ids[-1] if source_ids else None, stage="connector", status="completed", reason=connector.name)
        return {"status": "completed", "connector_id": connector_id, "rows_ingested": rows_ingested, "source_ids": source_ids}
    except Exception as exc:
        mark_db_connector_sync_failed(connector_id, str(exc))
        source = get_source_by_id(source_ids[-1]) if source_ids else None
        log_event("connector.db.sync.failed", level=40, source_id=source.id if source else None, stage="connector", status="failed", reason=str(exc))
        raise
