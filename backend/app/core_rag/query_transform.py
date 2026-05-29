import re
import time
from dataclasses import dataclass

from app.core.logging import logger
from app.profiles.models import RetrievalProfileConfig


_EXPANSIONS = {
    "q4": ["fourth quarter", "quarter 4"],
    "liability": ["responsibility", "obligation"],
    "subcontracting": ["subcontractor", "third party work"],
    "budget": ["forecast", "spend"],
    "compensation": ["salary", "pay"],
}


@dataclass
class QueryTransformResult:
    effective_query: str
    generated_queries: list[str]
    trace: dict


def _normalize_query(question: str) -> str:
    cleaned = re.sub(r"\s+", " ", question or "").strip()
    return cleaned


def _expanded_query(question: str) -> str:
    additions: list[str] = []
    lowered = question.lower()
    for token, synonyms in _EXPANSIONS.items():
        if token in lowered:
            additions.extend(synonyms)
    if not additions:
        return question
    return f"{question} {' '.join(additions[:8])}"


def _hyde_query(question: str) -> str:
    return f"Hypothetical relevant passage answering: {question}"


def transform_query(question: str, profile: RetrievalProfileConfig) -> QueryTransformResult:
    start = time.time()
    original = _normalize_query(question)
    trace = {
        "enabled": bool(profile.query_transform_enabled),
        "strategy": [],
        "original_query": original,
        "generated_queries": [],
        "latency_ms": 0,
        "fallback_reason": None,
    }
    if not profile.query_transform_enabled:
        return QueryTransformResult(effective_query=original, generated_queries=[], trace=trace)

    try:
        variants: list[str] = []
        if profile.rewrite_enabled:
            rewritten = _normalize_query(original)
            if rewritten and rewritten != original:
                variants.append(rewritten)
            trace["strategy"].append("rewrite")
        if profile.expansion_enabled:
            variants.append(_expanded_query(original))
            trace["strategy"].append("expansion")
        if profile.hyde_enabled:
            variants.append(_hyde_query(original))
            trace["strategy"].append("hyde")
        unique_variants: list[str] = []
        seen = {original}
        for variant in variants:
            normalized = _normalize_query(variant)
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique_variants.append(normalized)
        unique_variants = unique_variants[: max(0, int(profile.transform_max_variants))]
        effective_query = " ".join([original, *unique_variants]).strip()
        trace["generated_queries"] = unique_variants
        return QueryTransformResult(effective_query=effective_query or original, generated_queries=unique_variants, trace=trace)
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("Query transform failed: %s", exc)
        trace["fallback_reason"] = str(exc)
        return QueryTransformResult(effective_query=original, generated_queries=[], trace=trace)
    finally:
        trace["latency_ms"] = int((time.time() - start) * 1000)
