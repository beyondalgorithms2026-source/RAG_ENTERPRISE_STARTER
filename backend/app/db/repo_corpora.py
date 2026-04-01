import json
from typing import Any, Dict, Optional

from sqlalchemy import text

from app.db.db import engine


def list_corpora() -> list[dict[str, Any]]:
    sql = text(
        """
        SELECT
            c.name,
            c.description,
            c.metadata_json,
            c.created_at,
            c.updated_at,
            COALESCE(source_stats.source_count, 0) AS source_count
        FROM corpora c
        LEFT JOIN (
            SELECT
                source_metadata_json ->> 'corpus' AS corpus_name,
                COUNT(*)::bigint AS source_count
            FROM sources
            WHERE COALESCE(source_metadata_json ->> 'corpus', '') <> ''
            GROUP BY source_metadata_json ->> 'corpus'
        ) AS source_stats
            ON source_stats.corpus_name = c.name
        ORDER BY c.name ASC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
    return [dict(row) for row in rows]


def get_corpus(name: str) -> Optional[dict[str, Any]]:
    sql = text(
        """
        SELECT name, description, metadata_json, created_at, updated_at
        FROM corpora
        WHERE name = :name
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"name": name}).mappings().first()
    return dict(row) if row else None


def upsert_corpus(*, name: str, description: str = "", metadata_json: Optional[Dict[str, Any]] = None) -> dict[str, Any]:
    sql = text(
        """
        INSERT INTO corpora (name, description, metadata_json)
        VALUES (:name, :description, CAST(:metadata_json AS jsonb))
        ON CONFLICT (name) DO UPDATE
        SET description = EXCLUDED.description,
            metadata_json = EXCLUDED.metadata_json,
            updated_at = now()
        RETURNING name, description, metadata_json, created_at, updated_at
        """
    )
    with engine.begin() as conn:
        row = conn.execute(
            sql,
            {
                "name": name,
                "description": description,
                "metadata_json": json.dumps(metadata_json or {}),
            },
        ).mappings().one()
    return dict(row)
