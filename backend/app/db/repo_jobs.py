import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from sqlalchemy import text

from app.db.db import engine


@dataclass
class IngestionJobRow:
    id: int
    source_id: Optional[int]
    status: str
    stage: str
    triggered_by: str
    error_message: Optional[str]
    job_metadata_json: Dict


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


def _row_to_ingestion_job(row) -> IngestionJobRow:
    return IngestionJobRow(*row)


def create_ingestion_job(
    *,
    source_id: Optional[int],
    status: str,
    stage: str = "queued",
    triggered_by: str = "system",
    job_metadata_json: Optional[Dict] = None,
) -> int:
    sql = text(
        """
        INSERT INTO ingestion_jobs (source_id, status, stage, triggered_by, job_metadata_json, started_at)
        VALUES (:source_id, :status, :stage, :triggered_by, CAST(:job_metadata_json AS jsonb), now())
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
                "triggered_by": triggered_by,
                "job_metadata_json": json.dumps(job_metadata_json or {}),
            },
        ).scalar_one()


def get_ingestion_job(job_id: int) -> Optional[IngestionJobRow]:
    sql = text(
        """
        SELECT id, source_id, status, stage, triggered_by, error_message, job_metadata_json
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
        SELECT id, source_id, status, stage, triggered_by, error_message, job_metadata_json
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
        SELECT id, source_id, source_part_id, enrichment_type, artifact_version, status, stage, error_message, job_metadata_json
        FROM enrichment_jobs
        WHERE id = :job_id
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"job_id": job_id}).first()
    if not row:
        return None
    return EnrichmentJobRow(*row)


def list_enrichment_jobs(source_id: Optional[int] = None) -> List[EnrichmentJobRow]:
    sql = """
        SELECT id, source_id, source_part_id, enrichment_type, artifact_version, status, stage, error_message, job_metadata_json
        FROM enrichment_jobs
    """
    params = {}
    if source_id is not None:
        sql += " WHERE source_id = :source_id"
        params["source_id"] = source_id
    sql += " ORDER BY created_at DESC, id DESC"

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()
    return [EnrichmentJobRow(*row) for row in rows]


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
