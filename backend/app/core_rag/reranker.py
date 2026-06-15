import math
import time
from typing import Dict, List

from app.core.logging import logger


RERANK_CHUNK_CAP = 2000
_reranker = None
_loaded_reranker_model: str | None = None


def _normalize_policy_values(values: List[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        token = str(value or "").strip().lower()
        if not token or token in seen:
            continue
        seen.add(token)
        normalized.append(token)
    return normalized


def evaluate_rerank_policy(
    *,
    resolved_mode: str,
    chunks: List[Dict],
    candidate_corpora: List[str],
    search_latency_ms: int,
) -> dict:
    from app.profiles.resolver import get_effective_reranker

    profile = get_effective_reranker()
    allowed_modes = _normalize_policy_values(profile.enabled_modes)
    allowed_corpora = _normalize_policy_values(profile.enabled_corpora)
    observed_corpora = _normalize_policy_values(candidate_corpora)
    candidate_count = len(chunks)
    policy = {
        "enabled": bool(profile.enabled),
        "eligible": False,
        "applied": False,
        "reason": "reranker_disabled",
        "mode": resolved_mode,
        "allowed_modes": allowed_modes,
        "allowed_corpora": allowed_corpora,
        "observed_corpora": observed_corpora,
        "candidate_count": candidate_count,
        "min_candidate_count": int(profile.min_candidate_count or 0),
        "max_candidate_count": profile.max_candidate_count,
        "search_latency_ms": int(search_latency_ms or 0),
        "latency_budget_ms": profile.latency_budget_ms,
        "top_n": profile.top_n,
        "score_threshold": profile.score_threshold,
        "model": profile.model,
        "mmr": {
            "enabled": bool(profile.mmr_enabled),
            "applied": False,
            "lambda": float(profile.mmr_lambda),
            "reason": "disabled",
        },
    }

    if not profile.enabled:
        return policy
    if not chunks:
        policy["reason"] = "no_candidates"
        return policy
    if allowed_modes and str(resolved_mode).strip().lower() not in allowed_modes:
        policy["reason"] = "mode_not_enabled"
        return policy
    if allowed_corpora and not any(corpus in allowed_corpora for corpus in observed_corpora):
        policy["reason"] = "corpus_not_enabled"
        return policy
    if candidate_count < int(profile.min_candidate_count or 0):
        policy["reason"] = "candidate_count_below_min"
        return policy
    if profile.max_candidate_count is not None and candidate_count > int(profile.max_candidate_count):
        policy["reason"] = "candidate_count_above_max"
        return policy
    if profile.latency_budget_ms is not None and int(search_latency_ms or 0) > int(profile.latency_budget_ms):
        policy["reason"] = "latency_budget_exceeded"
        return policy

    policy["eligible"] = True
    policy["reason"] = "eligible_policy_match"
    policy["mmr"]["reason"] = "eligible" if profile.mmr_enabled else "disabled"
    return policy


def _cosine_similarity(left: List[float], right: List[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def _normalized_relevance(chunks: List[Dict]) -> dict[int, float]:
    scores = [float(chunk.get("rerank_score") or 0.0) for chunk in chunks]
    low = min(scores, default=0.0)
    high = max(scores, default=0.0)
    if high <= low:
        return {int(chunk["chunk_id"]): 1.0 for chunk in chunks}
    return {
        int(chunk["chunk_id"]): (float(chunk.get("rerank_score") or 0.0) - low) / (high - low)
        for chunk in chunks
    }


def apply_mmr(chunks: List[Dict], policy: dict, *, top_k: int) -> List[Dict]:
    started_at = time.perf_counter()
    mmr_policy = dict(policy.get("mmr") or {})
    effective_top = max(0, min(int(top_k), len(chunks)))
    if not mmr_policy.get("enabled") or effective_top == 0:
        mmr_policy["applied"] = False
        mmr_policy["reason"] = "disabled" if not mmr_policy.get("enabled") else "no_candidates"
        mmr_policy["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 3)
        policy["mmr"] = mmr_policy
        return chunks[:effective_top]

    from app.db.repo_chunks import fetch_chunk_embeddings

    embeddings = fetch_chunk_embeddings([int(chunk["chunk_id"]) for chunk in chunks])
    if len(embeddings) != len(chunks):
        mmr_policy["applied"] = False
        mmr_policy["reason"] = "missing_candidate_embeddings"
        mmr_policy["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 3)
        policy["mmr"] = mmr_policy
        return chunks[:effective_top]

    relevance = _normalized_relevance(chunks)
    candidate_by_id = {int(chunk["chunk_id"]): chunk for chunk in chunks}
    remaining = list(candidate_by_id)
    selected: List[int] = []
    lambda_value = min(1.0, max(0.0, float(mmr_policy.get("lambda") or 0.5)))
    while remaining and len(selected) < effective_top:
        def mmr_score(chunk_id: int) -> tuple[float, float, int]:
            redundancy = max(
                (_cosine_similarity(embeddings[chunk_id], embeddings[selected_id]) for selected_id in selected),
                default=0.0,
            )
            score = lambda_value * relevance[chunk_id] - (1.0 - lambda_value) * redundancy
            return score, relevance[chunk_id], -remaining.index(chunk_id)

        chosen = max(remaining, key=mmr_score)
        selected.append(chosen)
        remaining.remove(chosen)

    mmr_policy["applied"] = True
    mmr_policy["reason"] = "eval_proven_diversity"
    mmr_policy["selected_chunk_ids"] = selected
    mmr_policy["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 3)
    policy["mmr"] = mmr_policy
    return [candidate_by_id[chunk_id] for chunk_id in selected]


def get_reranker():
    global _reranker, _loaded_reranker_model
    from app.profiles.resolver import get_effective_reranker
    profile = get_effective_reranker()
    if _reranker is None or _loaded_reranker_model != profile.model:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required to load the reranker model."
            ) from exc

        logger.info(f"Loading reranker model: {profile.model}")
        _reranker = CrossEncoder(profile.model)
        _loaded_reranker_model = profile.model
        logger.info("Reranker model loaded successfully.")
    return _reranker


def rerank(question: str, chunks: List[Dict]) -> List[Dict]:
    from app.profiles.resolver import get_effective_reranker
    profile = get_effective_reranker()
    model = get_reranker()
    pairs = [(question, chunk["snippet"][:RERANK_CHUNK_CAP]) for chunk in chunks]
    scores = model.predict(pairs)

    for index, chunk in enumerate(chunks):
        chunk["rerank_score"] = float(scores[index])

    if profile.score_threshold is not None:
        chunks = [c for c in chunks if c["rerank_score"] >= profile.score_threshold]

    chunks.sort(key=lambda item: item["rerank_score"], reverse=True)
    return chunks
