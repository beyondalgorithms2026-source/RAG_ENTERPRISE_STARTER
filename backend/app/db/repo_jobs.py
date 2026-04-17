import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.db.db import engine


@dataclass
class IngestionJobRow:
    id: int
    source_id: Optional[int]
    status: str
    stage: str
    priority: int
    triggered_by: str
    owner_external_user_id: Optional[str]
    owner_email: Optional[str]
    owner_display_name: Optional[str]
    error_message: Optional[str]
    job_metadata_json: Dict
    started_at: Optional[str]
    completed_at: Optional[str]
    created_at: Optional[str]


@dataclass
class EnrichmentJobRow:
    id: int
    source_id: Optional[int]
    source_part_id: Optional[int]
    enrichment_type: str
    artifact_version: Optional[str]
    status: str
    stage: str
    error_message: Optional[str]
    job_metadata_json: Dict
    started_at: Optional[str]
    completed_at: Optional[str]
    created_at: Optional[str]


def _jsonable(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _row_to_ingestion_job(row) -> IngestionJobRow:
    return IngestionJobRow(*[_jsonable(value) for value in row])


def create_ingestion_job(
    *,
    source_id: Optional[int],
    status: str,
    stage: str = "queued",
    priority: int = 100,
    triggered_by: str = "system",
    owner_external_user_id: Optional[str] = None,
    owner_email: Optional[str] = None,
    owner_display_name: Optional[str] = None,
    job_metadata_json: Optional[Dict] = None,
) -> int:
    sql = text(
        """
        INSERT INTO ingestion_jobs (
            source_id, status, stage, priority, triggered_by,
            owner_external_user_id, owner_email, owner_display_name, job_metadata_json
        )
        VALUES (
            :source_id, :status, :stage, :priority, :triggered_by,
            :owner_external_user_id, :owner_email, :owner_display_name, CAST(:job_metadata_json AS jsonb)
        )
        RETURNING id
        """
    )
    with engine.begin() as conn:
        return conn.execute(
            sql,
            {
                "source_id": source_id,
                "status": status,
                "stage": stage,
                "priority": priority,
                "triggered_by": triggered_by,
                "owner_external_user_id": owner_external_user_id,
                "owner_email": owner_email,
                "owner_display_name": owner_display_name,
                "job_metadata_json": json.dumps(job_metadata_json or {}),
            },
        ).scalar_one()


def get_ingestion_job(job_id: int) -> Optional[IngestionJobRow]:
    sql = text(
        """
        SELECT id, source_id, status, stage, priority, triggered_by,
               owner_external_user_id, owner_email, owner_display_name,
               error_message, job_metadata_json, started_at, completed_at, created_at
        FROM ingestion_jobs
        WHERE id = :job_id
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"job_id": job_id}).first()
    if not row:
        return None
    return _row_to_ingestion_job(row)


def list_ingestion_jobs(source_id: Optional[int] = None) -> List[IngestionJobRow]:
    sql = """
        SELECT id, source_id, status, stage, priority, triggered_by,
               owner_external_user_id, owner_email, owner_display_name,
               error_message, job_metadata_json, started_at, completed_at, created_at
        FROM ingestion_jobs
    """
    params = {}
    if source_id is not None:
        sql += " WHERE source_id = :source_id"
        params["source_id"] = source_id
    sql += " ORDER BY created_at DESC, id DESC"

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()
    return [_row_to_ingestion_job(row) for row in rows]


def claim_next_ingestion_job() -> Optional[IngestionJobRow]:
    sql = text(
        """
        WITH next_job AS (
            SELECT id
            FROM ingestion_jobs
            WHERE status = 'queued'
            ORDER BY priority DESC, created_at ASC, id ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        UPDATE ingestion_jobs ij
        SET status = 'processing',
            stage = CASE WHEN ij.stage IN ('queued', 'uploaded', 'admin_reindex', 'retry_queued', 'requeue_requested') THEN 'parsing' ELSE ij.stage END,
            started_at = COALESCE(ij.started_at, now()),
            error_message = NULL
        FROM next_job
        WHERE ij.id = next_job.id
        RETURNING ij.id, ij.source_id, ij.status, ij.stage, ij.priority, ij.triggered_by,
                  ij.owner_external_user_id, ij.owner_email, ij.owner_display_name,
                  ij.error_message, ij.job_metadata_json, ij.started_at, ij.completed_at, ij.created_at
        """
    )
    with engine.begin() as conn:
        row = conn.execute(sql).first()
    if not row:
        return None
    return _row_to_ingestion_job(row)


def update_ingestion_job(
    job_id: int,
    *,
    status: Optional[str] = None,
    stage: Optional[str] = None,
    priority: Optional[int] = None,
    error_message: Optional[str] = None,
    started_at_now: bool = False,
    completed_at_now: bool = False,
    clear_completed_at: bool = False,
    clear_started_at: bool = False,
    job_metadata_json: Optional[Dict] = None,
) -> bool:
    updates = []
    params: Dict[str, Any] = {"job_id": job_id}
    if status is not None:
        updates.append("status = :status")
        params["status"] = status
    if stage is not None:
        updates.append("stage = :stage")
        params["stage"] = stage
    if priority is not None:
        updates.append("priority = :priority")
        params["priority"] = priority
    if error_message is not None:
        updates.append("error_message = :error_message")
        params["error_message"] = error_message
    if job_metadata_json is not None:
        updates.append("job_metadata_json = CAST(:job_metadata_json AS jsonb)")
        params["job_metadata_json"] = json.dumps(job_metadata_json)
    if started_at_now:
        updates.append("started_at = now()")
    if completed_at_now:
        updates.append("completed_at = now()")
    if clear_completed_at:
        updates.append("completed_at = NULL")
    if clear_started_at:
        updates.append("started_at = NULL")
    if not updates:
        return False
    sql = text(f"UPDATE ingestion_jobs SET {', '.join(updates)} WHERE id = :job_id")
    with engine.begin() as conn:
        result = conn.execute(sql, params)
    return result.rowcount > 0


def list_recent_completed_ingestion_jobs(limit: int = 20) -> List[IngestionJobRow]:
    sql = text(
        """
        SELECT id, source_id, status, stage, priority, triggered_by,
               owner_external_user_id, owner_email, owner_display_name,
               error_message, job_metadata_json, started_at, completed_at, created_at
        FROM ingestion_jobs
        WHERE status = 'completed'
          AND started_at IS NOT NULL
          AND completed_at IS NOT NULL
        ORDER BY completed_at DESC, id DESC
        LIMIT :limit
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"limit": limit}).fetchall()
    return [_row_to_ingestion_job(row) for row in rows]


def finish_ingestion_job(job_id: int, *, status: str, error_message: Optional[str] = None) -> None:
    sql = text(
        """
        UPDATE ingestion_jobs
        SET status = :status,
            error_message = :error_message,
            completed_at = now()
        WHERE id = :job_id
        """
    )
    with engine.begin() as conn:
        conn.execute(sql, {"job_id": job_id, "status": status, "error_message": error_message})


def create_enrichment_job(
    *,
    source_id: Optional[int],
    enrichment_type: str,
    status: str,
    source_part_id: Optional[int] = None,
    artifact_version: Optional[str] = None,
    stage: str = "queued",
    job_metadata_json: Optional[Dict] = None,
) -> int:
    sql = text(
        """
        INSERT INTO enrichment_jobs (
            source_id, source_part_id, enrichment_type, artifact_version, status, stage, job_metadata_json, started_at
        )
        VALUES (
            :source_id, :source_part_id, :enrichment_type, :artifact_version, :status, :stage,
            CAST(:job_metadata_json AS jsonb), now()
        )
        RETURNING id
        """
    )
    with engine.begin() as conn:
        return conn.execute(
            sql,
            {
                "source_id": source_id,
                "source_part_id": source_part_id,
                "enrichment_type": enrichment_type,
                "artifact_version": artifact_version,
                "status": status,
                "stage": stage,
                "job_metadata_json": json.dumps(job_metadata_json or {}),
            },
        ).scalar_one()


def finish_enrichment_job(job_id: int, *, status: str, error_message: Optional[str] = None) -> None:
    sql = text(
        """
        UPDATE enrichment_jobs
        SET status = :status,
            error_message = :error_message,
            completed_at = now()
        WHERE id = :job_id
        """
    )
    with engine.begin() as conn:
        conn.execute(sql, {"job_id": job_id, "status": status, "error_message": error_message})


def get_enrichment_job(job_id: int) -> Optional[EnrichmentJobRow]:
    sql = text(
        """
        SELECT id, source_id, source_part_id, enrichment_type, artifact_version, status, stage, error_message, job_metadata_json,
               started_at, completed_at, created_at
        FROM enrichment_jobs
        WHERE id = :job_id
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"job_id": job_id}).first()
    if not row:
        return None
    return EnrichmentJobRow(*[_jsonable(value) for value in row])


def list_enrichment_jobs(source_id: Optional[int] = None) -> List[EnrichmentJobRow]:
    sql = """
        SELECT id, source_id, source_part_id, enrichment_type, artifact_version, status, stage, error_message, job_metadata_json,
               started_at, completed_at, created_at
        FROM enrichment_jobs
    """
    params = {}
    if source_id is not None:
        sql += " WHERE source_id = :source_id"
        params["source_id"] = source_id
    sql += " ORDER BY created_at DESC, id DESC"

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()
    return [EnrichmentJobRow(*[_jsonable(value) for value in row]) for row in rows]


def create_attachment_link(
    *,
    parent_source_id: int,
    child_source_id: int,
    relationship_type: str = "attachment",
    attachment_metadata_json: Optional[Dict] = None,
) -> int:
    sql = text(
        """
        INSERT INTO attachments (
            parent_source_id, child_source_id, relationship_type, attachment_metadata_json
        )
        VALUES (
            :parent_source_id, :child_source_id, :relationship_type, CAST(:attachment_metadata_json AS jsonb)
        )
        ON CONFLICT (parent_source_id, child_source_id, relationship_type) DO UPDATE
        SET attachment_metadata_json = EXCLUDED.attachment_metadata_json
        RETURNING id
        """
    )
    with engine.begin() as conn:
        return conn.execute(
            sql,
            {
                "parent_source_id": parent_source_id,
                "child_source_id": child_source_id,
                "relationship_type": relationship_type,
                "attachment_metadata_json": json.dumps(attachment_metadata_json or {}),
            },
        ).scalar_one()


def list_attachments(parent_source_id: int) -> List[Dict]:
    sql = text(
        """
        SELECT id, parent_source_id, child_source_id, relationship_type, attachment_metadata_json
        FROM attachments
        WHERE parent_source_id = :parent_source_id
        ORDER BY id ASC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"parent_source_id": parent_source_id}).fetchall()

    return [
        {
            "id": row[0],
            "parent_source_id": row[1],
            "child_source_id": row[2],
            "relationship_type": row[3],
            "attachment_metadata_json": row[4],
        }
        for row in rows
    ]
