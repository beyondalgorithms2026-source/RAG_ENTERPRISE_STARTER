from typing import List, Literal, Optional

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

from app.ingestion.jobs import process_upload, process_upload_batch


router = APIRouter()


class UploadResponse(BaseModel):
    status: Literal["queued", "skipped"]
    source_id: int
    job_id: int
    file_name: str
    source_type: str
    hash_sha256: str
    storage_path: str
    reupload_of_source_id: Optional[int] = None


class BatchUploadResponse(BaseModel):
    uploaded_count: int
    items: List[UploadResponse]


@router.post("/upload", response_model=UploadResponse)
async def upload_endpoint(file: UploadFile = File(...)):
    result = await process_upload(file)
    return UploadResponse(**result)


@router.post("/upload/batch", response_model=BatchUploadResponse)
async def upload_batch_endpoint(files: List[UploadFile] = File(...)):
    results = await process_upload_batch(files)
    return BatchUploadResponse(
        uploaded_count=len(results),
        items=[UploadResponse(**result) for result in results],
    )
