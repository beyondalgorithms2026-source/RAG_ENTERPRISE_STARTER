import json
import math
from typing import Dict, List, Optional

from sqlalchemy import text

from app.db.db import engine


def _pgvector_literal(vec: List[float], decimals: int = 8) -> str:
    parts = []
    for value in vec:
        if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
            value = 0.0
        parts.append(f"{float(value):.{decimals}f}")
    return "[" + ",".join(parts) + "]"


def check_chunks_exist(source_id: int) -> bool:
    sql = text("SELECT id FROM chunks WHERE source_id = :source_id LIMIT 1")
    with engine.connect() as conn:
        return conn.execute(sql, {"source_id": source_id}).first() is not None


def delete_chunks_for_source(source_id: int) -> None:
    sql = text("DELETE FROM chunks WHERE source_id = :source_id")
    with engine.begin() as conn:
        conn.execute(sql, {"source_id": source_id})


def insert_chunks(source_id: int, chunks: List[Dict], source_part_id: Optional[int] = None) -> None:
    sql = text(
        """
        INSERT INTO chunks (
            source_id, source_part_id, chunk_index, heading, section_path, chunk_text,
            token_count, locator_json, entities_json, relations_json, temporal_json,
            provenance_json, search_tsv
        )
        VALUES (
            :source_id, :source_part_id, :chunk_index, :heading, :section_path, :chunk_text,
            :token_count, CAST(:locator_json AS jsonb), CAST(:entities_json AS jsonb),
            CAST(:relations_json AS jsonb), CAST(:temporal_json AS jsonb),
            CAST(:provenance_json AS jsonb), to_tsvector('english', :chunk_text)
        )
        """
    )
    with engine.begin() as conn:
        for index, chunk in enumerate(chunks):
            conn.execute(
                sql,
                {
                    "source_id": source_id,
                    "source_part_id": chunk.get("source_part_id", source_part_id),
                    "chunk_index": chunk.get("chunk_index", index),
                    "heading": chunk.get("heading", ""),
                    "section_path": chunk.get("section_path", ""),
                    "chunk_text": chunk["chunk_text"],
                    "token_count": chunk.get("token_count", 0),
                    "locator_json": json.dumps(chunk.get("locator_json", {})),
                    "entities_json": json.dumps(chunk.get("entities_json", [])),
                    "relations_json": json.dumps(chunk.get("relations_json", [])),
                    "temporal_json": json.dumps(chunk.get("temporal_json", {})),
                    "provenance_json": json.dumps(chunk.get("provenance_json", {})),
                },
            )


def get_chunks_to_embed(force: bool = False, limit: Optional[int] = None, source_id: Optional[int] = None) -> List[Dict]:
    conditions = []
    params: Dict[str, object] = {}

    if not force:
        conditions.append("embedding IS NULL")
    if source_id is not None:
        conditions.append("source_id = :source_id")
        params["source_id"] = source_id

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    limit_clause = "LIMIT :limit" if limit is not None else ""
    if limit is not None:
        params["limit"] = limit

    sql = text(
        f"""
        SELECT id, source_id, source_part_id, chunk_text
        FROM chunks
        {where_clause}
        ORDER BY source_id ASC, chunk_index ASC
        {limit_clause}
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, params).fetchall()

    return [
        {
            "id": row[0],
            "source_id": row[1],
            "source_part_id": row[2],
            "chunk_text": row[3],
        }
        for row in rows
    ]


def get_chunks_for_enrichment(source_id: int) -> List[Dict]:
    sql = text(
        """
        SELECT id, source_id, source_part_id, chunk_index, heading, chunk_text,
               locator_json, entities_json, relations_json, provenance_json, temporal_json
        FROM chunks
        WHERE source_id = :source_id
        ORDER BY chunk_index ASC, id ASC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"source_id": source_id}).fetchall()

    return [
        {
            "id": row[0],
            "source_id": row[1],
            "source_part_id": row[2],
            "chunk_index": row[3],
            "heading": row[4],
            "chunk_text": row[5],
            "locator_json": row[6] or {},
            "entities_json": row[7] or [],
            "relations_json": row[8] or [],
            "provenance_json": row[9] or {},
            "temporal_json": row[10] or {},
        }
        for row in rows
    ]


def update_chunk_enrichment(
    *,
    chunk_id: int,
    entities_json: List[Dict],
    relations_json: List[Dict],
    temporal_json: Dict,
    provenance_json: Dict,
) -> None:
    sql = text(
        """
        UPDATE chunks
        SET entities_json = CAST(:entities_json AS jsonb),
            relations_json = CAST(:relations_json AS jsonb),
            temporal_json = CAST(:temporal_json AS jsonb),
            provenance_json = CAST(:provenance_json AS jsonb),
            updated_at = now()
        WHERE id = :chunk_id
        """
    )
    with engine.begin() as conn:
        conn.execute(
            sql,
            {
                "chunk_id": chunk_id,
                "entities_json": json.dumps(entities_json),
                "relations_json": json.dumps(relations_json),
                "temporal_json": json.dumps(temporal_json),
                "provenance_json": json.dumps(provenance_json),
            },
        )


def update_chunk_embeddings(chunk_embeddings: List[tuple[int, List[float]]]) -> None:
    if not chunk_embeddings:
        return

    sql = text("UPDATE chunks SET embedding = CAST(:embedding AS vector), updated_at = now() WHERE id = :chunk_id")
    with engine.begin() as conn:
        for chunk_id, embedding_vector in chunk_embeddings:
            conn.execute(sql, {"chunk_id": chunk_id, "embedding": _pgvector_literal(embedding_vector)})


def fetch_neighbor_chunks(chunk_ids: List[int], radius: int = 1) -> List[Dict]:
    if not chunk_ids or radius < 1:
        return []

    sql = text(
        """
        WITH base AS (
            SELECT DISTINCT source_id, chunk_index
            FROM chunks
            WHERE id = ANY(:chunk_ids)
        )
        SELECT DISTINCT
            c.id,
            c.source_id,
            c.source_part_id,
            c.chunk_index,
            c.heading,
            c.chunk_text,
            c.locator_json
        FROM chunks c
        JOIN base b
            ON c.source_id = b.source_id
           AND c.chunk_index BETWEEN b.chunk_index - :radius AND b.chunk_index + :radius
        WHERE c.id <> ALL(:chunk_ids)
        ORDER BY c.source_id ASC, c.chunk_index ASC, c.id ASC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"chunk_ids": list(chunk_ids), "radius": radius}).fetchall()

    return [
        {
            "id": row[0],
            "source_id": row[1],
            "source_part_id": row[2],
            "chunk_index": row[3],
            "heading": row[4],
            "chunk_text": row[5],
            "locator_json": row[6] or {},
        }
        for row in rows
    ]
