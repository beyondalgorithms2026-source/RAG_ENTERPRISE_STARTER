from __future__ import annotations

from contextlib import ExitStack, contextmanager
from typing import Any, Iterator, Optional

from app.core_rag.answering import AskRequest, AskResponse, perform_ask
from app.db.repo_tuning_configs import build_resolved_profile_bundle
from app.profiles.models import EmbeddingProfileConfig, LLMProfileConfig, RerankerProfileConfig, RetrievalProfileConfig
from app.profiles.resolver import (
    get_effective_embedding,
    get_effective_llm,
    get_effective_reranker,
    get_effective_retrieval,
)


@contextmanager
def _temporary_value(target: Any, attr_name: str, value: Any) -> Iterator[None]:
    original = getattr(target, attr_name)
    setattr(target, attr_name, value)
    try:
        yield
    finally:
        setattr(target, attr_name, original)


@contextmanager
def _temporary_llm_profile(profile: Optional[LLMProfileConfig]) -> Iterator[None]:
    if profile is None:
        yield
        return

    import app.profiles.resolver as resolver_module

    with _temporary_value(resolver_module, "get_effective_llm", lambda: profile):
        yield


@contextmanager
def _temporary_embedding_profile(profile: Optional[EmbeddingProfileConfig]) -> Iterator[None]:
    if profile is None:
        yield
        return

    import app.profiles.resolver as resolver_module

    with _temporary_value(resolver_module, "get_effective_embedding", lambda: profile):
        yield


@contextmanager
def _temporary_retrieval_profile(profile: Optional[RetrievalProfileConfig]) -> Iterator[None]:
    if profile is None:
        yield
        return

    import app.core_rag.retrieval as retrieval_module
    import app.profiles.resolver as resolver_module

    with _temporary_value(resolver_module, "get_effective_retrieval", lambda: profile):
        with _temporary_value(retrieval_module, "get_effective_retrieval", lambda: profile):
            yield


@contextmanager
def _temporary_reranker_profile(profile: Optional[RerankerProfileConfig]) -> Iterator[None]:
    if profile is None:
        yield
        return

    import app.core_rag.retrieval as retrieval_module
    import app.profiles.resolver as resolver_module

    with _temporary_value(resolver_module, "get_effective_reranker", lambda: profile):
        with _temporary_value(retrieval_module, "get_effective_reranker", lambda: profile):
            yield


@contextmanager
def _temporary_chunk_cap(chunk_size_cap_chars: Optional[int]) -> Iterator[None]:
    if not chunk_size_cap_chars:
        yield
        return

    import app.core_rag.answering as answering_module

    with _temporary_value(answering_module, "MAX_CHUNK_CHARS", int(chunk_size_cap_chars)):
        yield


def _effective_selected_profiles(*, live_selected: dict[str, str], selected_profiles: Optional[dict[str, str]] = None) -> dict[str, str]:
    combined = dict(live_selected)
    for key, value in (selected_profiles or {}).items():
        token = str(value or "").strip()
        if token:
            combined[str(key)] = token
    return combined


def _profile_models_from_selected(selected_profiles: dict[str, str]) -> dict[str, Any]:
    resolved = build_resolved_profile_bundle(selected_profiles)
    return {
        "embedding": EmbeddingProfileConfig(**(resolved["embedding"]["config"] or {})),
        "llm": LLMProfileConfig(**(resolved["llm"]["config"] or {})),
        "reranker": RerankerProfileConfig(**(resolved["reranker"]["config"] or {})),
        "retrieval": RetrievalProfileConfig(**(resolved["retrieval"]["config"] or {})),
        "resolved": resolved,
    }


def _profile_models_with_retrieval_override(selected_profiles: dict[str, str], retrieval_override_config: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    resolved = build_resolved_profile_bundle(selected_profiles, retrieval_override_config)
    return {
        "embedding": EmbeddingProfileConfig(**(resolved["embedding"]["config"] or {})),
        "llm": LLMProfileConfig(**(resolved["llm"]["config"] or {})),
        "reranker": RerankerProfileConfig(**(resolved["reranker"]["config"] or {})),
        "retrieval": RetrievalProfileConfig(**(resolved["retrieval"]["config"] or {})),
        "resolved": resolved,
    }


def _retrieval_summary(response: AskResponse) -> dict[str, Any]:
    trace = ((response.debug_info or {}).get("retrieval_trace") or {}) if response.debug_info else {}
    return {
        "resolved_mode": response.mode,
        "retrieval_path": trace.get("retrieval_path_used"),
        "candidate_counts": trace.get("candidate_counts") or {},
        "latency_ms": trace.get("latency_ms") or {},
        "rerank_policy": trace.get("rerank_policy") or {},
        "route_reason": trace.get("route_reason"),
        "route_class": trace.get("route_class"),
        "preferred_mode": trace.get("preferred_mode"),
        "fallback_reason": trace.get("fallback_reason"),
        "accessed_doc_ids": ((trace.get("acl") or {}).get("accessed_doc_ids") or []),
        "observed_query_transform": trace.get("query_transform") or {},
    }


def _transform_summary(retrieval_config: RetrievalProfileConfig) -> dict[str, Any]:
    strategy: list[str] = []
    if retrieval_config.rewrite_enabled:
        strategy.append("rewrite")
    if retrieval_config.expansion_enabled:
        strategy.append("expansion")
    if retrieval_config.hyde_enabled:
        strategy.append("hyde")
    return {
        "enabled": retrieval_config.query_transform_enabled,
        "rewrite_enabled": retrieval_config.rewrite_enabled,
        "expansion_enabled": retrieval_config.expansion_enabled,
        "hyde_enabled": retrieval_config.hyde_enabled,
        "transform_timeout_ms": retrieval_config.transform_timeout_ms,
        "transform_max_variants": retrieval_config.transform_max_variants,
        "multi_query_enabled": retrieval_config.multi_query_enabled,
        "strategy": strategy,
    }


def _run_payload(
    *,
    label: str,
    response: AskResponse,
    selected_profiles: dict[str, str],
    llm_config: LLMProfileConfig,
    retrieval_config: RetrievalProfileConfig,
    reranker_config: RerankerProfileConfig,
    chunk_size_cap_chars: Optional[int],
) -> dict[str, Any]:
    retrieval_summary = _retrieval_summary(response)
    citations = [item.model_dump() for item in response.citations]
    answer_generation_path = str((response.debug_info or {}).get("answer_generation_path") or "unknown")
    return {
        "label": label,
        "status": "completed",
        "answer": response.answer,
        "citations": citations,
        "citation_count": len(citations),
        "used_chunks_count": response.used_chunks_count,
        "latency_ms": response.latency_ms,
        "mode": response.mode,
        "selected_profiles": selected_profiles,
        "generation_summary": {
            "provider": llm_config.provider,
            "model": llm_config.model,
            "temperature": llm_config.temperature,
            "top_p": llm_config.top_p,
            "max_tokens": llm_config.max_tokens,
            "answer_generation_path": answer_generation_path,
        },
        "retrieval_summary": {
            **retrieval_summary,
            "default_mode": retrieval_config.default_mode,
            "hybrid_alpha": retrieval_config.hybrid_alpha,
            "top_k_initial": retrieval_config.top_k_initial,
            "answer_time_chunk_cap_chars": chunk_size_cap_chars,
            "answer_generation_path": answer_generation_path,
            "transform_summary": _transform_summary(retrieval_config),
        },
        "rerank_summary": {
            "enabled": reranker_config.enabled,
            "model": reranker_config.model,
            "top_n": reranker_config.top_n,
            "score_threshold": reranker_config.score_threshold,
            "policy": retrieval_summary.get("rerank_policy") or {},
        },
    }


def _run_ask(
    *,
    question: str,
    selected_profiles: dict[str, str],
    llm_config: LLMProfileConfig,
    retrieval_config: RetrievalProfileConfig,
    reranker_config: RerankerProfileConfig,
    embedding_config: Optional[EmbeddingProfileConfig],
    temperature: Optional[float],
    top_p: Optional[float],
    chunk_size_cap_chars: Optional[int],
    k_retrieval_count: Optional[int],
) -> dict[str, Any]:
    candidate_llm = llm_config.model_copy(
        update={
            "temperature": (
                0.0
                if llm_config.structured_output_mode == "prompt_json_only"
                else float(temperature if temperature is not None else llm_config.temperature)
            ),
            "top_p": float(top_p if top_p is not None else llm_config.top_p),
        }
    )
    with ExitStack() as stack:
        stack.enter_context(_temporary_llm_profile(candidate_llm))
        stack.enter_context(_temporary_retrieval_profile(retrieval_config))
        stack.enter_context(_temporary_reranker_profile(reranker_config))
        stack.enter_context(_temporary_embedding_profile(embedding_config))
        stack.enter_context(_temporary_chunk_cap(chunk_size_cap_chars))
        response = perform_ask(
            AskRequest(
                question=question,
                k_chunks=int(k_retrieval_count or 6),
                mode=retrieval_config.default_mode,
            )
        )
    return _run_payload(
        label="sandbox",
        response=response,
        selected_profiles=selected_profiles,
        llm_config=candidate_llm,
        retrieval_config=retrieval_config,
        reranker_config=reranker_config,
        chunk_size_cap_chars=chunk_size_cap_chars,
    )


def run_sandbox_compare(
    *,
    question: str,
    live_selected_profiles: dict[str, str],
    selected_profiles: Optional[dict[str, str]] = None,
    retrieval_override_config: Optional[dict[str, Any]] = None,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    chunk_size_cap_chars: Optional[int] = None,
    k_retrieval_count: Optional[int] = None,
) -> dict[str, Any]:
    live_selected = _effective_selected_profiles(live_selected=live_selected_profiles)
    candidate_selected = _effective_selected_profiles(live_selected=live_selected_profiles, selected_profiles=selected_profiles)

    live_models = _profile_models_from_selected(live_selected)
    candidate_models = _profile_models_with_retrieval_override(candidate_selected, retrieval_override_config)

    live_run = _run_ask(
        question=question,
        selected_profiles=live_selected,
        llm_config=live_models["llm"],
        retrieval_config=live_models["retrieval"],
        reranker_config=live_models["reranker"],
        embedding_config=live_models["embedding"],
        temperature=live_models["llm"].temperature,
        top_p=live_models["llm"].top_p,
        chunk_size_cap_chars=None,
        k_retrieval_count=6,
    )
    live_run["label"] = "live"

    warnings: list[dict[str, Any]] = []
    preconditions: list[dict[str, Any]] = []
    changed_profile_types = [
        profile_type
        for profile_type in ("llm", "embedding", "reranker", "retrieval")
        if candidate_selected.get(profile_type) != live_selected.get(profile_type)
    ]
    if retrieval_override_config and "retrieval" not in changed_profile_types:
        changed_profile_types.append("retrieval")

    candidate_run: Optional[dict[str, Any]]
    if candidate_selected.get("embedding") != live_selected.get("embedding"):
        warning = {
            "code": "embedding_scope_later_enhancement",
            "message": "Embedding swaps are visible for planning, but sandbox compare is deferred to a later scoped-index workflow.",
            "detail": "Future enhancement: evaluate alternate embeddings at file-, corpus-, or folder-level shadow scope to avoid mixed embedding spaces in the same indexed dataset.",
        }
        warnings.append(warning)
        preconditions.append(warning)
        candidate_run = {
            "label": "sandbox",
            "status": "blocked_embedding_scope",
            "answer": None,
            "citations": [],
            "citation_count": 0,
            "used_chunks_count": 0,
            "latency_ms": 0,
            "mode": candidate_models["retrieval"].default_mode,
            "selected_profiles": candidate_selected,
            "generation_summary": {
                "provider": candidate_models["llm"].provider,
                "model": candidate_models["llm"].model,
                "temperature": float(temperature if temperature is not None else candidate_models["llm"].temperature),
                "top_p": float(top_p if top_p is not None else candidate_models["llm"].top_p),
                "max_tokens": candidate_models["llm"].max_tokens,
            },
            "retrieval_summary": {
                "default_mode": candidate_models["retrieval"].default_mode,
                "answer_time_chunk_cap_chars": chunk_size_cap_chars,
                "transform_summary": _transform_summary(candidate_models["retrieval"]),
            },
            "rerank_summary": {
                "enabled": candidate_models["reranker"].enabled,
                "model": candidate_models["reranker"].model,
            },
            "warning": warning,
        }
    else:
        candidate_run = _run_ask(
            question=question,
            selected_profiles=candidate_selected,
            llm_config=candidate_models["llm"],
            retrieval_config=candidate_models["retrieval"],
            reranker_config=candidate_models["reranker"],
            embedding_config=candidate_models["embedding"],
            temperature=temperature,
            top_p=top_p,
            chunk_size_cap_chars=chunk_size_cap_chars,
            k_retrieval_count=k_retrieval_count,
        )

    candidate_latency = candidate_run["latency_ms"] if candidate_run and candidate_run["status"] == "completed" else None
    candidate_citations = candidate_run["citation_count"] if candidate_run and candidate_run["status"] == "completed" else None
    candidate_chunks = candidate_run["used_chunks_count"] if candidate_run and candidate_run["status"] == "completed" else None

    return {
        "live_run": live_run,
        "candidate_run": candidate_run,
        "summary": {
            "changed_profile_types": changed_profile_types,
            "latency_delta_ms": candidate_latency - live_run["latency_ms"] if candidate_latency is not None else None,
            "citation_count_delta": candidate_citations - live_run["citation_count"] if candidate_citations is not None else None,
            "used_chunk_delta": candidate_chunks - live_run["used_chunks_count"] if candidate_chunks is not None else None,
            "live_retrieval_path": (live_run["retrieval_summary"] or {}).get("retrieval_path"),
            "candidate_retrieval_path": (candidate_run["retrieval_summary"] or {}).get("retrieval_path") if candidate_run else None,
            "live_mode": live_run["mode"],
            "candidate_mode": candidate_run["mode"] if candidate_run else None,
            "live_answer_path": ((live_run["retrieval_summary"] or {}).get("answer_generation_path")),
            "candidate_answer_path": ((candidate_run["retrieval_summary"] or {}).get("answer_generation_path")) if candidate_run else None,
            "live_transform_summary": (live_run["retrieval_summary"] or {}).get("transform_summary"),
            "candidate_transform_summary": (candidate_run["retrieval_summary"] or {}).get("transform_summary") if candidate_run else None,
        },
        "warnings": warnings,
        "preconditions": preconditions,
    }
