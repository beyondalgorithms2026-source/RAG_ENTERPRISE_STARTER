from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.db.repo_chunks import fetch_chunk_context
from app.db.repo_jobs import get_ingestion_job
from app.db.repo_sources import get_source_by_id, list_sources
from app.ingestion.jobs import delete_uploaded_source
from app.ingestion.jobs import _source_file_absolute_path


router = APIRouter()


class CorpusItem(BaseModel):
    id: int
    file_name: str
    storage_path: str
    source_type: str
    mime_type: Optional[str] = None
    hash_sha256: str
    file_size_bytes: Optional[int] = None
    ingestion_status: str
    enrichment_status: str
    source_metadata_json: Dict[str, Any]


class IngestionJobItem(BaseModel):
    id: int
    source_id: Optional[int] = None
    status: str
    stage: str
    triggered_by: str
    error_message: Optional[str] = None
    job_metadata_json: Dict[str, Any]


class DeleteCorpusResponse(BaseModel):
    status: str
    source_id: int
    file_name: str
    storage_path: str
    file_deleted: bool


class ChunkContextItem(BaseModel):
    id: int
    source_id: int
    source_part_id: Optional[int] = None
    chunk_index: int
    heading: str
    chunk_text: str
    locator_json: Dict[str, Any]


class ChunkContextResponse(BaseModel):
    source_id: int
    source_file_name: str
    chunk_id: int
    target: Optional[ChunkContextItem] = None
    neighbors: List[ChunkContextItem] = []


@router.get("/corpus", response_model=List[CorpusItem])
def corpus_list_endpoint():
    return [CorpusItem(**row.__dict__) for row in list_sources()]


@router.get("/corpus/jobs/{job_id}", response_model=IngestionJobItem)
def job_status_endpoint(job_id: int):
    row = get_ingestion_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "job_not_found", "job_id": job_id})
    return IngestionJobItem(**row.__dict__)


@router.delete("/corpus/{source_id}", response_model=DeleteCorpusResponse)
def delete_corpus_source_endpoint(source_id: int):
    try:
        result = delete_uploaded_source(source_id=source_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"error": "source_not_found", "source_id": source_id}) from None
    return DeleteCorpusResponse(**result)


@router.get("/corpus/{source_id}/chunks/{chunk_id}/context", response_model=ChunkContextResponse)
def corpus_chunk_context_endpoint(source_id: int, chunk_id: int, radius: int = 1):
    source = get_source_by_id(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail={"error": "source_not_found", "source_id": source_id})

    payload = fetch_chunk_context(source_id=source_id, chunk_id=chunk_id, radius=radius)
    if not payload:
        raise HTTPException(
            status_code=404,
            detail={"error": "chunk_context_not_found", "source_id": source_id, "chunk_id": chunk_id},
        )

    target = payload.get("target")
    neighbors = payload.get("neighbors", [])
    return ChunkContextResponse(
        source_id=source_id,
        source_file_name=source.file_name,
        chunk_id=chunk_id,
        target=ChunkContextItem(**target) if target else None,
        neighbors=[ChunkContextItem(**item) for item in neighbors],
    )


@router.get("/corpus/{source_id}/file")
def corpus_source_file_endpoint(source_id: int):
    source = get_source_by_id(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail={"error": "source_not_found", "source_id": source_id})

    absolute_path = _source_file_absolute_path(source.storage_path)
    if not absolute_path.exists():
        raise HTTPException(
            status_code=404,
            detail={"error": "source_file_not_found", "source_id": source_id, "storage_path": source.storage_path},
        )
    media_type = source.mime_type or ("application/pdf" if source.source_type == "pdf" else "application/octet-stream")
    return FileResponse(path=str(absolute_path), media_type=media_type, filename=source.file_name)
