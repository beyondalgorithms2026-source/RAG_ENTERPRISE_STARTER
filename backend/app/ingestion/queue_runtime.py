from __future__ import annotations

import threading
from typing import Optional

from app.core.logging import logger
from app.db.repo_jobs import claim_next_ingestion_job
from app.db.repo_sources import get_source_by_id


_queue_event = threading.Event()
_worker_thread: Optional[threading.Thread] = None
_worker_lock = threading.Lock()


def _process_job(job_id: int) -> None:
    from app.ingestion.jobs import run_queued_ingestion_job

    run_queued_ingestion_job(job_id)


def _worker_loop() -> None:
    logger.info("Ingestion queue worker started.")
    while True:
        _queue_event.wait(timeout=2.0)
        _queue_event.clear()
        while True:
            job = claim_next_ingestion_job()
            if job is None:
                break
            source = get_source_by_id(int(job.source_id)) if job.source_id is not None else None
            if source is None:
                logger.warning("Skipping ingestion job %s because source %s is missing.", job.id, job.source_id)
                continue
            try:
                _process_job(job.id)
            except Exception:
                logger.exception("Queued ingestion job %s failed during worker execution.", job.id)


def start_ingestion_queue_worker() -> None:
    global _worker_thread
    with _worker_lock:
        if _worker_thread and _worker_thread.is_alive():
            return
        _worker_thread = threading.Thread(
            target=_worker_loop,
            name="ingestion-queue-worker",
            daemon=True,
        )
        _worker_thread.start()


def poke_ingestion_queue() -> None:
    _queue_event.set()
