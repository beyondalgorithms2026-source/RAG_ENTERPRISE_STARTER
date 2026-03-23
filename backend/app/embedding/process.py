import time
from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.logging import logger
from app.db.repo_chunks import get_chunks_to_embed, update_chunk_embeddings
from app.embedding.embedder import embed_texts, get_expected_dim


def process_embeddings(force: bool = False, limit: Optional[int] = None, source_id: Optional[int] = None) -> Dict[str, Any]:
    start_time = time.time()
    chunks = get_chunks_to_embed(force=force, limit=limit, source_id=source_id)

    stats = {
        "chunks_total_selected": len(chunks),
        "chunks_embedded": 0,
        "chunks_failed": 0,
        "expected_dim": None,
        "time_taken_s": 0.0,
    }

    if not chunks:
        logger.info("No chunks found requiring embeddings.")
        stats["time_taken_s"] = round(time.time() - start_time, 2)
        return stats

    expected_dim = get_expected_dim()
    stats["expected_dim"] = expected_dim
    batch_size = settings.EMBEDDING_BATCH_SIZE

    for batch_start in range(0, len(chunks), batch_size):
        batch = chunks[batch_start : batch_start + batch_size]
        valid_ids = []
        valid_texts = []

        for chunk in batch:
            text = (chunk.get("chunk_text") or "").strip()
            if not text:
                logger.warning("Skipping empty chunk text for chunk_id=%s", chunk.get("id"))
                stats["chunks_failed"] += 1
                continue
            valid_ids.append(chunk["id"])
            valid_texts.append(text)

        if not valid_texts:
            continue

        try:
            embeddings = embed_texts(valid_texts)
        except Exception as exc:
            logger.error("Embedding batch failed: %s", exc)
            stats["chunks_failed"] += len(valid_texts)
            continue

        db_updates = []
        for chunk_id, vector in zip(valid_ids, embeddings):
            if len(vector) != expected_dim:
                logger.error(
                    "Embedding dimension mismatch for chunk_id=%s: expected=%s actual=%s",
                    chunk_id,
                    expected_dim,
                    len(vector),
                )
                stats["chunks_failed"] += 1
                continue
            db_updates.append((chunk_id, vector))

        if db_updates:
            update_chunk_embeddings(db_updates)
            stats["chunks_embedded"] += len(db_updates)

    stats["time_taken_s"] = round(time.time() - start_time, 2)
    return stats
