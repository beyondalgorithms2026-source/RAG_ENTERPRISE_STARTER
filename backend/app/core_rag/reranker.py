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
    policy["mmr"]["reason"] = "placeholder_reserved_for_future_milestone" if profile.mmr_enabled else "disabled"
    return policy


def apply_mmr_placeholder(chunks: List[Dict], policy: dict) -> List[Dict]:
    mmr_policy = dict(policy.get("mmr") or {})
    if mmr_policy.get("enabled"):
        mmr_policy["applied"] = False
        mmr_policy["reason"] = "placeholder_reserved_for_future_milestone"
    policy["mmr"] = mmr_policy
    return chunks


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


def rerank(question: str, chunks: List[Dict], top_k: int) -> List[Dict]:
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
    effective_top = profile.top_n or top_k
    return chunks[:effective_top]
