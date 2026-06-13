from __future__ import annotations

import threading
from typing import Any, Optional

from app.core.config import settings
from app.core.logging import log_event, logger
from app.db.repo_connectors import (
    DbConnectorRow,
    claim_db_connector,
    claim_due_db_connector,
    create_connector_sync_run,
    mark_db_connector_sync_completed,
    mark_db_connector_sync_failed,
)


class ConnectorSyncConflict(RuntimeError):
    pass


_scheduler_thread: Optional[threading.Thread] = None
_scheduler_lock = threading.Lock()
_scheduler_wakeup = threading.Event()


def retry_delay_seconds(consecutive_failures: int) -> int:
    exponent = max(0, int(consecutive_failures))
    return min(
        int(settings.CONNECTOR_RETRY_MAX_SECONDS),
        int(settings.CONNECTOR_RETRY_BASE_SECONDS) * (2**exponent),
    )


def _execute_claimed_sync(connector: DbConnectorRow, *, trigger_type: str, row_limit: int) -> dict[str, Any]:
    from app.connectors.db import _ingest_db_connector_rows

    attempt_number = int(connector.consecutive_failures or 0) + 1
    run_id = create_connector_sync_run(
        connector_id=connector.id,
        trigger_type=trigger_type,
        attempt_number=attempt_number,
    )
    try:
        result = _ingest_db_connector_rows(connector.id, row_limit=row_limit)
        mark_db_connector_sync_completed(
            connector_id=connector.id,
            last_cursor_updated_at=result.get("last_cursor_updated_at"),
            last_cursor_id=result.get("last_cursor_id"),
            rows_ingested=int(result["rows_ingested"]),
            source_ids=list(result["source_ids"]),
            run_id=run_id,
        )
        return {key: value for key, value in result.items() if not key.startswith("last_cursor_")} | {"run_id": run_id}
    except Exception as exc:
        delay = retry_delay_seconds(connector.consecutive_failures)
        mark_db_connector_sync_failed(
            connector.id,
            run_id=run_id,
            error_message=str(exc),
            retry_seconds=delay,
        )
        log_event(
            "connector.db.sync.failed",
            level=40,
            stage="connector",
            status="degraded",
            reason=str(exc),
        )
        raise


def run_connector_sync(connector_id: int, *, trigger_type: str, row_limit: int = 200) -> dict[str, Any]:
    connector = claim_db_connector(connector_id, lease_seconds=settings.CONNECTOR_LEASE_SECONDS)
    if connector is None:
        from app.db.repo_connectors import get_db_connector

        if get_db_connector(connector_id) is None:
            raise ValueError(f"DB connector {connector_id} not found")
        raise ConnectorSyncConflict(f"DB connector {connector_id} is already syncing")
    return _execute_claimed_sync(connector, trigger_type=trigger_type, row_limit=row_limit)


def run_due_connector_once(*, row_limit: int = 200) -> Optional[dict[str, Any]]:
    connector = claim_due_db_connector(lease_seconds=settings.CONNECTOR_LEASE_SECONDS)
    if connector is None:
        return None
    return _execute_claimed_sync(connector, trigger_type="scheduled", row_limit=row_limit)


def _scheduler_loop() -> None:
    logger.info("Connector scheduler started.")
    while True:
        try:
            while run_due_connector_once() is not None:
                pass
        except Exception:
            logger.exception("Scheduled connector sync failed.")
        _scheduler_wakeup.wait(timeout=max(1, int(settings.CONNECTOR_SCHEDULER_POLL_SECONDS)))
        _scheduler_wakeup.clear()


def start_connector_scheduler() -> None:
    global _scheduler_thread
    if not settings.CONNECTOR_SCHEDULER_ENABLED:
        return
    with _scheduler_lock:
        if _scheduler_thread and _scheduler_thread.is_alive():
            return
        _scheduler_thread = threading.Thread(
            target=_scheduler_loop,
            name="connector-scheduler",
            daemon=True,
        )
        _scheduler_thread.start()


def poke_connector_scheduler() -> None:
    _scheduler_wakeup.set()
