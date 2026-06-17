import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator, Optional

from app.core.config import settings
from app.core.logging import logger
from app.profiles.models import (
    EmbeddingProfileConfig,
    LLMProfileConfig,
    RerankerProfileConfig,
    RetrievalProfileConfig,
)

_CACHE_TTL_S = 5.0
_cache: dict[str, tuple[float, Any]] = {}

# AR8: request-scoped profile overrides. A ContextVar is isolated per thread and
# per asyncio task, so a candidate bundle applied during a sandbox compare or
# candidate eval cannot bleed into a concurrent live request — unlike the prior
# module-global monkeypatching the audit flagged as a correctness hazard.
_override_ctx: ContextVar[Optional[dict]] = ContextVar("profile_overrides", default=None)


def current_profile_overrides() -> dict:
    return _override_ctx.get() or {}


@contextmanager
def profile_overrides(
    *,
    retrieval: Optional[RetrievalProfileConfig] = None,
    reranker: Optional[RerankerProfileConfig] = None,
    llm: Optional[LLMProfileConfig] = None,
    embedding: Optional[EmbeddingProfileConfig] = None,
    chunk_cap: Optional[int] = None,
) -> Iterator[None]:
    """Apply profile/chunk-cap overrides for the current execution context only."""
    base = dict(_override_ctx.get() or {})
    for key, value in (
        ("retrieval", retrieval),
        ("reranker", reranker),
        ("llm", llm),
        ("embedding", embedding),
        ("chunk_cap", chunk_cap),
    ):
        if value is not None:
            base[key] = value
    token = _override_ctx.set(base)
    try:
        yield
    finally:
        _override_ctx.reset(token)


def _get_cached(profile_type: str) -> Optional[dict]:
    entry = _cache.get(profile_type)
    if entry and (time.monotonic() - entry[0]) < _CACHE_TTL_S:
        return entry[1]
    return None


def _set_cached(profile_type: str, config: dict) -> None:
    _cache[profile_type] = (time.monotonic(), config)


def invalidate_cache(profile_type: Optional[str] = None) -> None:
    if profile_type:
        _cache.pop(profile_type, None)
    else:
        _cache.clear()


def _load_active_config(profile_type: str) -> Optional[dict]:
    cached = _get_cached(profile_type)
    if cached is not None:
        return cached
    try:
        from app.db.repo_profiles import get_active_profile_config
        config = get_active_profile_config(profile_type)
    except Exception as exc:
        logger.debug("Could not load active %s profile from DB: %s", profile_type, exc)
        return None
    if config is not None:
        _set_cached(profile_type, config)
    return config


def get_effective_embedding() -> EmbeddingProfileConfig:
    override = _override_ctx.get()
    if override and override.get("embedding") is not None:
        return override["embedding"]
    config = _load_active_config("embedding")
    if config:
        return EmbeddingProfileConfig(**config)
    try:
        from app.embedding.embedder import get_expected_dim
        dim = get_expected_dim()
    except Exception:
        dim = 384
    return EmbeddingProfileConfig(
        model=settings.EMBEDDING_MODEL,
        dimension=dim,
        batch_size=settings.EMBEDDING_BATCH_SIZE,
    )


def get_effective_reranker() -> RerankerProfileConfig:
    override = _override_ctx.get()
    if override and override.get("reranker") is not None:
        return override["reranker"]
    config = _load_active_config("reranker")
    if config:
        return RerankerProfileConfig(**config)
    return RerankerProfileConfig(
        enabled=settings.RERANK_ENABLED,
        model=settings.RERANK_MODEL,
        enabled_modes=[],
        enabled_corpora=[],
        min_candidate_count=0,
        max_candidate_count=None,
        latency_budget_ms=None,
        mmr_enabled=False,
        mmr_lambda=0.5,
    )


def get_effective_llm() -> LLMProfileConfig:
    override = _override_ctx.get()
    if override and override.get("llm") is not None:
        return override["llm"]
    config = _load_active_config("llm")
    if config:
        return LLMProfileConfig(**config)
    return LLMProfileConfig(
        provider=settings.LLM_PROVIDER,
        model=settings.LLM_MODEL,
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        timeout_s=settings.LLM_TIMEOUT_S,
        temperature=0.0,
        structured_output_mode="prompt_json_only" if settings.LLM_MODEL == "gpt-oss:20b-cloud" else "native_json",
        reasoning_effort="none" if settings.LLM_MODEL == "gpt-oss:20b-cloud" else None,
    )


def get_effective_retrieval() -> RetrievalProfileConfig:
    override = _override_ctx.get()
    if override and override.get("retrieval") is not None:
        return override["retrieval"]
    config = _load_active_config("retrieval")
    if config:
        return RetrievalProfileConfig(**config)
    return RetrievalProfileConfig(
        default_mode=settings.RETRIEVAL_MODE,
        top_k_initial=settings.TOP_K_INITIAL,
        hybrid_alpha=settings.HYBRID_ALPHA,
        vector_candidates=settings.VECTOR_CANDIDATES,
        keyword_candidates=settings.KEYWORD_CANDIDATES,
        fusion_method="linear",
        rrf_k=60,
    )


def get_active_profile_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for profile_type, getter in (
        ("embedding", get_effective_embedding),
        ("reranker", get_effective_reranker),
        ("llm", get_effective_llm),
        ("retrieval", get_effective_retrieval),
    ):
        try:
            profile = getter()
            snapshot[profile_type] = profile.model_dump()
        except Exception as exc:
            snapshot[profile_type] = {"error": str(exc)}
    return snapshot
