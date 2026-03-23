from typing import Dict, List

from app.core.config import settings
from app.core.logging import logger


RERANK_CHUNK_CAP = 2000
_reranker = None


def get_reranker():
    global _reranker
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required to load the reranker model."
            ) from exc

        logger.info(f"Loading reranker model: {settings.RERANK_MODEL}")
        _reranker = CrossEncoder(settings.RERANK_MODEL)
        logger.info("Reranker model loaded successfully.")
    return _reranker


def rerank(question: str, chunks: List[Dict], top_k: int) -> List[Dict]:
    model = get_reranker()
    pairs = [(question, chunk["snippet"][:RERANK_CHUNK_CAP]) for chunk in chunks]
    scores = model.predict(pairs)

    for index, chunk in enumerate(chunks):
        chunk["rerank_score"] = float(scores[index])

    chunks.sort(key=lambda item: item["rerank_score"], reverse=True)
    return chunks[:top_k]
