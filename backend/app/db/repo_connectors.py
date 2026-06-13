import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.db.db import engine


@dataclass
class DbConnectorRow:
    id: int
    name: str
    connector_type: str
    db_url: str
    table_name: str
    id_column: str
    updated_at_column: str
    text_columns_json: List[str]
    metadata_columns_json: List[str]
    corpus_name: Optional[str]
    acl_group_names_json: List[str]
    status: str
    last_cursor_updated_at: Optional[str]
    last_cursor_id: Optional[str]
    last_run_at: Optional[str]
    last_error: Optional[str]
    connector_metadata_json: Dict[str, Any]
    schedule_enabled: bool = False
    sync_interval_minutes: int = 60
    next_run_at: Optional[str] = None
    consecutive_failures: int = 0
    retry_at: Optional[str] = None
    last_success_at: Optional[str] = None
    lease_expires_at: Optional[str] = None


@dataclass
class ConnectorSyncRunRow:
    id: int
    connector_id: int
    trigger_type: str
    status: str
    attempt_number: int
    rows_ingested: int
    source_ids_json: List[int]
    error_message: Optional[str]
    retry_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]


@dataclass
class ConnectorRequestRow:
    id: int
    connector_type: str
    requested_system: str
    business_reason: str
    requested_scope_json: Dict[str, Any]
    status: str
    review_reason: Optional[str]
    requester_external_user_id: Optional[str]
    requester_email: Optional[str]
    requester_display_name: Optional[str]
    reviewed_by_external_user_id: Optional[str]
    reviewed_by_email: Optional[str]
    reviewed_at: Optional[str]
    created_at: Optional[str]


def _row_to_connector(row) -> DbConnectorRow:
    return DbConnectorRow(
        id=row[0],
        name=row[1],
        connector_type=row[2],
        db_url=row[3],
        table_name=row[4],
        id_column=row[5],
        updated_at_column=row[6],
        text_columns_json=row[7] or [],
        metadata_columns_json=row[8] or [],
        corpus_name=row[9],
        acl_group_names_json=row[10] or [],
        status=row[11],
        last_cursor_updated_at=str(row[12]) if row[12] is not None else None,
        last_cursor_id=str(row[13]) if row[13] is not None else None,
        last_run_at=str(row[14]) if row[14] is not None else None,
        last_error=row[15],
        connector_metadata_json=row[16] or {},
        schedule_enabled=bool(row[17]),
        sync_interval_minutes=int(row[18] or 60),
        next_run_at=str(row[19]) if row[19] is not None else None,
        consecutive_failures=int(row[20] or 0),
        retry_at=str(row[21]) if row[21] is not None else None,
        last_success_at=str(row[22]) if row[22] is not None else None,
        lease_expires_at=str(row[23]) if row[23] is not None else None,
    )


def upsert_db_connector(
    *,
    name: str,
    connector_type: str,
    db_url: str,
    table_name: str,
    id_column: str,
    updated_at_column: str,
    text_columns: List[str],
    metadata_columns: List[str],
    corpus_name: Optional[str],
    acl_group_names: List[str],
    connector_metadata_json: Optional[Dict[str, Any]] = None,
    schedule_enabled: bool = False,
    sync_interval_minutes: int = 60,
) -> int:
    sql = text(
        """
        INSERT INTO db_connectors (
            name, connector_type, db_url, table_name, id_column, updated_at_column,
            text_columns_json, metadata_columns_json, corpus_name, acl_group_names_json,
            status, last_error, connector_metadata_json, schedule_enabled,
            sync_interval_minutes, next_run_at
        )
        VALUES (
            :name, :connector_type, :db_url, :table_name, :id_column, :updated_at_column,
            CAST(:text_columns_json AS jsonb), CAST(:metadata_columns_json AS jsonb),
            :corpus_name, CAST(:acl_group_names_json AS jsonb), 'configured', NULL,
            CAST(:connector_metadata_json AS jsonb), :schedule_enabled,
            :sync_interval_minutes,
            CASE WHEN :schedule_enabled THEN now() ELSE NULL END
        )
        ON CONFLICT (name) DO UPDATE
        SET connector_type = EXCLUDED.connector_type,
            db_url = EXCLUDED.db_url,
            table_name = EXCLUDED.table_name,
            id_column = EXCLUDED.id_column,
            updated_at_column = EXCLUDED.updated_at_column,
            text_columns_json = EXCLUDED.text_columns_json,
            metadata_columns_json = EXCLUDED.metadata_columns_json,
            corpus_name = EXCLUDED.corpus_name,
            acl_group_names_json = EXCLUDED.acl_group_names_json,
            status = 'configured',
            last_error = NULL,
            connector_metadata_json = EXCLUDED.connector_metadata_json,
            schedule_enabled = EXCLUDED.schedule_enabled,
            sync_interval_minutes = EXCLUDED.sync_interval_minutes,
            next_run_at = CASE
                WHEN EXCLUDED.schedule_enabled THEN COALESCE(db_connectors.next_run_at, now())
                ELSE NULL
            END,
            retry_at = NULL,
            updated_at = now()
        RETURNING id
        """
    )
    with engine.begin() as conn:
        return conn.execute(
            sql,
            {
                "name": name,
                "connector_type": connector_type,
                "db_url": db_url,
                "table_name": table_name,
                "id_column": id_column,
                "updated_at_column": updated_at_column,
                "text_columns_json": json.dumps(text_columns),
                "metadata_columns_json": json.dumps(metadata_columns),
                "corpus_name": corpus_name,
                "acl_group_names_json": json.dumps(acl_group_names),
                "connector_metadata_json": json.dumps(connector_metadata_json or {}),
                "schedule_enabled": bool(schedule_enabled),
                "sync_interval_minutes": max(1, int(sync_interval_minutes)),
            },
        ).scalar_one()


def get_db_connector(connector_id: int) -> Optional[DbConnectorRow]:
    sql = text(
        """
        SELECT id, name, connector_type, db_url, table_name, id_column, updated_at_column,
               text_columns_json, metadata_columns_json, corpus_name, acl_group_names_json,
               status, last_cursor_updated_at, last_cursor_id, last_run_at, last_error,
               connector_metadata_json, schedule_enabled, sync_interval_minutes, next_run_at,
               consecutive_failures, retry_at, last_success_at, lease_expires_at
        FROM db_connectors
        WHERE id = :connector_id
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"connector_id": connector_id}).first()
    return _row_to_connector(row) if row else None


def list_db_connectors() -> List[DbConnectorRow]:
    sql = text(
        """
        SELECT id, name, connector_type, db_url, table_name, id_column, updated_at_column,
               text_columns_json, metadata_columns_json, corpus_name, acl_group_names_json,
               status, last_cursor_updated_at, last_cursor_id, last_run_at, last_error,
               connector_metadata_json, schedule_enabled, sync_interval_minutes, next_run_at,
               consecutive_failures, retry_at, last_success_at, lease_expires_at
        FROM db_connectors
        ORDER BY updated_at DESC, id DESC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()
    return [_row_to_connector(row) for row in rows]


def claim_db_connector(connector_id: int, *, lease_seconds: int) -> Optional[DbConnectorRow]:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                UPDATE db_connectors
                SET status = 'syncing',
                    lease_expires_at = now() + (:lease_seconds * interval '1 second'),
                    last_error = NULL,
                    updated_at = now()
                WHERE id = :connector_id
                  AND (status <> 'syncing' OR lease_expires_at IS NULL OR lease_expires_at <= now())
                RETURNING id, name, connector_type, db_url, table_name, id_column, updated_at_column,
                          text_columns_json, metadata_columns_json, corpus_name, acl_group_names_json,
                          status, last_cursor_updated_at, last_cursor_id, last_run_at, last_error,
                          connector_metadata_json, schedule_enabled, sync_interval_minutes, next_run_at,
                          consecutive_failures, retry_at, last_success_at, lease_expires_at
                """
            ),
            {"connector_id": connector_id, "lease_seconds": max(1, int(lease_seconds))},
        ).first()
    return _row_to_connector(row) if row else None


def claim_due_db_connector(*, lease_seconds: int) -> Optional[DbConnectorRow]:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                WITH due AS (
                    SELECT id
                    FROM db_connectors
                    WHERE schedule_enabled = TRUE
                      AND next_run_at IS NOT NULL
                      AND next_run_at <= now()
                      AND (status <> 'syncing' OR lease_expires_at IS NULL OR lease_expires_at <= now())
                    ORDER BY next_run_at ASC, id ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE db_connectors c
                SET status = 'syncing',
                    lease_expires_at = now() + (:lease_seconds * interval '1 second'),
                    last_error = NULL,
                    updated_at = now()
                FROM due
                WHERE c.id = due.id
                RETURNING c.id, c.name, c.connector_type, c.db_url, c.table_name, c.id_column,
                          c.updated_at_column, c.text_columns_json, c.metadata_columns_json,
                          c.corpus_name, c.acl_group_names_json, c.status, c.last_cursor_updated_at,
                          c.last_cursor_id, c.last_run_at, c.last_error, c.connector_metadata_json,
                          c.schedule_enabled, c.sync_interval_minutes, c.next_run_at,
                          c.consecutive_failures, c.retry_at, c.last_success_at, c.lease_expires_at
                """
            ),
            {"lease_seconds": max(1, int(lease_seconds))},
        ).first()
    return _row_to_connector(row) if row else None


def create_connector_sync_run(*, connector_id: int, trigger_type: str, attempt_number: int) -> int:
    with engine.begin() as conn:
        return int(
            conn.execute(
                text(
                    """
                    INSERT INTO connector_sync_runs (connector_id, trigger_type, status, attempt_number)
                    VALUES (:connector_id, :trigger_type, 'running', :attempt_number)
                    RETURNING id
                    """
                ),
                {
                    "connector_id": connector_id,
                    "trigger_type": trigger_type,
                    "attempt_number": max(1, int(attempt_number)),
                },
            ).scalar_one()
        )


def mark_db_connector_sync_failed(
    connector_id: int,
    *,
    run_id: int,
    error_message: str,
    retry_seconds: int,
) -> None:
    with engine.begin() as conn:
        retry_at = conn.execute(
            text("SELECT now() + (:retry_seconds * interval '1 second')"),
            {"retry_seconds": max(1, int(retry_seconds))},
        ).scalar_one()
        conn.execute(
            text(
                """
                UPDATE db_connectors
                SET status = 'degraded',
                    last_error = :last_error,
                    last_run_at = now(),
                    consecutive_failures = consecutive_failures + 1,
                    retry_at = :retry_at,
                    next_run_at = CASE WHEN schedule_enabled THEN :retry_at ELSE NULL END,
                    lease_expires_at = NULL,
                    updated_at = now()
                WHERE id = :connector_id
                """
            ),
            {"connector_id": connector_id, "last_error": error_message[:1000], "retry_at": retry_at},
        )
        conn.execute(
            text(
                """
                UPDATE connector_sync_runs
                SET status = 'failed', error_message = :last_error, retry_at = :retry_at,
                    completed_at = now()
                WHERE id = :run_id
                """
            ),
            {"run_id": run_id, "last_error": error_message[:1000], "retry_at": retry_at},
        )


def mark_db_connector_sync_completed(
    *,
    connector_id: int,
    last_cursor_updated_at: Optional[str],
    last_cursor_id: Optional[str],
    rows_ingested: int,
    source_ids: List[int],
    run_id: int,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE db_connectors
                SET status = 'ready',
                    last_cursor_updated_at = COALESCE(:last_cursor_updated_at, last_cursor_updated_at),
                    last_cursor_id = COALESCE(:last_cursor_id, last_cursor_id),
                    last_run_at = now(),
                    last_success_at = now(),
                    last_error = NULL,
                    consecutive_failures = 0,
                    retry_at = NULL,
                    next_run_at = CASE
                        WHEN schedule_enabled THEN now() + (sync_interval_minutes * interval '1 minute')
                        ELSE NULL
                    END,
                    lease_expires_at = NULL,
                    connector_metadata_json = jsonb_set(
                        connector_metadata_json,
                        '{last_rows_ingested}',
                        to_jsonb(CAST(:rows_ingested AS int)),
                        true
                    ),
                    updated_at = now()
                WHERE id = :connector_id
                """
            ),
            {
                "connector_id": connector_id,
                "last_cursor_updated_at": last_cursor_updated_at,
                "last_cursor_id": last_cursor_id,
                "rows_ingested": rows_ingested,
            },
        )
        conn.execute(
            text(
                """
                UPDATE connector_sync_runs
                SET status = 'completed', rows_ingested = :rows_ingested,
                    source_ids_json = CAST(:source_ids_json AS jsonb), completed_at = now()
                WHERE id = :run_id
                """
            ),
            {
                "run_id": run_id,
                "rows_ingested": rows_ingested,
                "source_ids_json": json.dumps(source_ids),
            },
        )


def update_db_connector_schedule(*, connector_id: int, schedule_enabled: bool, sync_interval_minutes: int) -> Optional[DbConnectorRow]:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                UPDATE db_connectors
                SET schedule_enabled = :schedule_enabled,
                    sync_interval_minutes = :sync_interval_minutes,
                    next_run_at = CASE WHEN :schedule_enabled THEN now() ELSE NULL END,
                    retry_at = NULL,
                    updated_at = now()
                WHERE id = :connector_id
                RETURNING id, name, connector_type, db_url, table_name, id_column, updated_at_column,
                          text_columns_json, metadata_columns_json, corpus_name, acl_group_names_json,
                          status, last_cursor_updated_at, last_cursor_id, last_run_at, last_error,
                          connector_metadata_json, schedule_enabled, sync_interval_minutes, next_run_at,
                          consecutive_failures, retry_at, last_success_at, lease_expires_at
                """
            ),
            {
                "connector_id": connector_id,
                "schedule_enabled": bool(schedule_enabled),
                "sync_interval_minutes": max(1, int(sync_interval_minutes)),
            },
        ).first()
    return _row_to_connector(row) if row else None


def _row_to_sync_run(row) -> ConnectorSyncRunRow:
    return ConnectorSyncRunRow(
        id=int(row[0]),
        connector_id=int(row[1]),
        trigger_type=str(row[2]),
        status=str(row[3]),
        attempt_number=int(row[4]),
        rows_ingested=int(row[5] or 0),
        source_ids_json=[int(item) for item in (row[6] or [])],
        error_message=row[7],
        retry_at=str(row[8]) if row[8] is not None else None,
        started_at=str(row[9]) if row[9] is not None else None,
        completed_at=str(row[10]) if row[10] is not None else None,
    )


def list_connector_sync_runs(connector_id: int, *, limit: int = 50) -> List[ConnectorSyncRunRow]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, connector_id, trigger_type, status, attempt_number, rows_ingested,
                       source_ids_json, error_message, retry_at, started_at, completed_at
                FROM connector_sync_runs
                WHERE connector_id = :connector_id
                ORDER BY started_at DESC, id DESC
                LIMIT :limit
                """
            ),
            {"connector_id": connector_id, "limit": max(1, min(int(limit), 200))},
        ).fetchall()
    return [_row_to_sync_run(row) for row in rows]


def _row_to_request(row) -> ConnectorRequestRow:
    return ConnectorRequestRow(
        id=int(row[0]),
        connector_type=str(row[1]),
        requested_system=str(row[2]),
        business_reason=str(row[3] or ""),
        requested_scope_json=row[4] or {},
        status=str(row[5]),
        review_reason=row[6],
        requester_external_user_id=row[7],
        requester_email=row[8],
        requester_display_name=row[9],
        reviewed_by_external_user_id=row[10],
        reviewed_by_email=row[11],
        reviewed_at=str(row[12]) if row[12] is not None else None,
        created_at=str(row[13]) if row[13] is not None else None,
    )


def create_connector_request(
    *,
    connector_type: str,
    requested_system: str,
    business_reason: str,
    requested_scope_json: Optional[Dict[str, Any]],
    requester_external_user_id: Optional[str],
    requester_email: Optional[str],
    requester_display_name: Optional[str],
) -> int:
    sql = text(
        """
        INSERT INTO connector_requests (
            connector_type, requested_system, business_reason, requested_scope_json,
            requester_external_user_id, requester_email, requester_display_name
        )
        VALUES (
            :connector_type, :requested_system, :business_reason, CAST(:requested_scope_json AS jsonb),
            :requester_external_user_id, :requester_email, :requester_display_name
        )
        RETURNING id
        """
    )
    with engine.begin() as conn:
        return int(
            conn.execute(
                sql,
                {
                    "connector_type": connector_type,
                    "requested_system": requested_system,
                    "business_reason": business_reason,
                    "requested_scope_json": json.dumps(requested_scope_json or {}),
                    "requester_external_user_id": requester_external_user_id,
                    "requester_email": requester_email,
                    "requester_display_name": requester_display_name,
                },
            ).scalar_one()
        )


def list_connector_requests(*, requester_external_user_id: Optional[str] = None, limit: int = 200) -> List[ConnectorRequestRow]:
    conditions = []
    params: Dict[str, Any] = {"limit": limit}
    if requester_external_user_id:
        conditions.append("requester_external_user_id = :requester_external_user_id")
        params["requester_external_user_id"] = requester_external_user_id
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = text(
        f"""
        SELECT id, connector_type, requested_system, business_reason, requested_scope_json,
               status, review_reason, requester_external_user_id, requester_email,
               requester_display_name, reviewed_by_external_user_id, reviewed_by_email,
               reviewed_at, created_at
        FROM connector_requests
        {where_clause}
        ORDER BY created_at DESC, id DESC
        LIMIT :limit
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_request(row) for row in rows]


def update_connector_request_review(
    *,
    request_id: int,
    status: str,
    review_reason: str,
    reviewed_by_external_user_id: Optional[str],
    reviewed_by_email: Optional[str],
) -> Optional[ConnectorRequestRow]:
    sql = text(
        """
        UPDATE connector_requests
        SET status = :status,
            review_reason = :review_reason,
            reviewed_by_external_user_id = :reviewed_by_external_user_id,
            reviewed_by_email = :reviewed_by_email,
            reviewed_at = now(),
            updated_at = now()
        WHERE id = :request_id
        RETURNING id, connector_type, requested_system, business_reason, requested_scope_json,
                  status, review_reason, requester_external_user_id, requester_email,
                  requester_display_name, reviewed_by_external_user_id, reviewed_by_email,
                  reviewed_at, created_at
        """
    )
    with engine.begin() as conn:
        row = conn.execute(
            sql,
            {
                "request_id": request_id,
                "status": status,
                "review_reason": review_reason,
                "reviewed_by_external_user_id": reviewed_by_external_user_id,
                "reviewed_by_email": reviewed_by_email,
            },
        ).first()
    return _row_to_request(row) if row else None
