from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.auth.context import AuthenticatedUser, get_current_user
from app.auth.dependencies import require_admin_user, require_connector_request_user
from app.db.repo_chunks import fetch_chunk_context
from app.db.repo_admin_audit import insert_admin_audit_event
from app.db.repo_connectors import (
    DbConnectorRow,
    list_connector_sync_runs,
    list_db_connectors,
    update_db_connector_schedule,
    upsert_db_connector,
)
from app.db.repo_connectors import create_connector_request, list_connector_requests, update_connector_request_review
from app.db.repo_jobs import get_ingestion_job, list_ingestion_jobs
from app.db.repo_priority_requests import (
    create_priority_request,
    expire_stale_priority_requests,
    get_latest_priority_request_for_job,
    list_priority_requests,
)
from app.db.repo_sources import get_accessible_source_by_id, list_accessible_sources
from app.db.repo_source_parts import list_source_parts
from app.ingestion.queue_metrics import priority_request_payload, summarize_ingestion_queue
from app.ingestion.jobs import delete_uploaded_source
from app.ingestion.jobs import _source_file_absolute_path
from app.connectors.db import ingest_db_connector, inspect_db_connector_schema, preview_db_connector_sync
from app.connectors.runtime import ConnectorSyncConflict, poke_connector_scheduler
from app.freshness import source_freshness


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
    freshness: Dict[str, Any]
    latest_ingestion_job: Optional[Dict[str, Any]] = None


class EtaWindowItem(BaseModel):
    seconds: float
    lower_seconds: float
    upper_seconds: float
    confidence: str


class PriorityRequestItem(BaseModel):
    id: int
    job_id: int
    source_id: Optional[int] = None
    requester_external_user_id: Optional[str] = None
    requester_email: Optional[str] = None
    requester_display_name: Optional[str] = None
    requested_priority: int
    reason: str
    status: str
    review_reason: Optional[str] = None
    reviewed_by_external_user_id: Optional[str] = None
    reviewed_by_email: Optional[str] = None
    created_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    expires_at: Optional[str] = None


class IngestionJobItem(BaseModel):
    id: int
    source_id: Optional[int] = None
    status: str
    stage: str
    stage_label: Optional[str] = None
    priority: int = 100
    triggered_by: str
    owner_external_user_id: Optional[str] = None
    owner_email: Optional[str] = None
    owner_display_name: Optional[str] = None
    error_message: Optional[str] = None
    job_metadata_json: Dict[str, Any]
    estimated_total_seconds: Optional[float] = None
    estimated_remaining_seconds: Optional[float] = None
    eta_window: Optional[EtaWindowItem] = None
    wait_window: Optional[EtaWindowItem] = None
    eta_confidence: Optional[str] = None
    queue_position: Optional[int] = None
    jobs_ahead: Optional[int] = None
    queue_delay_message: Optional[str] = None
    source_file_name: Optional[str] = None
    source_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    corpus_name: Optional[str] = None
    priority_request: Optional[PriorityRequestItem] = None


class QueuePriorityRequestCreate(BaseModel):
    reason: str = Field(default="")
    requested_priority: int = Field(default=200, ge=120, le=300)


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
    freshness: Dict[str, Any]
    target: Optional[ChunkContextItem] = None
    neighbors: List[ChunkContextItem] = []


class DbConnectorCreate(BaseModel):
    name: str
    connector_type: Literal["postgres", "mysql"] = "postgres"
    db_url: str
    table_name: str
    id_column: str = "id"
    updated_at_column: str = "updated_at"
    text_columns: List[str] = Field(default_factory=list)
    metadata_columns: List[str] = Field(default_factory=list)
    corpus_name: Optional[str] = None
    acl_group_names: List[str] = Field(default_factory=list)
    schedule_enabled: bool = True
    sync_interval_minutes: int = Field(default=60, ge=1, le=10080)


class DbConnectorItem(BaseModel):
    id: int
    name: str
    connector_type: str
    table_name: str
    id_column: str
    updated_at_column: str
    text_columns: List[str]
    metadata_columns: List[str]
    corpus_name: Optional[str] = None
    acl_group_names: List[str]
    status: str
    last_cursor_updated_at: Optional[str] = None
    last_cursor_id: Optional[str] = None
    last_run_at: Optional[str] = None
    last_error: Optional[str] = None
    connector_metadata_json: Dict[str, Any]
    schedule_enabled: bool
    sync_interval_minutes: int
    next_run_at: Optional[str] = None
    consecutive_failures: int
    retry_at: Optional[str] = None
    last_success_at: Optional[str] = None
    health_status: str


class DbConnectorScheduleUpdate(BaseModel):
    schedule_enabled: bool
    sync_interval_minutes: int = Field(default=60, ge=1, le=10080)


class DbConnectorSyncRequest(BaseModel):
    row_limit: int = Field(default=200, ge=1, le=1000)


class DbConnectorSyncResponse(BaseModel):
    status: str
    connector_id: int
    rows_ingested: int
    source_ids: List[int]


class ConnectorRequestCreate(BaseModel):
    connector_type: str = "database"
    requested_system: str
    business_reason: str = ""
    requested_scope_json: Dict[str, Any] = Field(default_factory=dict)


class ConnectorRequestReview(BaseModel):
    status: Literal["under_review", "approved", "denied"]
    review_reason: str = ""


class ConnectorRequestItem(BaseModel):
    id: int
    connector_type: str
    requested_system: str
    business_reason: str
    requested_scope_json: Dict[str, Any]
    status: str
    review_reason: Optional[str] = None
    requester_external_user_id: Optional[str] = None
    requester_email: Optional[str] = None
    requester_display_name: Optional[str] = None
    reviewed_by_external_user_id: Optional[str] = None
    reviewed_by_email: Optional[str] = None
    reviewed_at: Optional[str] = None
    created_at: Optional[str] = None


def _enriched_ingestion_jobs() -> list[dict[str, Any]]:
    expire_stale_priority_requests()
    sources = list_accessible_sources()
    source_lookup = {int(source.id): source for source in sources}
    latest_requests: dict[int, Any] = {}
    for request in list_priority_requests(limit=200):
        latest_requests.setdefault(request.job_id, request)
    payloads, _ = summarize_ingestion_queue(list_ingestion_jobs(), source_lookup, latest_requests)
    return payloads


def _connector_payload(row: DbConnectorRow) -> DbConnectorItem:
    return DbConnectorItem(
        id=row.id,
        name=row.name,
        connector_type=row.connector_type,
        table_name=row.table_name,
        id_column=row.id_column,
        updated_at_column=row.updated_at_column,
        text_columns=row.text_columns_json,
        metadata_columns=row.metadata_columns_json,
        corpus_name=row.corpus_name,
        acl_group_names=row.acl_group_names_json,
        status=row.status,
        last_cursor_updated_at=row.last_cursor_updated_at,
        last_cursor_id=row.last_cursor_id,
        last_run_at=row.last_run_at,
        last_error=row.last_error,
        connector_metadata_json=row.connector_metadata_json,
        schedule_enabled=row.schedule_enabled,
        sync_interval_minutes=row.sync_interval_minutes,
        next_run_at=row.next_run_at,
        consecutive_failures=row.consecutive_failures,
        retry_at=row.retry_at,
        last_success_at=row.last_success_at,
        health_status="degraded" if row.status in {"degraded", "failed"} else ("syncing" if row.status == "syncing" else "healthy"),
    )


def _connector_request_payload(row) -> ConnectorRequestItem:
    return ConnectorRequestItem(**row.__dict__)


@router.get("/corpus", response_model=List[CorpusItem])
def corpus_list_endpoint():
    latest_job_by_source: dict[int, dict[str, Any]] = {}
    for job in _enriched_ingestion_jobs():
        source_id = job.get("source_id")
        if source_id is None:
            continue
        latest_job_by_source.setdefault(int(source_id), job)
    return [
        CorpusItem(
            **row.__dict__,
            freshness=source_freshness(row),
            latest_ingestion_job=latest_job_by_source.get(int(row.id)),
        )
        for row in list_accessible_sources()
    ]


@router.get("/connectors/db", response_model=List[DbConnectorItem])
def db_connector_list_endpoint(_admin=Depends(require_admin_user)):
    return [_connector_payload(row) for row in list_db_connectors()]


@router.get("/connectors/requests", response_model=List[ConnectorRequestItem])
def connector_request_list_endpoint(_user: AuthenticatedUser | None = Depends(require_connector_request_user)):
    actor = get_current_user()
    requester_id = None if actor and "admin" in {role.lower() for role in actor.roles} else actor.user_id if actor else None
    return [_connector_request_payload(row) for row in list_connector_requests(requester_external_user_id=requester_id)]


@router.post("/connectors/requests", response_model=ConnectorRequestItem)
def connector_request_create_endpoint(
    body: ConnectorRequestCreate,
    _user: AuthenticatedUser | None = Depends(require_connector_request_user),
):
    actor = get_current_user()
    request_id = create_connector_request(
        connector_type=body.connector_type.strip() or "database",
        requested_system=body.requested_system.strip(),
        business_reason=body.business_reason.strip(),
        requested_scope_json=body.requested_scope_json,
        requester_external_user_id=actor.user_id if actor else None,
        requester_email=actor.email if actor else None,
        requester_display_name=actor.name if actor else None,
    )
    request = next(row for row in list_connector_requests(limit=20) if row.id == request_id)
    insert_admin_audit_event(
        event_type="connector",
        action="connector.request.submitted",
        resource_type="connector_request",
        resource_id=str(request_id),
        resource_name=body.requested_system,
        after_json=request.__dict__,
    )
    return _connector_request_payload(request)


@router.post("/connectors/requests/{request_id}/review", response_model=ConnectorRequestItem)
def connector_request_review_endpoint(request_id: int, body: ConnectorRequestReview, _admin=Depends(require_admin_user)):
    actor = get_current_user()
    request = update_connector_request_review(
        request_id=request_id,
        status=body.status,
        review_reason=body.review_reason,
        reviewed_by_external_user_id=actor.user_id if actor else None,
        reviewed_by_email=actor.email if actor else None,
    )
    if request is None:
        raise HTTPException(status_code=404, detail={"error": "connector_request_not_found", "request_id": request_id})
    insert_admin_audit_event(
        event_type="connector",
        action="connector.request.reviewed",
        resource_type="connector_request",
        resource_id=str(request_id),
        resource_name=request.requested_system,
        after_json=request.__dict__,
    )
    return _connector_request_payload(request)


@router.post("/connectors/db", response_model=DbConnectorItem)
def db_connector_create_endpoint(body: DbConnectorCreate, _admin=Depends(require_admin_user)):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail={"error": "connector_name_required"})
    if not body.text_columns:
        raise HTTPException(status_code=400, detail={"error": "text_columns_required"})
    connector_id = upsert_db_connector(
        name=body.name.strip(),
        connector_type=body.connector_type,
        db_url=body.db_url.strip(),
        table_name=body.table_name.strip(),
        id_column=body.id_column.strip(),
        updated_at_column=body.updated_at_column.strip(),
        text_columns=[column.strip() for column in body.text_columns if column.strip()],
        metadata_columns=[column.strip() for column in body.metadata_columns if column.strip()],
        corpus_name=body.corpus_name.strip() if body.corpus_name and body.corpus_name.strip() else None,
        acl_group_names=[group.strip() for group in body.acl_group_names if group.strip()],
        connector_metadata_json={"source": "console"},
        schedule_enabled=body.schedule_enabled,
        sync_interval_minutes=body.sync_interval_minutes,
    )
    insert_admin_audit_event(
        event_type="connector",
        action="connector.db.configured",
        resource_type="db_connector",
        resource_id=str(connector_id),
        resource_name=body.name.strip(),
        corpus_name=body.corpus_name,
        after_json={
            "connector_id": connector_id,
            "connector_type": body.connector_type,
            "table_name": body.table_name,
            "id_column": body.id_column,
            "updated_at_column": body.updated_at_column,
            "text_columns": body.text_columns,
            "metadata_columns": body.metadata_columns,
            "corpus_name": body.corpus_name,
            "acl_group_names": body.acl_group_names,
        },
    )
    return _connector_payload(next(row for row in list_db_connectors() if row.id == connector_id))


@router.patch("/connectors/db/{connector_id}/schedule", response_model=DbConnectorItem)
def db_connector_schedule_endpoint(connector_id: int, body: DbConnectorScheduleUpdate, _admin=Depends(require_admin_user)):
    connector = update_db_connector_schedule(
        connector_id=connector_id,
        schedule_enabled=body.schedule_enabled,
        sync_interval_minutes=body.sync_interval_minutes,
    )
    if connector is None:
        raise HTTPException(status_code=404, detail={"error": "connector_not_found", "connector_id": connector_id})
    poke_connector_scheduler()
    return _connector_payload(connector)


@router.get("/connectors/db/{connector_id}/runs")
def db_connector_runs_endpoint(connector_id: int, _admin=Depends(require_admin_user)):
    if not any(row.id == connector_id for row in list_db_connectors()):
        raise HTTPException(status_code=404, detail={"error": "connector_not_found", "connector_id": connector_id})
    return {"runs": [row.__dict__ for row in list_connector_sync_runs(connector_id)]}


@router.post("/connectors/db/{connector_id}/sync", response_model=DbConnectorSyncResponse)
def db_connector_sync_endpoint(connector_id: int, body: DbConnectorSyncRequest, _admin=Depends(require_admin_user)):
    try:
        result = ingest_db_connector(connector_id, row_limit=body.row_limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "connector_not_found", "message": str(exc)}) from exc
    except ConnectorSyncConflict as exc:
        raise HTTPException(status_code=409, detail={"error": "connector_sync_in_progress", "message": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"error": "connector_sync_failed", "message": str(exc)}) from exc
    insert_admin_audit_event(
        event_type="connector",
        action="connector.db.synced",
        resource_type="db_connector",
        resource_id=str(connector_id),
        job_kind="ingestion",
        after_json=result,
    )
    return DbConnectorSyncResponse(**result)


@router.get("/connectors/db/{connector_id}/schema")
def db_connector_schema_endpoint(connector_id: int, _admin=Depends(require_admin_user)):
    connector = next((row for row in list_db_connectors() if row.id == connector_id), None)
    if connector is None:
        raise HTTPException(status_code=404, detail={"error": "connector_not_found", "connector_id": connector_id})
    try:
        return inspect_db_connector_schema(connector)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"error": "connector_schema_failed", "message": str(exc)}) from exc


@router.post("/connectors/db/{connector_id}/preview")
def db_connector_preview_endpoint(connector_id: int, body: DbConnectorSyncRequest, _admin=Depends(require_admin_user)):
    connector = next((row for row in list_db_connectors() if row.id == connector_id), None)
    if connector is None:
        raise HTTPException(status_code=404, detail={"error": "connector_not_found", "connector_id": connector_id})
    try:
        return preview_db_connector_sync(connector, row_limit=body.row_limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"error": "connector_preview_failed", "message": str(exc)}) from exc


@router.get("/corpus/jobs/{job_id}", response_model=IngestionJobItem)
def job_status_endpoint(job_id: int):
    row = next((job for job in _enriched_ingestion_jobs() if int(job["id"]) == job_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "job_not_found", "job_id": job_id})
    return IngestionJobItem(**row)


@router.post("/corpus/jobs/{job_id}/priority-request", response_model=PriorityRequestItem)
def submit_priority_request(job_id: int, body: QueuePriorityRequestCreate):
    job = get_ingestion_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": "job_not_found", "job_id": job_id})
    actor = get_current_user()
    if actor is None:
        raise HTTPException(status_code=401, detail={"error": "authentication_required", "message": "Authentication is required before submitting a priority request."})
    if job.owner_external_user_id and actor.user_id != job.owner_external_user_id and "admin" not in actor.roles:
        raise HTTPException(status_code=403, detail={"error": "not_job_owner", "message": "Only the original uploader can request priority for this job."})
    if str(job.status).lower() not in {"queued", "processing", "running", "paused"}:
        raise HTTPException(status_code=400, detail={"error": "job_not_actionable", "message": "Priority can be requested only while indexing is still active or waiting."})
    if not (job.owner_external_user_id or job.owner_email):
        raise HTTPException(status_code=400, detail={"error": "owner_missing", "message": "This job does not have a recorded owner for user-side priority requests."})
    request_id = create_priority_request(
        job_id=job_id,
        source_id=job.source_id,
        requested_priority=body.requested_priority,
        reason=body.reason,
    )
    request = get_latest_priority_request_for_job(job_id)
    insert_admin_audit_event(
        event_type="queue",
        action="queue.priority_request.submitted",
        resource_type="ingestion_job",
        resource_id=str(job_id),
        resource_name=str(job.source_id or job_id),
        source_id=job.source_id,
        job_kind="ingestion",
        job_id=job_id,
        event_json={
            "request_id": request_id,
            "requested_priority": body.requested_priority,
            "reason": body.reason,
        },
    )
    return PriorityRequestItem(**(priority_request_payload(request) or {}))


@router.delete("/corpus/{source_id}", response_model=DeleteCorpusResponse)
def delete_corpus_source_endpoint(source_id: int):
    try:
        result = delete_uploaded_source(source_id=source_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"error": "source_not_found", "source_id": source_id}) from None
    return DeleteCorpusResponse(**result)


@router.get("/corpus/{source_id}/chunks/{chunk_id}/context", response_model=ChunkContextResponse)
def corpus_chunk_context_endpoint(source_id: int, chunk_id: int, radius: int = 1):
    source = get_accessible_source_by_id(source_id)
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
        freshness=source_freshness(source),
        target=ChunkContextItem(**target) if target else None,
        neighbors=[ChunkContextItem(**item) for item in neighbors],
    )


@router.get("/corpus/{source_id}/file")
def corpus_source_file_endpoint(source_id: int):
    source = get_accessible_source_by_id(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail={"error": "source_not_found", "source_id": source_id})

    if source.source_type == "db_row":
        parts = list_source_parts(source_id)
        body = "\n\n".join(part.content_text or "" for part in parts).strip()
        return PlainTextResponse(body or source.file_name, media_type="text/plain")

    absolute_path = _source_file_absolute_path(source.storage_path)
    if not absolute_path.exists():
        raise HTTPException(
            status_code=404,
            detail={"error": "source_file_not_found", "source_id": source_id, "storage_path": source.storage_path},
        )
    media_type = source.mime_type or ("application/pdf" if source.source_type == "pdf" else "application/octet-stream")
    return FileResponse(path=str(absolute_path), media_type=media_type, filename=source.file_name)
