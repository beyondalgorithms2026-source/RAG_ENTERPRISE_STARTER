import re
import time
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import log_event, logger
from app.core_rag.query_router import QueryRouteDecision, route_query
from app.db.repo_search import search_chunks, search_chunks_keyword
from app.db.repo_sources import get_sources_by_ids
from app.embedding.embedder import embed_texts
from app.graph.graph_retriever import retrieve_graph_candidates
from app.graph.temporal import analyze_temporal_metadata
from app.ingestion.enrichment import ensure_lazy_full_mode_readiness


SearchMode = Literal["vector", "keyword", "hybrid", "graph_hybrid", "full"]
DEEP_LOOKUP_MODE = "deep_lookup"
DEEP_LOOKUP_VECTOR_CANDIDATES = 24
DEEP_LOOKUP_KEYWORD_CANDIDATES = 36
DEEP_LOOKUP_HYBRID_ALPHA = 0.2
_ANCHOR_STOPWORDS = {
    "about",
    "after",
    "before",
    "could",
    "does",
    "from",
    "have",
    "into",
    "itself",
    "just",
    "more",
    "than",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
}


class SearchFilters(BaseModel):
    source_type: Optional[str] = None
    source_id: Optional[int] = None
    source_part_id: Optional[int] = None
    locator_filter: Optional[str] = None


class SearchRequest(BaseModel):
    question: str
    k: int = Field(default=10, le=50, description="Number of results to return, max 50")
    filters: Optional[SearchFilters] = None
    mode: Optional[SearchMode] = Field(default=None)
    debug: bool = False


class SearchResultItem(BaseModel):
    chunk_id: int
    source_id: int
    source_part_id: Optional[int] = None
    file_name: str
    source_type: str
    heading: str
    locator: Optional[str] = None
    snippet: str
    score: float
    distance: Optional[float] = None
    rerank_score: Optional[float] = None
    vector_score: Optional[float] = None
    keyword_score: Optional[float] = None
    combined_score: Optional[float] = None
    rank_score: Optional[float] = None


class SearchResponse(BaseModel):
    results: List[SearchResultItem]
    latency_ms: int
    mode: str


class DeepLookupRequest(BaseModel):
    question: str
    source_ids: List[int]
    k: int = Field(default=12, le=20, description="Number of deep lookup results to return, max 20")
    debug: bool = False


class DeepLookupResponse(BaseModel):
    results: List[SearchResultItem]
    latency_ms: int
    mode: Literal["deep_lookup"]
    scoped_source_ids: List[int]
    strategy: str


def _result_sort_key(item: Dict) -> tuple:
    combined_score = item.get("combined_score")
    return (
        -(combined_score if combined_score is not None else 0.0),
        item["distance"] if item.get("distance") is not None else float("inf"),
        item.get("chunk_index", 0),
    )


def _tokenize_text(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9]+", text.lower())


def _extract_query_anchors(question: str) -> List[str]:
    anchors: List[str] = []
    seen: set[str] = set()
    for token in _tokenize_text(question):
        if token in seen or token in _ANCHOR_STOPWORDS:
            continue
        if len(token) < 4 and not any(char.isdigit() for char in token):
            continue
        seen.add(token)
        anchors.append(token)
    return anchors[:8]


def _apply_anchor_cooccurrence_boost(*, question: str, raw_results: List[Dict]) -> List[Dict]:
    anchors = _extract_query_anchors(question)
    if not anchors:
        return raw_results

    adjusted: List[Dict] = []
    for item in raw_results:
        updated = dict(item)
        haystack = f"{item.get('heading', '')} {item.get('snippet', '')}".lower()
        matched = [anchor for anchor in anchors if anchor in haystack]
        anchor_score = min(0.18, (len(matched) * 0.03) + (max(len(matched) - 1, 0) * 0.02))
        updated["anchor_score"] = round(anchor_score, 4)
        updated["combined_score"] = _blend_score(updated.get("combined_score", 0.0), anchor_score, 1.0)
        adjusted.append(updated)

    adjusted.sort(key=_result_sort_key)
    return adjusted


def merge_hybrid_results(
    vector_results: List[Dict],
    keyword_results: List[Dict],
    k: int,
    alpha: float = 0.65,
) -> List[Dict]:
    merged = {}

    for result in vector_results:
        chunk_id = result["chunk_id"]
        distance = result["distance"] if result["distance"] is not None else 1.0
        vector_score = max(0.0, 1.0 - distance)
        merged[chunk_id] = {
            "chunk_id": chunk_id,
            "source_id": result["source_id"],
            "source_part_id": result.get("source_part_id"),
            "file_name": result["file_name"],
            "source_type": result["source_type"],
            "heading": result["heading"],
            "locator": result.get("locator"),
            "snippet": result["snippet"],
            "distance": distance,
            "chunk_index": result["chunk_index"],
            "vector_score": vector_score,
            "keyword_score": 0.0,
            "rank_score": 0.0,
        }

    max_rank = max((result["rank_score"] for result in keyword_results), default=0.0)

    for result in keyword_results:
        chunk_id = result["chunk_id"]
        keyword_score = result["rank_score"] / max_rank if max_rank > 0 else 0.0
        if chunk_id in merged:
            merged[chunk_id]["keyword_score"] = keyword_score
            merged[chunk_id]["rank_score"] = result["rank_score"]
        else:
            merged[chunk_id] = {
                "chunk_id": chunk_id,
                "source_id": result["source_id"],
                "source_part_id": result.get("source_part_id"),
                "file_name": result["file_name"],
                "source_type": result["source_type"],
                "heading": result["heading"],
                "locator": result.get("locator"),
                "snippet": result["snippet"],
                "distance": None,
                "chunk_index": result["chunk_index"],
                "vector_score": 0.0,
                "keyword_score": keyword_score,
                "rank_score": result["rank_score"],
            }

    final_results = []
    for result in merged.values():
        result["combined_score"] = alpha * result["vector_score"] + (1.0 - alpha) * result["keyword_score"]
        final_results.append(result)

    final_results.sort(
        key=_result_sort_key
    )
    return final_results[:k]


def _blend_score(base_score: float, additive_score: float, weight: float) -> float:
    return base_score + max(0.0, additive_score) * weight


def _integrate_graph_candidates(
    *,
    baseline_results: List[Dict],
    graph_candidates: List[Dict],
    k: int,
) -> List[Dict]:
    merged = {item["chunk_id"]: dict(item) for item in baseline_results}

    for item in merged.values():
        item["graph_score"] = 0.0

    for candidate in graph_candidates:
        chunk_id = candidate["chunk_id"]
        graph_score = float(candidate.get("graph_score") or 0.0)
        if chunk_id in merged:
            merged[chunk_id]["graph_score"] = max(merged[chunk_id].get("graph_score", 0.0), graph_score)
            merged[chunk_id]["combined_score"] = _blend_score(
                merged[chunk_id].get("combined_score", 0.0),
                graph_score,
                0.35,
            )
            continue

        supplemental = dict(candidate)
        supplemental.setdefault("source_part_id", None)
        supplemental.setdefault("locator", None)
        supplemental.setdefault("snippet", "")
        supplemental.setdefault("distance", None)
        supplemental.setdefault("vector_score", 0.0)
        supplemental.setdefault("keyword_score", 0.0)
        supplemental.setdefault("rank_score", 0.0)
        supplemental["graph_score"] = graph_score
        supplemental["combined_score"] = graph_score * 0.2
        merged[chunk_id] = supplemental

    results = list(merged.values())
    results.sort(key=_result_sort_key)
    return results[:k]


def _extract_temporal_query_signals(question: str) -> Dict[str, set[str]]:
    analysis = analyze_temporal_metadata(text=question)
    normalized_dates = {
        value
        for value in analysis.metadata.get("normalized_dates", [])
        if isinstance(value, str) and value
    }
    years = {value[:4] for value in normalized_dates if len(value) >= 4}
    version_values = {
        str(item.get("value"))
        for item in analysis.metadata.get("document_version_refs", [])
        if item.get("value")
    }
    return {
        "normalized_dates": normalized_dates,
        "years": years,
        "versions": version_values,
    }


def _apply_temporal_signals(*, question: str, baseline_results: List[Dict], k: int) -> List[Dict]:
    if not (settings.ENABLE_TEMPORAL or settings.EXTRACT_TEMPORAL_METADATA or settings.TEMPORAL_RERANK_ENABLED):
        return baseline_results[:k]

    query_signals = _extract_temporal_query_signals(question)
    if not any(query_signals.values()):
        return baseline_results[:k]

    source_rows = get_sources_by_ids(sorted({item["source_id"] for item in baseline_results}))
    adjusted: List[Dict] = []
    for item in baseline_results:
        updated = dict(item)
        updated["temporal_score"] = 0.0
        source = source_rows.get(item["source_id"])
        temporal_metadata = dict((source.source_metadata_json or {}).get("temporal") or {}) if source else {}
        if temporal_metadata.get("fallback_reason"):
            adjusted.append(updated)
            continue

        temporal_score = 0.0
        date_bounds = temporal_metadata.get("date_bounds") or {}
        effective_window = temporal_metadata.get("effective_window") or {}
        version_refs = temporal_metadata.get("document_version_refs") or []

        bound_values = {
            str(value)
            for value in [date_bounds.get("earliest"), date_bounds.get("latest"), effective_window.get("start"), effective_window.get("end")]
            if value
        }
        bound_years = {value[:4] for value in bound_values if len(value) >= 4}
        if query_signals["normalized_dates"] & bound_values:
            temporal_score = max(temporal_score, 0.12)
        elif query_signals["years"] & bound_years:
            temporal_score = max(temporal_score, 0.08)

        source_versions = {str(item.get("value")) for item in version_refs if item.get("value")}
        if query_signals["versions"] & source_versions:
            temporal_score = max(temporal_score, 0.1)

        if temporal_score > 0:
            updated["combined_score"] = _blend_score(updated.get("combined_score", 0.0), temporal_score, 0.2)
            updated["temporal_score"] = temporal_score
        adjusted.append(updated)

    adjusted.sort(key=_result_sort_key)
    return adjusted[:k]


def _default_mode() -> str:
    return getattr(settings, "RETRIEVAL_MODE", None) or "hybrid"


def _extract_request_filters(request: SearchRequest) -> tuple[Optional[str], Optional[int], Optional[int], Optional[str]]:
    if not request.filters:
        return None, None, None, None
    return (
        request.filters.source_type,
        request.filters.source_id,
        request.filters.source_part_id,
        request.filters.locator_filter,
    )


def _resolve_mode(request: SearchRequest) -> tuple[str, QueryRouteDecision]:
    source_id = request.filters.source_id if request.filters else None
    default_mode = _default_mode()
    decision = route_query(
        question=request.question,
        explicit_mode=request.mode,
        default_mode=default_mode,
        source_id=source_id,
    )
    return decision.selected_mode, decision


def _run_vector_mode(*, request: SearchRequest, source_type: Optional[str], source_id: Optional[int], source_part_id: Optional[int], locator_filter: Optional[str]) -> List[Dict]:
    query_vector = embed_texts([request.question])[0]
    effective_k = settings.TOP_K_INITIAL if settings.RERANK_ENABLED else request.k
    raw_results = search_chunks(
        query_vector=query_vector,
        k=effective_k,
        source_type=source_type,
        source_id=source_id,
        source_part_id=source_part_id,
        locator_filter=locator_filter,
    )
    for result in raw_results:
        result["vector_score"] = max(0.0, 1.0 - (result["distance"] or 1.0))
        result["keyword_score"] = None
        result["combined_score"] = None
        result["rank_score"] = None
    return raw_results


def _run_keyword_mode(*, request: SearchRequest, source_type: Optional[str], source_id: Optional[int], source_part_id: Optional[int], locator_filter: Optional[str]) -> List[Dict]:
    effective_k = settings.TOP_K_INITIAL if settings.RERANK_ENABLED else request.k
    raw_results = search_chunks_keyword(
        query_text=request.question,
        k=effective_k,
        source_type=source_type,
        source_id=source_id,
        source_part_id=source_part_id,
        locator_filter=locator_filter,
    )
    max_rank = max((result["rank_score"] for result in raw_results), default=0.0)
    for result in raw_results:
        result["keyword_score"] = result["rank_score"] / max_rank if max_rank > 0 else 0.0
        result["vector_score"] = None
        result["combined_score"] = None
    return raw_results


def _run_hybrid_baseline(*, request: SearchRequest, source_type: Optional[str], source_id: Optional[int], source_part_id: Optional[int], locator_filter: Optional[str]) -> tuple[List[Dict], int]:
    query_vector = embed_texts([request.question])[0]
    effective_k = settings.TOP_K_INITIAL if settings.RERANK_ENABLED else request.k
    vector_results = search_chunks(
        query_vector=query_vector,
        k=settings.VECTOR_CANDIDATES,
        source_type=source_type,
        source_id=source_id,
        source_part_id=source_part_id,
        locator_filter=locator_filter,
    )
    keyword_results = search_chunks_keyword(
        query_text=request.question,
        k=settings.KEYWORD_CANDIDATES,
        source_type=source_type,
        source_id=source_id,
        source_part_id=source_part_id,
        locator_filter=locator_filter,
    )
    raw_results = merge_hybrid_results(
        vector_results=vector_results,
        keyword_results=keyword_results,
        k=effective_k,
        alpha=settings.HYBRID_ALPHA,
    )
    return raw_results, effective_k


def _apply_graph_and_temporal_layers(*, request: SearchRequest, resolved_mode: str, source_id: Optional[int], raw_results: List[Dict], effective_k: int) -> tuple[List[Dict], str]:
    response_mode = "hybrid"
    if resolved_mode not in {"graph_hybrid", "full"}:
        return raw_results, response_mode

    graph_result = retrieve_graph_candidates(
        question=request.question,
        source_id=source_id,
        baseline_candidates=raw_results,
    )
    if graph_result.enabled and graph_result.candidates:
        raw_results = _integrate_graph_candidates(
            baseline_results=raw_results,
            graph_candidates=graph_result.candidates,
            k=effective_k,
        )
        response_mode = resolved_mode
        log_event(
            "search.graph_applied",
            source_id=source_id,
            stage="search",
            status="completed",
            requested_mode=resolved_mode,
            resolved_mode=response_mode,
            reason=graph_result.reason,
        )
    elif resolved_mode == "graph_hybrid":
        log_event(
            "search.graph_fallback",
            source_id=source_id,
            stage="search",
            status="fallback",
            requested_mode=resolved_mode,
            resolved_mode=response_mode,
            reason=graph_result.reason,
        )

    if resolved_mode == "full":
        raw_results = _apply_temporal_signals(question=request.question, baseline_results=raw_results, k=effective_k)
        if graph_result.enabled and graph_result.candidates:
            response_mode = "full"
        elif any(item.get("temporal_score", 0.0) > 0 for item in raw_results):
            response_mode = "full"

    return raw_results, response_mode


def _materialize_search_results(*, raw_results: List[Dict], resolved_mode: str, debug: bool) -> List[SearchResultItem]:
    results = []
    for result in raw_results:
        if resolved_mode == "vector":
            score = max(0.0, 1.0 - (result["distance"] or 1.0))
        elif resolved_mode == "keyword":
            score = result.get("keyword_score", 0.0)
        else:
            score = result.get("combined_score", 0.0)

        item = SearchResultItem(
            chunk_id=result["chunk_id"],
            source_id=result["source_id"],
            source_part_id=result.get("source_part_id"),
            file_name=result["file_name"],
            source_type=result["source_type"],
            heading=result["heading"],
            locator=result.get("locator"),
            snippet=result["snippet"],
            score=round(score, 4),
            distance=round(result["distance"], 4) if result.get("distance") is not None else None,
            rerank_score=round(result["rerank_score"], 4) if "rerank_score" in result else None,
        )
        if debug:
            item.vector_score = round(result["vector_score"], 4) if result.get("vector_score") is not None else None
            item.keyword_score = round(result["keyword_score"], 4) if result.get("keyword_score") is not None else None
            item.combined_score = round(result["combined_score"], 4) if result.get("combined_score") is not None else None
            item.rank_score = round(result["rank_score"], 4) if result.get("rank_score") is not None else None
        results.append(item)
    return results


def perform_search(request: SearchRequest) -> SearchResponse:
    start_time = time.time()
    resolved_mode, route_decision = _resolve_mode(request)

    source_type, source_id, source_part_id, locator_filter = _extract_request_filters(request)

    log_event(
        "search.started",
        source_id=source_id,
        stage="search",
        status="processing",
        requested_mode=request.mode,
        resolved_mode=resolved_mode,
        reason=route_decision.reason,
    )

    lazy_result = None
    if resolved_mode == "full":
        lazy_result = ensure_lazy_full_mode_readiness(source_id=source_id)
        log_event(
            "search.full_readiness",
            source_id=lazy_result.source_id,
            stage="search",
            status="completed",
            requested_mode="full",
            reason=lazy_result.reason,
        )

    try:
        if resolved_mode == "vector":
            raw_results = _run_vector_mode(
                request=request,
                source_type=source_type,
                source_id=source_id,
                source_part_id=source_part_id,
                locator_filter=locator_filter,
            )
        elif resolved_mode == "keyword":
            raw_results = _run_keyword_mode(
                request=request,
                source_type=source_type,
                source_id=source_id,
                source_part_id=source_part_id,
                locator_filter=locator_filter,
            )
        else:
            raw_results, effective_k = _run_hybrid_baseline(
                request=request,
                source_type=source_type,
                source_id=source_id,
                source_part_id=source_part_id,
                locator_filter=locator_filter,
            )
            raw_results, resolved_mode = _apply_graph_and_temporal_layers(
                request=request,
                resolved_mode=resolved_mode,
                source_id=source_id,
                raw_results=raw_results,
                effective_k=effective_k,
            )
    except Exception as exc:
        log_event(
            "search.failed",
            level=40,
            source_id=source_id,
            stage="search",
            status="failed",
            requested_mode=request.mode,
            resolved_mode=resolved_mode,
            reason=str(exc),
        )
        return SearchResponse(results=[], latency_ms=int((time.time() - start_time) * 1000), mode=resolved_mode)

    if settings.RERANK_ENABLED and raw_results:
        from app.core_rag.reranker import rerank

        logger.info(f"Reranking {len(raw_results)} candidates down to {request.k}")
        raw_results = rerank(request.question, raw_results, request.k)

    results = _materialize_search_results(raw_results=raw_results, resolved_mode=resolved_mode, debug=request.debug)
    log_event(
        "search.completed",
        source_id=source_id,
        stage="search",
        status="completed",
        requested_mode=request.mode,
        resolved_mode=resolved_mode,
        reason=f"results={len(results)}",
    )

    return SearchResponse(
        results=results,
        latency_ms=int((time.time() - start_time) * 1000),
        mode=resolved_mode,
    )


def perform_deep_lookup(request: DeepLookupRequest) -> DeepLookupResponse:
    start_time = time.time()
    scoped_source_ids = list(request.source_ids)
    effective_k = max(request.k * 3, DEEP_LOOKUP_VECTOR_CANDIDATES)
    log_event(
        "deep_lookup.started",
        stage="deep_lookup",
        status="processing",
        reason=f"source_ids={scoped_source_ids}",
    )

    try:
        query_vector = embed_texts([request.question])[0]
        vector_results = search_chunks(
            query_vector=query_vector,
            k=max(request.k * 2, DEEP_LOOKUP_VECTOR_CANDIDATES),
            source_ids=scoped_source_ids,
        )
        keyword_results = search_chunks_keyword(
            query_text=request.question,
            k=max(request.k * 3, DEEP_LOOKUP_KEYWORD_CANDIDATES),
            source_ids=scoped_source_ids,
        )
        raw_results = merge_hybrid_results(
            vector_results=vector_results,
            keyword_results=keyword_results,
            k=effective_k,
            alpha=DEEP_LOOKUP_HYBRID_ALPHA,
        )
        raw_results = _apply_anchor_cooccurrence_boost(question=request.question, raw_results=raw_results)
        results = _materialize_search_results(
            raw_results=raw_results[: request.k],
            resolved_mode=DEEP_LOOKUP_MODE,
            debug=request.debug,
        )
    except Exception as exc:
        log_event(
            "deep_lookup.failed",
            level=40,
            stage="deep_lookup",
            status="failed",
            reason=str(exc),
        )
        return DeepLookupResponse(
            results=[],
            latency_ms=int((time.time() - start_time) * 1000),
            mode=DEEP_LOOKUP_MODE,
            scoped_source_ids=scoped_source_ids,
            strategy="selected_source_keyword_vector_anchor_boost",
        )

    log_event(
        "deep_lookup.completed",
        stage="deep_lookup",
        status="completed",
        reason=f"results={len(results)}",
    )
    return DeepLookupResponse(
        results=results,
        latency_ms=int((time.time() - start_time) * 1000),
        mode=DEEP_LOOKUP_MODE,
        scoped_source_ids=scoped_source_ids,
        strategy="selected_source_keyword_vector_anchor_boost",
    )
