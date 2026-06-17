from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Optional

from app.db.repo_jobs import IngestionJobRow, list_recent_completed_ingestion_jobs
from app.db.repo_priority_requests import PriorityRequestRow
from app.db.repo_sources import SourceRow


_BASE_SECONDS_BY_TYPE = {
    "pdf": 26.0,
    "docx": 18.0,
    "pptx": 18.0,
    "xlsx": 14.0,
    "txt": 8.0,
    "md": 8.0,
    "eml": 12.0,
}

_SECONDS_PER_MB_BY_TYPE = {
    "pdf": 12.0,
    "docx": 8.0,
    "pptx": 8.0,
    "xlsx": 7.0,
    "txt": 3.0,
    "md": 3.0,
    "eml": 5.0,
}

_DEFAULT_CHUNKS_PER_MINUTE = 92.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _seconds_since(value: Optional[str]) -> float:
    parsed = _parse_datetime(value)
    if parsed is None:
        return 0.0
    return max((_now() - parsed).total_seconds(), 0.0)


def queue_stage_label(stage: Optional[str], status: Optional[str]) -> str:
    normalized_stage = str(stage or "").strip().lower()
    normalized_status = str(status or "").strip().lower()
    if normalized_status == "failed":
        return "failed"
    if normalized_status == "completed":
        return "completed"
    mapping = {
        "queued": "queued",
        "uploaded": "queued",
        "retry_queued": "queued",
        "requeue_requested": "queued",
        "parsing": "parsing",
        "source_parts": "indexing/enrichment",
        "chunking": "chunking",
        "embedding": "embedding",
        "embedded": "completed",
        "deduplicated": "completed",
        "admin_reindex": "queued",
        "paused": "paused",
        "cancelled": "cancelled",
    }
    return mapping.get(normalized_stage, normalized_stage or normalized_status or "queued")


def queue_confidence_label(job: IngestionJobRow) -> str:
    metadata = dict(job.job_metadata_json or {})
    if metadata.get("actual_chunk_count") and metadata.get("throughput_chunks_per_minute"):
        return "high"
    if metadata.get("actual_chunk_count") or metadata.get("parsed_part_count"):
        return "medium"
    return "low"


def _confidence_band_multiplier(confidence: str) -> float:
    return {"high": 0.18, "medium": 0.35}.get(confidence, 0.6)


def _throughput_chunks_per_minute() -> float:
    completed = list_recent_completed_ingestion_jobs(limit=16)
    samples: list[float] = []
    for job in completed:
        metadata = dict(job.job_metadata_json or {})
        chunk_count = metadata.get("actual_chunk_count") or metadata.get("chunk_count")
        started_at = _parse_datetime(job.started_at)
        completed_at = _parse_datetime(job.completed_at)
        if not chunk_count or not started_at or not completed_at:
            continue
        duration_seconds = max((completed_at - started_at).total_seconds(), 1.0)
        samples.append((float(chunk_count) / duration_seconds) * 60.0)
    if not samples:
        return _DEFAULT_CHUNKS_PER_MINUTE
    return round(sum(samples) / len(samples), 2)


def _rough_service_seconds(job: IngestionJobRow, source: Optional[SourceRow]) -> float:
    source_type = str((source.source_type if source else "") or "").lower()
    file_size_bytes = int(source.file_size_bytes or 0) if source else 0
    file_size_mb = max(file_size_bytes / (1024 * 1024), 0.1)
    base_seconds = _BASE_SECONDS_BY_TYPE.get(source_type, 16.0)
    rate_seconds = _SECONDS_PER_MB_BY_TYPE.get(source_type, 6.0)
    return round(base_seconds + (file_size_mb * rate_seconds), 1)


def estimate_total_service_seconds(job: IngestionJobRow, source: Optional[SourceRow]) -> float:
    metadata = dict(job.job_metadata_json or {})
    chunk_count = metadata.get("actual_chunk_count") or metadata.get("chunk_count")
    throughput = float(metadata.get("throughput_chunks_per_minute") or _throughput_chunks_per_minute())
    rough_seconds = _rough_service_seconds(job, source)
    if not chunk_count:
        return rough_seconds
    embedding_seconds = (float(chunk_count) / max(throughput, 1.0)) * 60.0
    parsed_part_count = float(metadata.get("parsed_part_count") or 0)
    indexing_overhead = min(parsed_part_count * 0.35, 18.0)
    return round(max(rough_seconds, 8.0 + embedding_seconds + indexing_overhead), 1)


def estimate_remaining_service_seconds(job: IngestionJobRow, source: Optional[SourceRow]) -> float:
    total_seconds = estimate_total_service_seconds(job, source)
    stage = queue_stage_label(job.stage, job.status)
    progress = {
        "queued": 0.0,
        "parsing": 0.12,
        "chunking": 0.42,
        "indexing/enrichment": 0.56,
        "embedding": 0.78,
        "completed": 1.0,
        "failed": 1.0,
        "paused": 0.0,
        "cancelled": 1.0,
    }.get(stage, 0.0)
    if str(job.status).lower() == "processing" and job.started_at:
        elapsed = _seconds_since(job.started_at)
        baseline_remaining = max(total_seconds - elapsed, total_seconds * (1.0 - progress))
        return round(max(baseline_remaining, 4.0 if stage != "completed" else 0.0), 1)
    return round(max(total_seconds * (1.0 - progress), 0.0), 1)


def _window_payload(seconds: float, confidence: str) -> dict[str, Any]:
    band = max(seconds * _confidence_band_multiplier(confidence), 20.0 if confidence == "low" else 8.0)
    return {
        "seconds": round(seconds, 1),
        "lower_seconds": max(round(seconds - band, 1), 0.0),
        "upper_seconds": round(seconds + band, 1),
        "confidence": confidence,
    }


def priority_request_payload(request: Optional[PriorityRequestRow]) -> Optional[dict[str, Any]]:
    if request is None:
        return None
    payload = asdict(request)
    for key, value in list(payload.items()):
        if hasattr(value, "isoformat"):
            payload[key] = value.isoformat()
    return payload


def summarize_ingestion_queue(
    jobs: list[IngestionJobRow],
    source_lookup: dict[int, SourceRow],
    priority_lookup: Optional[dict[int, PriorityRequestRow]] = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    priority_lookup = priority_lookup or {}
    throughput = _throughput_chunks_per_minute()
    active_jobs = [
        job for job in jobs
        if str(job.status).lower() in {"processing", "running"}
    ]
    queued_jobs = [
        job for job in jobs
        if str(job.status).lower() in {"queued", "paused"}
    ]
    queued_jobs.sort(key=lambda item: (-int(item.priority), item.created_at or "", item.id))
    pipeline_seconds = sum(estimate_remaining_service_seconds(job, source_lookup.get(int(job.source_id or 0))) for job in active_jobs)
    active_workers = len(active_jobs)

    enriched: list[dict[str, Any]] = []
    for index, job in enumerate(queued_jobs):
        source = source_lookup.get(int(job.source_id or 0))
        own_seconds = estimate_total_service_seconds(job, source)
        wait_seconds = pipeline_seconds + sum(
            estimate_total_service_seconds(previous, source_lookup.get(int(previous.source_id or 0)))
            for previous in queued_jobs[:index]
            if str(previous.status).lower() == "queued"
        )
        finish_window = _window_payload(wait_seconds + own_seconds, queue_confidence_label(job))
        enriched.append(
            {
                "job_id": job.id,
                "wait_window": _window_payload(wait_seconds, queue_confidence_label(job)),
                "finish_window": finish_window,
                "queue_position": active_workers + index + 1,
                "jobs_ahead": active_workers + index,
                "queue_delay_message": "No earlier indexing jobs are ahead." if active_workers + index == 0 else f"{active_workers + index} earlier indexing job(s) are ahead in the queue.",
            }
        )

    queue_by_job_id = {item["job_id"]: item for item in enriched}
    payloads: list[dict[str, Any]] = []
    for job in jobs:
        source = source_lookup.get(int(job.source_id or 0))
        confidence = queue_confidence_label(job)
        stage_label = queue_stage_label(job.stage, job.status)
        estimate_total = estimate_total_service_seconds(job, source)
        estimate_remaining = estimate_remaining_service_seconds(job, source)
        dynamic_queue = queue_by_job_id.get(job.id)
        if str(job.status).lower() in {"processing", "running"}:
            finish_window = _window_payload(estimate_remaining, confidence)
            wait_window = _window_payload(0.0, confidence)
            queue_position = 0
            jobs_ahead = 0
            queue_delay_message = "This file is actively being indexed now."
        elif dynamic_queue:
            finish_window = dynamic_queue["finish_window"]
            wait_window = dynamic_queue["wait_window"]
            queue_position = dynamic_queue["queue_position"]
            jobs_ahead = dynamic_queue["jobs_ahead"]
            queue_delay_message = dynamic_queue["queue_delay_message"]
        else:
            finish_window = None
            wait_window = None
            queue_position = None
            jobs_ahead = None
            queue_delay_message = "Indexing is complete." if str(job.status).lower() == "completed" else "No queue estimate is available."

        payloads.append(
            {
                "id": job.id,
                "source_id": job.source_id,
                "status": job.status,
                "stage": job.stage,
                "stage_label": stage_label,
                "priority": job.priority,
                "triggered_by": job.triggered_by,
                "owner_external_user_id": job.owner_external_user_id,
                "owner_email": job.owner_email,
                "owner_display_name": job.owner_display_name,
                "error_message": job.error_message,
                "job_metadata_json": dict(job.job_metadata_json or {}),
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "created_at": job.created_at,
                "estimated_total_seconds": estimate_total,
                "estimated_remaining_seconds": estimate_remaining if str(job.status).lower() in {"queued", "processing", "running", "paused"} else 0.0,
                "eta_window": finish_window,
                "wait_window": wait_window,
                "eta_confidence": confidence,
                "queue_position": queue_position,
                "jobs_ahead": jobs_ahead,
                "queue_delay_message": queue_delay_message,
                "priority_label": "urgent" if int(job.priority) >= 200 else "high" if int(job.priority) >= 150 else "normal",
                "source_file_name": source.file_name if source else None,
                "source_type": source.source_type if source else None,
                "file_size_bytes": source.file_size_bytes if source else None,
                "corpus_name": (source.source_metadata_json or {}).get("corpus") if source else None,
                "priority_request": priority_request_payload(priority_lookup.get(job.id)),
            }
        )

    queued_count = len([job for job in jobs if str(job.status).lower() == "queued"])
    waiting_job_ages = [_seconds_since(job.created_at) for job in jobs if str(job.status).lower() == "queued"]
    oldest_wait_seconds = max(waiting_job_ages) if waiting_job_ages else 0.0
    failed_by_stage: dict[str, int] = {}
    for job in jobs:
        if str(job.status).lower() not in {"failed", "error"}:
            continue
        failed_by_stage[queue_stage_label(job.stage, job.status)] = failed_by_stage.get(queue_stage_label(job.stage, job.status), 0) + 1

    summary = {
        "backlog_count": queued_count,
        "active_workers": active_workers,
        "oldest_wait_seconds": round(oldest_wait_seconds, 1),
        "average_chunks_per_minute": throughput,
        "failure_hotspots": failed_by_stage,
        "queue_policy_label": "manual-priority-then-fifo",
    }
    return payloads, summary
