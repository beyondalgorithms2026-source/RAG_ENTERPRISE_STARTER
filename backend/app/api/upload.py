from typing import List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.auth.context import AuthenticatedUser
from app.auth.dependencies import require_upload_user
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit
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
async def upload_endpoint(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    _user: AuthenticatedUser | None = Depends(require_upload_user),
):
    enforce_rate_limit(request, scope="upload", limit_per_minute=settings.RATE_LIMIT_UPLOAD_PER_MINUTE)
    _reject_oversized_request(request)
    result = await process_upload(file, wait_for_completion=False, background_tasks=background_tasks)
    return UploadResponse(**result)


@router.post("/upload/batch", response_model=BatchUploadResponse)
async def upload_batch_endpoint(
    request: Request,
    files: List[UploadFile] = File(...),
    _user: AuthenticatedUser | None = Depends(require_upload_user),
):
    enforce_rate_limit(request, scope="upload_batch", limit_per_minute=settings.RATE_LIMIT_UPLOAD_PER_MINUTE)
    _reject_oversized_request(request)
    results = await process_upload_batch(files)
    return BatchUploadResponse(
        uploaded_count=len(results),
        items=[UploadResponse(**result) for result in results],
    )


def _reject_oversized_request(request: Request) -> None:
    raw_size = request.headers.get("content-length")
    if not raw_size:
        return
    try:
        size = int(raw_size)
    except ValueError:
        return
    if size > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"error": "file_too_large", "max_bytes": settings.MAX_UPLOAD_SIZE_BYTES},
        )
