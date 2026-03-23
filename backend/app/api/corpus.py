from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.repo_jobs import get_ingestion_job
from app.db.repo_sources import list_sources
from app.ingestion.jobs import delete_uploaded_source


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
