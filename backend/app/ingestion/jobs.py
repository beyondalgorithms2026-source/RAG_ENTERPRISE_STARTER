import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy import text

from app.adapters import ParsedSourceDocument, parse_source_bytes
from app.core.config import REPO_ROOT, settings
from app.core.logging import log_event, logger
from app.db.db import engine
from app.db.repo_chunks import check_chunks_exist, delete_chunks_for_source, insert_chunks
from app.db.repo_jobs import create_ingestion_job, finish_ingestion_job
from app.db.repo_source_parts import delete_source_parts_for_source, insert_source_part
from app.db.repo_sources import (
    delete_source,
    find_source_by_name_and_hash,
    get_latest_source_by_name,
    get_source_by_id,
    remove_source_metadata_sections,
    update_source_status,
    upsert_source,
)
from app.embedding.process import process_embeddings
from app.ingestion.chunking import chunk_parsed_document
from app.ingestion.enrichment import run_post_ingestion_enrichment


_EXTENSION_TO_MIME = {
    "pdf": {"application/pdf"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    "eml": {"message/rfc822", "application/octet-stream", "text/plain"},
    "txt": {"text/plain", "application/octet-stream"},
    "md": {"text/markdown", "text/x-markdown", "text/plain", "application/octet-stream"},
}


def _safe_filename(file_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", file_name).strip("._") or "upload.bin"


def _file_extension(file_name: str) -> str:
    return Path(file_name).suffix.lower().lstrip(".")


def _compute_sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _ensure_upload_dir() -> Path:
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _detect_source_type(file_name: str) -> str:
    extension = _file_extension(file_name)
    if extension not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail={"error": "unsupported_file_type", "file_name": file_name})
    return extension


def _validate_mime(source_type: str, content_type: Optional[str]) -> None:
    if not content_type:
        return
    allowed = _EXTENSION_TO_MIME.get(source_type, set())
    if allowed and content_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail={"error": "unsupported_mime_type", "source_type": source_type, "content_type": content_type},
        )


def _storage_path_for(file_name: str, hash_sha256: str) -> str:
    safe_name = _safe_filename(file_name)
    return os.path.join("data", "uploads", f"{hash_sha256}__{safe_name}")


def _ensure_valid_upload_content(*, content: bytes, file_name: str) -> None:
    if not content:
        raise HTTPException(status_code=400, detail={"error": "empty_upload", "file_name": file_name})
    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail={"error": "file_too_large", "file_name": file_name, "max_bytes": settings.MAX_UPLOAD_SIZE_BYTES},
        )


def _existing_upload_skip_result(*, file_name: str, hash_sha256: str) -> Optional[Dict[str, Any]]:
    existing_same = find_source_by_name_and_hash(file_name, hash_sha256)
    if not existing_same:
        return None

    job_id = create_ingestion_job(
        source_id=existing_same.id,
        status="skipped",
        stage="deduplicated",
        triggered_by="upload",
        job_metadata_json={"reason": "unchanged_reupload", "hash_sha256": hash_sha256},
    )
    log_event(
        "upload.skipped",
        source_id=existing_same.id,
        job_id=job_id,
        stage="upload",
        status="skipped",
        reason="unchanged_reupload",
    )
    return {
        "status": "skipped",
        "source_id": existing_same.id,
        "job_id": job_id,
        "file_name": existing_same.file_name,
        "source_type": existing_same.source_type,
        "hash_sha256": existing_same.hash_sha256,
        "storage_path": existing_same.storage_path,
    }


def _persist_upload_bytes(*, storage_path: str, content: bytes) -> Path:
    _ensure_upload_dir()
    absolute_path = Path(REPO_ROOT) / storage_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(content)
    return absolute_path


def _build_upload_metadata(*, file_name: str, content_type: Optional[str], hash_sha256: str) -> Dict[str, Any]:
    previous_source = get_latest_source_by_name(file_name)
    return {
        "original_file_name": file_name,
        "upload_content_type": content_type,
        "reupload_of_source_id": previous_source.id if previous_source and previous_source.hash_sha256 != hash_sha256 else None,
    }


def _queue_upload_source(
    *,
    file_name: str,
    source_type: str,
    hash_sha256: str,
    content_type: Optional[str],
    file_size_bytes: int,
    storage_path: str,
    metadata: Dict[str, Any],
) -> tuple[int, int]:
    source_id = upsert_source(
        storage_path=storage_path,
        file_name=file_name,
        source_type=source_type,
        hash_sha256=hash_sha256,
        mime_type=content_type,
        file_size_bytes=file_size_bytes,
        ingestion_status="queued",
        enrichment_status="not_started",
        source_metadata_json=metadata,
    )
    job_id = create_ingestion_job(
        source_id=source_id,
        status="queued",
        stage="uploaded",
        triggered_by="upload",
        job_metadata_json={"hash_sha256": hash_sha256, "storage_path": storage_path},
    )
    return source_id, job_id


def _debug_artifact_path(storage_path: str) -> Path:
    source_name = Path(storage_path).name
    return Path(REPO_ROOT) / "data" / "extracted" / f"{source_name}.json"


def _chunk_preview_path(storage_path: str) -> Path:
    source_name = Path(storage_path).name
    return Path(REPO_ROOT) / "data" / "extracted" / f"{source_name}.chunks.json"


def _update_ingestion_job_stage(job_id: int, *, status: str, stage: str, error_message: Optional[str] = None) -> None:
    sql = text(
        """
        UPDATE ingestion_jobs
        SET status = :status,
            stage = :stage,
            error_message = :error_message
        WHERE id = :job_id
        """
    )
    with engine.begin() as conn:
        conn.execute(sql, {"job_id": job_id, "status": status, "stage": stage, "error_message": error_message})


def _source_file_absolute_path(storage_path: str) -> Path:
    return Path(REPO_ROOT) / storage_path


def _assert_source_file_exists(storage_path: str) -> None:
    absolute_path = _source_file_absolute_path(storage_path)
    if not absolute_path.exists():
        raise FileNotFoundError(f"Source file not found at {absolute_path}")


def _persist_source_parts(source_id: int, parsed: ParsedSourceDocument) -> Dict[int, int]:
    source_part_ids: Dict[int, int] = {}
    for part in parsed.parts:
        parent_part_id = source_part_ids.get(part.parent_part_index) if part.parent_part_index is not None else None
        source_part_ids[part.part_index] = insert_source_part(
            source_id=source_id,
            part_type=part.part_type,
            part_index=part.part_index,
            title=part.title,
            parent_part_id=parent_part_id,
            locator_json=part.locator_json,
            content_text=part.content_text,
            provenance_json=part.provenance_json,
        )
    return source_part_ids


def _link_chunks_to_source_parts(chunks: list[Dict[str, Any]], source_part_ids: Dict[int, int]) -> list[Dict[str, Any]]:
    linked_chunks: list[Dict[str, Any]] = []
    for chunk in chunks:
        chunk_copy = dict(chunk)
        source_part_index = (chunk_copy.get("provenance_json") or {}).get("source_part_index")
        if source_part_index is not None and source_part_index in source_part_ids:
            chunk_copy["source_part_id"] = source_part_ids[source_part_index]
        linked_chunks.append(chunk_copy)
    return linked_chunks


def _ingest_uploaded_source(*, source_id: int, source_type: str, file_name: str, storage_path: str, job_id: int) -> Dict[str, Any]:
    try:
        log_event("upload.ingestion.started", source_id=source_id, job_id=job_id, stage="ingestion", status="processing")
        _update_ingestion_job_stage(job_id, status="processing", stage="parsing")
        log_event("parse.started", source_id=source_id, job_id=job_id, stage="parse", status="processing")
        parsed = parse_uploaded_source_file(
            source_type=source_type,
            file_name=file_name,
            storage_path=storage_path,
            persist_debug_artifact=False,
        )
        log_event("parse.completed", source_id=source_id, job_id=job_id, stage="parse", status="completed")

        _update_ingestion_job_stage(job_id, status="processing", stage="source_parts")
        source_part_ids = _persist_source_parts(source_id, parsed)
        log_event(
            "source_parts.completed",
            source_id=source_id,
            job_id=job_id,
            stage="source_parts",
            status="completed",
            reason="parsed_parts_persisted",
        )

        _update_ingestion_job_stage(job_id, status="processing", stage="chunking")
        log_event("chunk.started", source_id=source_id, job_id=job_id, stage="chunk", status="processing")
        chunks = chunk_parsed_document(parsed)
        linked_chunks = _link_chunks_to_source_parts(chunks, source_part_ids)
        if check_chunks_exist(source_id):
            delete_chunks_for_source(source_id)
        insert_chunks(source_id, linked_chunks)
        update_source_status(source_id, ingestion_status="chunked")
        log_event(
            "chunk.completed",
            source_id=source_id,
            job_id=job_id,
            stage="chunk",
            status="completed",
            reason="chunks_persisted",
        )

        _update_ingestion_job_stage(job_id, status="processing", stage="embedding")
        log_event("embed.started", source_id=source_id, job_id=job_id, stage="embed", status="processing")
        embed_stats = process_embeddings(force=False, source_id=source_id)
        if embed_stats["chunks_embedded"] < len(linked_chunks):
            raise RuntimeError(
                f"Only embedded {embed_stats['chunks_embedded']} of {len(linked_chunks)} chunk(s) for source_id={source_id}"
            )
        log_event(
            "embed.completed",
            source_id=source_id,
            job_id=job_id,
            stage="embed",
            status="completed",
            reason="embeddings_persisted",
        )

        update_source_status(source_id, ingestion_status="embedded")
        run_post_ingestion_enrichment(
            source_id=source_id,
            source_part_count=len(source_part_ids),
            chunk_count=len(linked_chunks),
            record_job=False,
        )
        finish_ingestion_job(job_id, status="completed")
        _update_ingestion_job_stage(job_id, status="completed", stage="embedded")
        log_event("upload.ingestion.completed", source_id=source_id, job_id=job_id, stage="ingestion", status="completed")
        return {"chunk_count": len(linked_chunks), "source_part_count": len(source_part_ids)}
    except Exception as exc:
        update_source_status(source_id, ingestion_status="failed")
        finish_ingestion_job(job_id, status="failed", error_message=str(exc))
        _update_ingestion_job_stage(job_id, status="failed", stage="failed", error_message=str(exc))
        log_event(
            "upload.ingestion.failed",
            level=40,
            source_id=source_id,
            job_id=job_id,
            stage="ingestion",
            status="failed",
            reason=str(exc),
        )
        raise


def parse_uploaded_source_file(
    *,
    source_type: str,
    file_name: str,
    storage_path: str,
    persist_debug_artifact: bool = False,
) -> ParsedSourceDocument:
    absolute_path = Path(REPO_ROOT) / storage_path
    content = absolute_path.read_bytes()
    parsed = parse_source_bytes(source_type, content, file_name)
    if persist_debug_artifact:
        debug_path = _debug_artifact_path(storage_path)
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug_path.write_text(json.dumps(parsed.to_dict(), indent=2), encoding="utf-8")
    return parsed


def chunk_uploaded_source_file(
    *,
    source_type: str,
    file_name: str,
    storage_path: str,
    persist_chunk_preview: bool = False,
) -> Dict[str, Any]:
    parsed = parse_uploaded_source_file(
        source_type=source_type,
        file_name=file_name,
        storage_path=storage_path,
        persist_debug_artifact=False,
    )
    chunks = chunk_parsed_document(parsed)
    if persist_chunk_preview:
        preview_path = _chunk_preview_path(storage_path)
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview_path.write_text(json.dumps(chunks, indent=2), encoding="utf-8")
    return {
        "source_type": source_type,
        "file_name": file_name,
        "chunk_count": len(chunks),
        "chunks": chunks,
    }


async def process_upload(upload: UploadFile) -> Dict[str, Any]:
    file_name = upload.filename or "upload.bin"
    log_event("upload.received", stage="upload", status="received", reason=file_name)
    source_type = _detect_source_type(file_name)
    _validate_mime(source_type, upload.content_type)

    content = await upload.read()
    _ensure_valid_upload_content(content=content, file_name=file_name)

    hash_sha256 = _compute_sha256_bytes(content)
    existing_result = _existing_upload_skip_result(file_name=file_name, hash_sha256=hash_sha256)
    if existing_result is not None:
        return existing_result

    storage_path = _storage_path_for(file_name, hash_sha256)
    _persist_upload_bytes(storage_path=storage_path, content=content)

    metadata = _build_upload_metadata(file_name=file_name, content_type=upload.content_type, hash_sha256=hash_sha256)
    source_id, job_id = _queue_upload_source(
        file_name=file_name,
        source_type=source_type,
        hash_sha256=hash_sha256,
        file_size_bytes=len(content),
        content_type=upload.content_type,
        storage_path=storage_path,
        metadata=metadata,
    )
    _ingest_uploaded_source(
        source_id=source_id,
        source_type=source_type,
        file_name=file_name,
        storage_path=storage_path,
        job_id=job_id,
    )
    log_event("upload.accepted", source_id=source_id, job_id=job_id, stage="upload", status="accepted")
    return {
        "status": "queued",
        "source_id": source_id,
        "job_id": job_id,
        "file_name": file_name,
        "source_type": source_type,
        "hash_sha256": hash_sha256,
        "storage_path": storage_path,
        "reupload_of_source_id": metadata["reupload_of_source_id"],
    }


async def process_upload_batch(uploads: List[UploadFile]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for upload in uploads:
        results.append(await process_upload(upload))
    return results


def delete_uploaded_source(*, source_id: int, delete_file: bool = True) -> Dict[str, Any]:
    source = get_source_by_id(source_id)
    if source is None:
        raise ValueError(f"Source {source_id} not found")

    absolute_path = _source_file_absolute_path(source.storage_path)
    file_deleted = False
    if delete_file and absolute_path.exists():
        absolute_path.unlink()
        file_deleted = True

    deleted = delete_source(source_id)
    if not deleted:
        raise ValueError(f"Source {source_id} not found")

    log_event(
        "source.deleted",
        source_id=source_id,
        stage="delete",
        status="completed",
        reason=source.file_name,
    )
    return {
        "status": "deleted",
        "source_id": source_id,
        "file_name": source.file_name,
        "storage_path": source.storage_path,
        "file_deleted": file_deleted,
    }


def _reset_source_for_reindex(source_id: int) -> None:
    delete_chunks_for_source(source_id)
    delete_source_parts_for_source(source_id)
    remove_source_metadata_sections(source_id, ["graph", "temporal", "lazy_enrichment"])
    update_source_status(source_id, ingestion_status="queued", enrichment_status="not_started")


def admin_reindex_source(*, source_id: int, force: bool = False) -> Dict[str, Any]:
    source = get_source_by_id(source_id)
    if source is None:
        raise ValueError(f"Source {source_id} not found")
    if source.ingestion_status == "processing" and not force:
        raise ValueError(f"Source {source_id} is currently processing; rerun with force to override")

    _assert_source_file_exists(source.storage_path)
    log_event("admin.reindex.started", source_id=source_id, stage="admin_reindex", status="processing", reason=source.ingestion_status)
    _reset_source_for_reindex(source_id)
    job_id = create_ingestion_job(
        source_id=source_id,
        status="queued",
        stage="admin_reindex",
        triggered_by="admin_reindex",
        job_metadata_json={"force": force, "storage_path": source.storage_path},
    )
    stats = _ingest_uploaded_source(
        source_id=source_id,
        source_type=source.source_type,
        file_name=source.file_name,
        storage_path=source.storage_path,
        job_id=job_id,
    )
    log_event("admin.reindex.completed", source_id=source_id, job_id=job_id, stage="admin_reindex", status="completed")
    return {
        "status": "completed",
        "source_id": source_id,
        "job_id": job_id,
        "chunk_count": stats["chunk_count"],
        "source_part_count": stats["source_part_count"],
    }
