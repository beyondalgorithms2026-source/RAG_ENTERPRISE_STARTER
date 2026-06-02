import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy import text

from app.adapters import ParsedSourceDocument, parse_source_bytes
from app.corpus_policies import get_corpus_policy, resolve_policy_name_from_source_metadata
from app.core.config import REPO_ROOT, settings
from app.core.logging import log_event, logger
from app.auth.context import get_current_user
from app.db.db import engine
from app.db.repo_acl import assign_document_acl, list_source_acl_map
from app.db.repo_chunks import check_chunks_exist, delete_chunks_for_source, insert_chunks
from app.db.repo_jobs import create_attachment_link, create_ingestion_job, finish_ingestion_job, get_ingestion_job, update_ingestion_job
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


NUL_CHARACTER = "\x00"


_EXTENSION_TO_MIME = {
    "pdf": {"application/pdf"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    "eml": {"message/rfc822", "application/octet-stream", "text/plain"},
    "txt": {"text/plain", "application/octet-stream"},
    "md": {"text/markdown", "text/x-markdown", "text/plain", "application/octet-stream"},
}


def _strip_nul_text(value: str) -> str:
    return value.replace(NUL_CHARACTER, "")


def _sanitize_text_value(value: Any) -> Any:
    if isinstance(value, str):
        return _strip_nul_text(value)
    if isinstance(value, list):
        return [_sanitize_text_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_text_value(item) for item in value)
    if isinstance(value, dict):
        return {_sanitize_text_value(key): _sanitize_text_value(item) for key, item in value.items()}
    return value


def _sanitize_parsed_document(parsed: ParsedSourceDocument) -> ParsedSourceDocument:
    parsed.title = _sanitize_text_value(parsed.title)
    parsed.metadata = _sanitize_text_value(parsed.metadata)
    parsed.warnings = _sanitize_text_value(parsed.warnings)
    for part in parsed.parts:
        part.title = _sanitize_text_value(part.title)
        part.locator_json = _sanitize_text_value(part.locator_json)
        part.content_text = _sanitize_text_value(part.content_text)
        part.provenance_json = _sanitize_text_value(part.provenance_json)
    for attachment in parsed.attachments:
        attachment.file_name = _sanitize_text_value(attachment.file_name)
        attachment.content_type = _sanitize_text_value(attachment.content_type)
        attachment.content_disposition = _sanitize_text_value(attachment.content_disposition)
        attachment.content_id = _sanitize_text_value(attachment.content_id)
    return parsed


def _safe_filename(file_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", file_name).strip("._") or "upload.bin"


def _file_extension(file_name: str) -> str:
    return Path(file_name).suffix.lower().lstrip(".")


def _compute_sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _source_type_from_attachment(file_name: str, content_type: Optional[str]) -> Optional[str]:
    extension = _file_extension(file_name)
    if extension not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        return None
    allowed_mimes = _EXTENSION_TO_MIME.get(extension, set())
    if content_type and allowed_mimes and content_type not in allowed_mimes:
        return None
    return extension


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


async def _read_upload_limited(upload: UploadFile, *, file_name: str) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > settings.MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail={"error": "file_too_large", "file_name": file_name, "max_bytes": settings.MAX_UPLOAD_SIZE_BYTES},
            )
        chunks.append(chunk)
    return b"".join(chunks)


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


def _build_upload_metadata(*, file_name: str, source_type: str, content_type: Optional[str], hash_sha256: str) -> Dict[str, Any]:
    previous_source = get_latest_source_by_name(file_name)
    actor = get_current_user()
    metadata = {
        "original_file_name": file_name,
        "upload_content_type": content_type,
        "reupload_of_source_id": previous_source.id if previous_source and previous_source.hash_sha256 != hash_sha256 else None,
        "uploaded_by_external_user_id": actor.user_id if actor else None,
        "uploaded_by_email": actor.email if actor else None,
        "uploaded_by_display_name": actor.name if actor else None,
    }
    if source_type == "eml":
        metadata["corpus_policy"] = "email_casework"
    metadata["corpus_policy"] = resolve_policy_name_from_source_metadata(metadata)
    return metadata


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
    actor = get_current_user()
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
        stage="queued",
        priority=100,
        triggered_by="upload",
        owner_external_user_id=actor.user_id if actor else None,
        owner_email=actor.email if actor else None,
        owner_display_name=actor.name if actor else None,
        job_metadata_json={
            "hash_sha256": hash_sha256,
            "storage_path": storage_path,
            "file_size_bytes": file_size_bytes,
            "source_type": source_type,
            "queue_stage_label": "queued",
        },
    )
    return source_id, job_id


def _debug_artifact_path(storage_path: str) -> Path:
    source_name = Path(storage_path).name
    return Path(REPO_ROOT) / "data" / "extracted" / f"{source_name}.json"


def _chunk_preview_path(storage_path: str) -> Path:
    source_name = Path(storage_path).name
    return Path(REPO_ROOT) / "data" / "extracted" / f"{source_name}.chunks.json"


def _update_ingestion_job_stage(job_id: int, *, status: str, stage: str, error_message: Optional[str] = None) -> None:
    current = get_ingestion_job(job_id)
    next_metadata = dict(current.job_metadata_json or {}) if current else {}
    next_metadata["queue_stage_label"] = stage
    update_ingestion_job(
        job_id,
        status=status,
        stage=stage,
        error_message=error_message,
        job_metadata_json=next_metadata,
    )


def _merge_ingestion_job_metadata(job_id: int, patch: Dict[str, Any]) -> None:
    current = get_ingestion_job(job_id)
    if current is None:
        return
    next_metadata = dict(current.job_metadata_json or {})
    next_metadata.update(patch)
    update_ingestion_job(job_id, job_metadata_json=next_metadata)


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


def _ingest_email_attachment_children(*, parent_source_id: int, parsed: ParsedSourceDocument, job_id: int) -> Dict[str, Any]:
    if parsed.source_type not in {"eml", "email_message"}:
        return {"attachment_count": len(parsed.attachments), "child_source_ids": []}

    child_source_ids: list[int] = []
    parent_acl_groups = list_source_acl_map().get(parent_source_id, [])
    for index, attachment in enumerate(parsed.attachments):
        content = attachment.content_bytes or b""
        source_type = _source_type_from_attachment(attachment.file_name, attachment.content_type)
        if not content or source_type is None:
            continue

        hash_sha256 = _compute_sha256_bytes(content)
        storage_path = _storage_path_for(f"attachment-{parent_source_id}-{attachment.file_name}", hash_sha256)
        _persist_upload_bytes(storage_path=storage_path, content=content)
        metadata = {
            "parent_source_id": parent_source_id,
            "parent_source_type": parsed.source_type,
            "attachment_index": index,
            "attachment_content_id": attachment.content_id,
            "attachment_disposition": attachment.content_disposition,
            "attachment_of_email": True,
            "corpus_policy": "email_casework",
        }
        source_id = upsert_source(
            storage_path=storage_path,
            file_name=attachment.file_name,
            source_type=source_type,
            hash_sha256=hash_sha256,
            mime_type=attachment.content_type,
            file_size_bytes=len(content),
            ingestion_status="processing",
            enrichment_status="not_started",
            source_metadata_json=metadata,
        )
        if parent_acl_groups:
            assign_document_acl(source_id=source_id, group_names=parent_acl_groups)
        child_parsed = _sanitize_parsed_document(parse_source_bytes(source_type, content, attachment.file_name))
        delete_source_parts_for_source(source_id)
        child_part_ids = _persist_source_parts(source_id, child_parsed)
        chunks = chunk_parsed_document(child_parsed, policy_name="email_casework")
        linked_chunks = _link_chunks_to_source_parts(chunks, child_part_ids)
        if check_chunks_exist(source_id):
            delete_chunks_for_source(source_id)
        insert_chunks(source_id, linked_chunks)
        process_embeddings(force=False, source_id=source_id)
        update_source_status(source_id, ingestion_status="embedded")
        run_post_ingestion_enrichment(
            source_id=source_id,
            source_part_count=len(child_part_ids),
            chunk_count=len(linked_chunks),
            record_job=False,
        )
        create_attachment_link(
            parent_source_id=parent_source_id,
            child_source_id=source_id,
            attachment_metadata_json=attachment.to_dict(),
        )
        child_source_ids.append(source_id)

    if child_source_ids:
        _merge_ingestion_job_metadata(job_id, {"attachment_child_source_ids": child_source_ids})
    return {"attachment_count": len(parsed.attachments), "child_source_ids": child_source_ids}


def _ingest_uploaded_source(*, source_id: int, source_type: str, file_name: str, storage_path: str, job_id: int) -> Dict[str, Any]:
    try:
        update_source_status(source_id, ingestion_status="processing")
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
        _merge_ingestion_job_metadata(job_id, {"parsed_part_count": len(parsed.parts)})
        attachment_stats = _ingest_email_attachment_children(parent_source_id=source_id, parsed=parsed, job_id=job_id)
        if attachment_stats["child_source_ids"]:
            log_event(
                "email.attachments.completed",
                source_id=source_id,
                job_id=job_id,
                stage="attachments",
                status="completed",
                reason=f"{len(attachment_stats['child_source_ids'])} child source(s)",
            )

        _update_ingestion_job_stage(job_id, status="processing", stage="indexing_enrichment")
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
        source = get_source_by_id(source_id)
        policy_name = resolve_policy_name_from_source_metadata(source.source_metadata_json if source else {})
        chunks = chunk_parsed_document(parsed, policy_name=policy_name)
        linked_chunks = _link_chunks_to_source_parts(chunks, source_part_ids)
        if check_chunks_exist(source_id):
            delete_chunks_for_source(source_id)
        insert_chunks(source_id, linked_chunks)
        update_source_status(source_id, ingestion_status="chunked")
        _merge_ingestion_job_metadata(job_id, {"actual_chunk_count": len(linked_chunks)})
        log_event(
            "chunk.completed",
            source_id=source_id,
            job_id=job_id,
            stage="chunk",
            status="completed",
            reason="chunks_persisted",
        )
        log_event(
            "chunk.policy_applied",
            source_id=source_id,
            job_id=job_id,
            stage="chunk",
            status="completed",
            reason=get_corpus_policy(policy_name).name,
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
    parsed = _sanitize_parsed_document(parse_source_bytes(source_type, content, file_name))
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


def _run_ingestion_job(*, source_id: int, source_type: str, file_name: str, storage_path: str, job_id: int) -> None:
    _ingest_uploaded_source(
        source_id=source_id,
        source_type=source_type,
        file_name=file_name,
        storage_path=storage_path,
        job_id=job_id,
    )


async def process_upload(
    upload: UploadFile,
    *,
    wait_for_completion: bool = True,
    background_tasks: Any | None = None,
) -> Dict[str, Any]:
    file_name = upload.filename or "upload.bin"
    log_event("upload.received", stage="upload", status="received", reason=file_name)
    source_type = _detect_source_type(file_name)
    _validate_mime(source_type, upload.content_type)

    content = await _read_upload_limited(upload, file_name=file_name)
    _ensure_valid_upload_content(content=content, file_name=file_name)

    hash_sha256 = _compute_sha256_bytes(content)
    existing_result = _existing_upload_skip_result(file_name=file_name, hash_sha256=hash_sha256)
    if existing_result is not None:
        return existing_result

    storage_path = _storage_path_for(file_name, hash_sha256)
    _persist_upload_bytes(storage_path=storage_path, content=content)

    metadata = _build_upload_metadata(file_name=file_name, source_type=source_type, content_type=upload.content_type, hash_sha256=hash_sha256)
    source_id, job_id = _queue_upload_source(
        file_name=file_name,
        source_type=source_type,
        hash_sha256=hash_sha256,
        file_size_bytes=len(content),
        content_type=upload.content_type,
        storage_path=storage_path,
        metadata=metadata,
    )
    log_event("upload.accepted", source_id=source_id, job_id=job_id, stage="upload", status="accepted")
    if wait_for_completion:
        _run_ingestion_job(
            source_id=source_id,
            source_type=source_type,
            file_name=file_name,
            storage_path=storage_path,
            job_id=job_id,
        )
    else:
        from app.ingestion.queue_runtime import poke_ingestion_queue

        poke_ingestion_queue()
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
        stage="queued",
        priority=150,
        triggered_by="admin_reindex",
        owner_external_user_id=None,
        owner_email=None,
        owner_display_name=None,
        job_metadata_json={
            "force": force,
            "storage_path": source.storage_path,
            "file_size_bytes": source.file_size_bytes,
            "source_type": source.source_type,
            "queue_stage_label": "queued",
        },
    )
    from app.ingestion.queue_runtime import poke_ingestion_queue

    poke_ingestion_queue()
    log_event("admin.reindex.queued", source_id=source_id, job_id=job_id, stage="admin_reindex", status="queued")
    return {
        "status": "queued",
        "source_id": source_id,
        "job_id": job_id,
    }


def run_queued_ingestion_job(job_id: int) -> None:
    job = get_ingestion_job(job_id)
    if job is None or job.source_id is None:
        raise ValueError(f"Ingestion job {job_id} not found")
    source = get_source_by_id(job.source_id)
    if source is None:
        raise ValueError(f"Source {job.source_id} not found")
    _ingest_uploaded_source(
        source_id=source.id,
        source_type=source.source_type,
        file_name=source.file_name,
        storage_path=source.storage_path,
        job_id=job_id,
    )
