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
) -> int:
    sql = text(
        """
        INSERT INTO db_connectors (
            name, connector_type, db_url, table_name, id_column, updated_at_column,
            text_columns_json, metadata_columns_json, corpus_name, acl_group_names_json,
            status, last_error, connector_metadata_json
        )
        VALUES (
            :name, :connector_type, :db_url, :table_name, :id_column, :updated_at_column,
            CAST(:text_columns_json AS jsonb), CAST(:metadata_columns_json AS jsonb),
            :corpus_name, CAST(:acl_group_names_json AS jsonb), 'configured', NULL,
            CAST(:connector_metadata_json AS jsonb)
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
            },
        ).scalar_one()


def get_db_connector(connector_id: int) -> Optional[DbConnectorRow]:
    sql = text(
        """
        SELECT id, name, connector_type, db_url, table_name, id_column, updated_at_column,
               text_columns_json, metadata_columns_json, corpus_name, acl_group_names_json,
               status, last_cursor_updated_at, last_cursor_id, last_run_at, last_error,
               connector_metadata_json
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
               connector_metadata_json
        FROM db_connectors
        ORDER BY updated_at DESC, id DESC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()
    return [_row_to_connector(row) for row in rows]


def mark_db_connector_sync_started(connector_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE db_connectors SET status = 'syncing', last_error = NULL, updated_at = now() WHERE id = :connector_id"),
            {"connector_id": connector_id},
        )


def mark_db_connector_sync_failed(connector_id: int, error_message: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE db_connectors
                SET status = 'failed', last_error = :last_error, last_run_at = now(), updated_at = now()
                WHERE id = :connector_id
                """
            ),
            {"connector_id": connector_id, "last_error": error_message[:1000]},
        )


def mark_db_connector_sync_completed(
    *,
    connector_id: int,
    last_cursor_updated_at: Optional[str],
    last_cursor_id: Optional[str],
    rows_ingested: int,
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
                    last_error = NULL,
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
