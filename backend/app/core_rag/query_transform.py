"""LLM-backed query transformation (AR5).

Replaces the audit-named stub (`query_transform.py:9-43`): a hardcoded 5-entry
synonym dict for "expansion", whitespace-normalization for "rewrite", and a
literal prefix string for "HyDE", with no LLM anywhere. Each strategy now calls
the configured LLM, honors the profile's `transform_timeout_ms` as a TOTAL
budget across strategies, and falls back to the original query (recording
`fallback_reason`) when the LLM is slow, unreachable, or returns nothing.

The LLM call is `app.llm.client.generate_transform_text`; tests pin the
module-level `_generate` indirection to avoid network access.
"""
import re
import time
from dataclasses import dataclass, field

from app.core.logging import logger
from app.profiles.models import RetrievalProfileConfig

_REWRITE_SYSTEM = (
    "You rewrite a user's search query into a single, concise, keyword-rich query "
    "optimized for document retrieval. Preserve all entities and intent. Reply with "
    "only the rewritten query — no preamble, no quotes, no explanation."
)
_EXPANSION_SYSTEM = (
    "You expand a search query with alternative phrasings and domain synonyms to "
    "improve recall. Reply with a single line of additional search terms and short "
    "phrases separated by commas — no preamble, no numbering, no explanation."
)
_HYDE_SYSTEM = (
    "You write one short hypothetical passage (2-3 sentences) that would directly "
    "answer the user's question, as if quoted from a relevant source document. "
    "Reply with only the passage — no preamble, no caveats."
)


@dataclass
class QueryTransformResult:
    effective_query: str
    generated_queries: list[str]
    trace: dict
    variant_details: list[dict] = field(default_factory=list)


def _generate(system_prompt: str, user_prompt: str, *, timeout_s: float, max_tokens: int = 256) -> dict:
    """Indirection over the LLM client so tests can pin transform behavior
    without network access. Returns {"success": bool, "content": str, ...}."""
    from app.llm.client import generate_transform_text

    return generate_transform_text(system_prompt, user_prompt, timeout_s=timeout_s, max_tokens=max_tokens)


def _normalize_query(question: str) -> str:
    return re.sub(r"\s+", " ", question or "").strip()


def _clean_variant(text: str) -> str:
    cleaned = _normalize_query(text)
    # Strip a leading label like "Query:" or surrounding quotes the model may add.
    cleaned = re.sub(r'^(rewritten query|query|passage|answer)\s*[:\-]\s*', "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip().strip('"').strip()


def transform_query(question: str, profile: RetrievalProfileConfig) -> QueryTransformResult:
    start = time.time()
    original = _normalize_query(question)
    budget_ms = max(0, int(profile.transform_timeout_ms))
    trace = {
        "enabled": bool(profile.query_transform_enabled),
        "strategy": [],
        "original_query": original,
        "generated_queries": [],
        "latency_ms": 0,
        "budget_ms": budget_ms,
        "fallback_reason": None,
        "variant_status": {},
        "llm_calls": 0,
    }
    if not profile.query_transform_enabled:
        return QueryTransformResult(effective_query=original, generated_queries=[], trace=trace)

    requested = []
    if profile.rewrite_enabled:
        requested.append(("rewrite", _REWRITE_SYSTEM, original))
    if profile.expansion_enabled:
        requested.append(("expansion", _EXPANSION_SYSTEM, original))
    if profile.hyde_enabled:
        requested.append(("hyde", _HYDE_SYSTEM, original))

    variants: list[str] = []
    variant_details: list[dict] = []
    seen = {original}
    for name, system_prompt, user_prompt in requested:
        trace["strategy"].append(name)
        elapsed_ms = int((time.time() - start) * 1000)
        remaining_ms = budget_ms - elapsed_ms
        if remaining_ms <= 0:
            trace["variant_status"][name] = "skipped_budget_exhausted"
            trace["fallback_reason"] = trace["fallback_reason"] or "timeout_budget_exhausted"
            continue
        try:
            result = _generate(system_prompt, user_prompt, timeout_s=remaining_ms / 1000.0)
        except Exception as exc:  # defensive: the call itself raised
            logger.warning("Query transform '%s' raised: %s", name, exc)
            trace["variant_status"][name] = "error"
            trace["fallback_reason"] = trace["fallback_reason"] or str(exc)
            continue
        trace["llm_calls"] += 1
        if not result.get("success"):
            status = "timeout" if result.get("timeout") else "llm_unavailable"
            trace["variant_status"][name] = status
            trace["fallback_reason"] = trace["fallback_reason"] or result.get("error") or status
            continue
        variant = _clean_variant(result.get("content") or "")
        if name == "expansion" and variant:
            # Expansion returns terms to append to the original, not a replacement.
            variant = _normalize_query(f"{original} {variant}")
        if not variant or variant in seen:
            trace["variant_status"][name] = "empty" if not variant else "duplicate"
            continue
        seen.add(variant)
        variants.append(variant)
        variant_details.append({"strategy": name, "query": variant})
        trace["variant_status"][name] = "generated"

    variants = variants[: max(0, int(profile.transform_max_variants))]
    variant_details = variant_details[: len(variants)]
    trace["generated_queries"] = variants

    if not variants:
        trace["fallback_reason"] = trace["fallback_reason"] or "no_variants_generated"
        effective_query = original
    else:
        # Single-query mode concatenates; multi-query fan-out (retrieval.py)
        # retrieves each variant separately and ignores this concatenation.
        effective_query = " ".join([original, *variants]).strip()

    trace["latency_ms"] = int((time.time() - start) * 1000)
    return QueryTransformResult(
        effective_query=effective_query or original,
        generated_queries=variants,
        trace=trace,
        variant_details=variant_details,
    )
