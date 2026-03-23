import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from sqlalchemy import text

from app.db.db import engine


@dataclass
class SourcePartRow:
    id: int
    source_id: int
    parent_part_id: Optional[int]
    part_type: str
    part_index: int
    title: Optional[str]
    locator_json: Dict
    content_text: Optional[str]
    provenance_json: Dict


def insert_source_part(
    *,
    source_id: int,
    part_type: str,
    part_index: int,
    title: Optional[str] = None,
    parent_part_id: Optional[int] = None,
    locator_json: Optional[Dict] = None,
    content_text: Optional[str] = None,
    provenance_json: Optional[Dict] = None,
) -> int:
    sql = text(
        """
        INSERT INTO source_parts (
            source_id, parent_part_id, part_type, part_index, title,
            locator_json, content_text, provenance_json
        )
        VALUES (
            :source_id, :parent_part_id, :part_type, :part_index, :title,
            CAST(:locator_json AS jsonb), :content_text, CAST(:provenance_json AS jsonb)
        )
        RETURNING id
        """
    )
    params = {
        "source_id": source_id,
        "parent_part_id": parent_part_id,
        "part_type": part_type,
        "part_index": part_index,
        "title": title,
        "locator_json": json.dumps(locator_json or {}),
        "content_text": content_text,
        "provenance_json": json.dumps(provenance_json or {}),
    }
    with engine.begin() as conn:
        return conn.execute(sql, params).scalar_one()


def list_source_parts(source_id: int) -> List[SourcePartRow]:
    sql = text(
        """
        SELECT id, source_id, parent_part_id, part_type, part_index, title,
               locator_json, content_text, provenance_json
        FROM source_parts
        WHERE source_id = :source_id
        ORDER BY part_index ASC, id ASC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"source_id": source_id}).fetchall()
    return [SourcePartRow(*row) for row in rows]


def delete_source_parts_for_source(source_id: int) -> None:
    sql = text("DELETE FROM source_parts WHERE source_id = :source_id")
    with engine.begin() as conn:
        conn.execute(sql, {"source_id": source_id})


def get_source_part(source_part_id: int) -> Optional[SourcePartRow]:
    sql = text(
        """
        SELECT id, source_id, parent_part_id, part_type, part_index, title,
               locator_json, content_text, provenance_json
        FROM source_parts
        WHERE id = :source_part_id
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"source_part_id": source_part_id}).first()
    if not row:
        return None
    return SourcePartRow(*row)
