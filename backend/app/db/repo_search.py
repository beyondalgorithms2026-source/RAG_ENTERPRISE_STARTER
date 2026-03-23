import math
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.db.db import engine


def _pgvector_literal(vec: List[float], decimals: int = 8) -> str:
    parts = []
    for value in vec:
        if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
            value = 0.0
        parts.append(f"{float(value):.{decimals}f}")
    return "[" + ",".join(parts) + "]"


def _row_to_result(row: Any, score_key: str, score_value: Optional[float]) -> Dict[str, Any]:
    return {
        "chunk_id": row[0],
        "source_id": row[1],
        "source_part_id": row[2],
        "file_name": row[3],
        "source_type": row[4],
        "heading": row[5],
        "locator": row[6],
        "snippet": row[7],
        score_key: score_value,
        "chunk_index": row[9],
    }


def search_chunks(
    query_vector: List[float],
    k: int = 10,
    source_type: Optional[str] = None,
    source_id: Optional[int] = None,
    source_ids: Optional[List[int]] = None,
    source_part_id: Optional[int] = None,
    locator_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    sql_base = """
        SELECT
            c.id AS chunk_id,
            c.source_id,
            c.source_part_id,
            s.file_name,
            s.source_type,
            c.heading,
            COALESCE(c.locator_json::text, sp.locator_json::text, '') AS locator,
            c.chunk_text,
            (c.embedding <=> CAST(:query_embedding AS vector)) AS distance,
            c.chunk_index
        FROM chunks c
        JOIN sources s ON c.source_id = s.id
        LEFT JOIN source_parts sp ON c.source_part_id = sp.id
        WHERE c.embedding IS NOT NULL
    """
    conditions = []
    params: Dict[str, Any] = {"query_embedding": _pgvector_literal(query_vector), "k": k}

    if source_type:
        conditions.append("s.source_type = :source_type")
        params["source_type"] = source_type

    if source_id is not None:
        conditions.append("s.id = :source_id")
        params["source_id"] = source_id
    elif source_ids:
        conditions.append("s.id = ANY(:source_ids)")
        params["source_ids"] = list(source_ids)

    if source_part_id is not None:
        conditions.append("c.source_part_id = :source_part_id")
        params["source_part_id"] = source_part_id

    if locator_filter:
        conditions.append("COALESCE(c.locator_json::text, sp.locator_json::text, '') ILIKE :locator_filter")
        params["locator_filter"] = f"%{locator_filter}%"

    if conditions:
        sql_base += " AND " + " AND ".join(conditions)

    sql_base += " ORDER BY distance ASC, c.chunk_index ASC LIMIT :k"

    with engine.connect() as conn:
        rows = conn.execute(text(sql_base), params).fetchall()

    return [_row_to_result(row, "distance", float(row[8])) for row in rows]


def search_chunks_keyword(
    query_text: str,
    k: int = 10,
    source_type: Optional[str] = None,
    source_id: Optional[int] = None,
    source_ids: Optional[List[int]] = None,
    source_part_id: Optional[int] = None,
    locator_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    sql_base = """
        SELECT
            c.id AS chunk_id,
            c.source_id,
            c.source_part_id,
            s.file_name,
            s.source_type,
            c.heading,
            COALESCE(c.locator_json::text, sp.locator_json::text, '') AS locator,
            c.chunk_text,
            ts_rank_cd(c.search_tsv, websearch_to_tsquery('english', :query_text)) AS rank_score,
            c.chunk_index
        FROM chunks c
        JOIN sources s ON c.source_id = s.id
        LEFT JOIN source_parts sp ON c.source_part_id = sp.id
        WHERE c.search_tsv @@ websearch_to_tsquery('english', :query_text)
    """
    conditions = []
    params: Dict[str, Any] = {"query_text": query_text, "k": k}

    if source_type:
        conditions.append("s.source_type = :source_type")
        params["source_type"] = source_type

    if source_id is not None:
        conditions.append("s.id = :source_id")
        params["source_id"] = source_id
    elif source_ids:
        conditions.append("s.id = ANY(:source_ids)")
        params["source_ids"] = list(source_ids)

    if source_part_id is not None:
        conditions.append("c.source_part_id = :source_part_id")
        params["source_part_id"] = source_part_id

    if locator_filter:
        conditions.append("COALESCE(c.locator_json::text, sp.locator_json::text, '') ILIKE :locator_filter")
        params["locator_filter"] = f"%{locator_filter}%"

    if conditions:
        sql_base += " AND " + " AND ".join(conditions)

    sql_base += " ORDER BY rank_score DESC, c.chunk_index ASC LIMIT :k"

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql_base), params).fetchall()
    except Exception:
        fallback_sql = text(sql_base.replace("websearch_to_tsquery", "plainto_tsquery"))
        with engine.connect() as conn:
            rows = conn.execute(fallback_sql, params).fetchall()

    results = []
    for row in rows:
        item = _row_to_result(row, "rank_score", float(row[8]))
        item["distance"] = None
        results.append(item)
    return results


def fetch_chunks_by_ids(chunk_ids: List[int]) -> List[Dict[str, Any]]:
    if not chunk_ids:
        return []

    sql = text(
        """
        SELECT
            c.id AS chunk_id,
            c.source_id,
            c.source_part_id,
            s.file_name,
            s.source_type,
            c.heading,
            COALESCE(c.locator_json::text, sp.locator_json::text, '') AS locator,
            c.chunk_text,
            NULL::float8 AS distance,
            c.chunk_index
        FROM chunks c
        JOIN sources s ON c.source_id = s.id
        LEFT JOIN source_parts sp ON c.source_part_id = sp.id
        WHERE c.id = ANY(:chunk_ids)
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"chunk_ids": list(chunk_ids)}).fetchall()

    row_by_chunk_id = {row[0]: row for row in rows}
    ordered_results: List[Dict[str, Any]] = []
    for chunk_id in chunk_ids:
        row = row_by_chunk_id.get(chunk_id)
        if row is None:
            continue
        item = _row_to_result(row, "distance", None)
        item["vector_score"] = 0.0
        item["keyword_score"] = 0.0
        item["rank_score"] = 0.0
        ordered_results.append(item)
    return ordered_results


# TODO: donor repo_search carried contract-specific filter assumptions; keep any future cleanup minimal until M3 schema work lands.
