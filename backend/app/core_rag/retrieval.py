import re
import time
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import log_event, logger
from app.core_rag.query_router import QueryRouteDecision, route_query
from app.profiles.resolver import get_effective_reranker, get_effective_retrieval
from app.db.repo_chunks import fetch_neighbor_chunks, get_chunks_for_enrichment
from app.db.repo_search import fetch_chunks_by_ids, search_chunks, search_chunks_keyword
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
    deep_research: bool = False
    custom_query: Optional[str] = None
    anchor_terms: List[str] = Field(default_factory=list)
    exact_phrase_bias: Optional[str] = None
    expand_neighbors: bool = False
    force_rare_keyword_scan: bool = False


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
    debug_info: Optional[dict] = None


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


def _normalize_anchor_terms(anchor_terms: Optional[List[str]]) -> List[str]:
    anchors: List[str] = []
    seen: set[str] = set()
    for raw_value in anchor_terms or []:
        for token in _tokenize_text(str(raw_value or "")):
            if token in seen or token in _ANCHOR_STOPWORDS:
                continue
            if len(token) < 3 and not any(char.isdigit() for char in token):
                continue
            seen.add(token)
            anchors.append(token)
    return anchors[:12]


def _resolve_query_text(request: SearchRequest) -> str:
    custom_query = (request.custom_query or "").strip()
    if custom_query:
        return custom_query
    exact_phrase = (request.exact_phrase_bias or "").strip()
    if exact_phrase:
        return exact_phrase
    return request.question


def _combined_anchor_terms(request: SearchRequest, query_text: str) -> List[str]:
    anchors: List[str] = []
    seen: set[str] = set()
    for token in _extract_query_anchors(request.question) + _extract_query_anchors(query_text) + _normalize_anchor_terms(request.anchor_terms):
        if token in seen:
            continue
        seen.add(token)
        anchors.append(token)
    return anchors[:12]


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


def _apply_anchor_boost_with_terms(*, anchors: List[str], raw_results: List[Dict]) -> List[Dict]:
    if not anchors:
        return raw_results

    adjusted: List[Dict] = []
    for item in raw_results:
        updated = dict(item)
        haystack = f"{item.get('heading', '')} {item.get('snippet', '')}".lower()
        matched = [anchor for anchor in anchors if anchor in haystack]
        anchor_score = min(0.24, (len(matched) * 0.035) + (max(len(matched) - 1, 0) * 0.025))
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
    rp = get_effective_retrieval()
    rr = get_effective_reranker()
    query_text = _resolve_query_text(request)
    query_vector = embed_texts([query_text])[0]
    effective_k = rp.top_k_initial if rr.enabled else max(request.k, rp.vector_candidates)
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
        result["combined_score"] = result["vector_score"]
        result["rank_score"] = None
    anchors = _combined_anchor_terms(request, query_text)
    return _apply_anchor_boost_with_terms(anchors=anchors, raw_results=raw_results)


def _run_keyword_mode(*, request: SearchRequest, source_type: Optional[str], source_id: Optional[int], source_part_id: Optional[int], locator_filter: Optional[str]) -> List[Dict]:
    rp = get_effective_retrieval()
    rr = get_effective_reranker()
    effective_k = rp.top_k_initial if rr.enabled else max(request.k, rp.keyword_candidates)
    query_text = _resolve_query_text(request)
    raw_results = search_chunks_keyword(
        query_text=query_text,
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
        result["combined_score"] = result["keyword_score"]
    anchors = _combined_anchor_terms(request, query_text)
    return _apply_anchor_boost_with_terms(anchors=anchors, raw_results=raw_results)


def _run_hybrid_baseline(*, request: SearchRequest, source_type: Optional[str], source_id: Optional[int], source_part_id: Optional[int], locator_filter: Optional[str]) -> tuple[List[Dict], int]:
    rp = get_effective_retrieval()
    rr = get_effective_reranker()
    query_text = _resolve_query_text(request)
    query_vector = embed_texts([query_text])[0]
    effective_k = rp.top_k_initial if rr.enabled else request.k
    merge_k = max(effective_k, rp.vector_candidates, rp.keyword_candidates)
    vector_results = search_chunks(
        query_vector=query_vector,
        k=rp.vector_candidates,
        source_type=source_type,
        source_id=source_id,
        source_part_id=source_part_id,
        locator_filter=locator_filter,
    )
    keyword_results = search_chunks_keyword(
        query_text=query_text,
        k=rp.keyword_candidates,
        source_type=source_type,
        source_id=source_id,
        source_part_id=source_part_id,
        locator_filter=locator_filter,
    )
    raw_results = merge_hybrid_results(
        vector_results=vector_results,
        keyword_results=keyword_results,
        k=merge_k,
        alpha=rp.hybrid_alpha,
    )
    anchors = _combined_anchor_terms(request, query_text)
    raw_results = _apply_anchor_boost_with_terms(anchors=anchors, raw_results=raw_results)
    return raw_results, effective_k


def _expand_neighbor_context(*, raw_results: List[Dict], request: SearchRequest, k: int) -> List[Dict]:
    if not request.expand_neighbors or not raw_results:
        return raw_results

    top_chunk_ids = [item["chunk_id"] for item in raw_results[: min(len(raw_results), max(k, 4))]]
    neighbors = fetch_neighbor_chunks(top_chunk_ids, radius=1)
    if not neighbors:
        return raw_results

    existing_ids = {item["chunk_id"] for item in raw_results}
    anchors = _combined_anchor_terms(request, _resolve_query_text(request))
    expanded = list(raw_results)
    for neighbor in neighbors:
        if neighbor["id"] in existing_ids:
            continue
        snippet = neighbor["chunk_text"]
        haystack = f"{neighbor.get('heading', '')} {snippet}".lower()
        matched_count = sum(1 for anchor in anchors if anchor in haystack)
        bonus = 0.03 + (matched_count * 0.025)
        expanded.append(
            {
                "chunk_id": neighbor["id"],
                "source_id": neighbor["source_id"],
                "source_part_id": neighbor.get("source_part_id"),
                "file_name": "",
                "source_type": "",
                "heading": neighbor.get("heading", ""),
                "locator": str(neighbor.get("locator_json") or ""),
                "snippet": snippet,
                "distance": None,
                "chunk_index": neighbor["chunk_index"],
                "vector_score": 0.0,
                "keyword_score": 0.0,
                "rank_score": 0.0,
                "combined_score": bonus,
                "neighbor_expansion": True,
            }
        )
    source_rows = get_sources_by_ids(sorted({item["source_id"] for item in expanded if item.get("source_id")}))
    for item in expanded:
        if item.get("file_name") and item.get("source_type"):
            continue
        source = source_rows.get(item["source_id"])
        if source is None:
            continue
        item["file_name"] = source.file_name
        item["source_type"] = source.source_type
    expanded.sort(key=_result_sort_key)
    return expanded


def _integrate_supplemental_results(*, baseline_results: List[Dict], supplemental_results: List[Dict], k: int) -> List[Dict]:
    if not supplemental_results:
        return baseline_results[:k]

    merged = {item["chunk_id"]: dict(item) for item in baseline_results}
    for item in supplemental_results:
        chunk_id = item["chunk_id"]
        supplemental_score = float(item.get("combined_score") or 0.0)
        if chunk_id in merged:
            merged_item = merged[chunk_id]
            merged_item["anchor_window_score"] = max(float(merged_item.get("anchor_window_score") or 0.0), supplemental_score)
            merged_item["combined_score"] = _blend_score(float(merged_item.get("combined_score") or 0.0), supplemental_score, 1.0)
            continue
        merged[chunk_id] = dict(item)
        merged[chunk_id]["anchor_window_score"] = supplemental_score

    results = list(merged.values())
    results.sort(key=_result_sort_key)
    return results[:k]


def _build_anchor_window_candidates(
    *,
    request: SearchRequest,
    source_id: Optional[int],
    query_text: str,
    anchors: List[str],
    k: int,
) -> tuple[List[Dict], Dict]:
    trace = {
        "source_scoped_scan_used": False,
        "source_scoped_scan_reason": "source_scope_required",
        "selected_anchors": anchors,
        "anchor_frequency_by_source": {},
        "rare_anchor_candidates": [],
        "window_candidates_added": 0,
        "window_debug": [],
    }
    if source_id is None:
        return [], trace

    source_chunks = get_chunks_for_enrichment(source_id)
    if not source_chunks:
        trace["source_scoped_scan_reason"] = "no_chunks_for_source"
        return [], trace

    trace["source_scoped_scan_used"] = True
    trace["source_scoped_scan_reason"] = "ok"
    chunk_count = len(source_chunks)
    anchor_frequency: Dict[str, int] = {}
    tokenized_query_terms = set(_tokenize_text(query_text))
    causal_terms = {"because", "challenging", "dominated", "making", "hard", "difficult", "saturated", "rank"}

    for anchor in anchors:
        anchor_frequency[anchor] = sum(1 for chunk in source_chunks if anchor in str(chunk.get("chunk_text", "")).lower())

    trace["anchor_frequency_by_source"] = {str(source_id): anchor_frequency}
    rare_anchors = [
        anchor
        for anchor, hit_count in anchor_frequency.items()
        if hit_count > 0 and (hit_count <= 3 or hit_count < 10 or (chunk_count and (hit_count / chunk_count) <= 0.01))
    ]
    if not rare_anchors and request.force_rare_keyword_scan:
        rare_anchors = anchors[:2]
    trace["rare_anchor_candidates"] = rare_anchors
    if not rare_anchors:
        trace["source_scoped_scan_reason"] = "no_rare_anchors_detected"
        return [], trace

    chunk_by_index = {int(chunk["chunk_index"]): chunk for chunk in source_chunks}
    candidate_scores: Dict[int, float] = {}
    window_debug: List[Dict] = []

    for chunk in source_chunks:
        haystack = str(chunk.get("chunk_text", "")).lower()
        matched_anchors = [anchor for anchor in rare_anchors if anchor in haystack]
        if not matched_anchors:
            continue

        lexical_overlap = len(tokenized_query_terms & set(_tokenize_text(haystack)))
        causal_bonus = 0.05 if any(term in haystack for term in causal_terms) else 0.0
        base_score = min(0.36, 0.12 + (len(matched_anchors) * 0.04) + min(0.08, lexical_overlap * 0.01) + causal_bonus)
        chunk_id = int(chunk["id"])
        candidate_scores[chunk_id] = max(candidate_scores.get(chunk_id, 0.0), base_score)

        chunk_index = int(chunk["chunk_index"])
        neighbors_added = []
        if request.expand_neighbors:
            for offset, bonus in [(-1, 0.08), (1, 0.08)]:
                neighbor = chunk_by_index.get(chunk_index + offset)
                if neighbor is None:
                    continue
                neighbor_id = int(neighbor["id"])
                neighbor_score = min(0.24, base_score * 0.7 + bonus)
                candidate_scores[neighbor_id] = max(candidate_scores.get(neighbor_id, 0.0), neighbor_score)
                neighbors_added.append(neighbor_id)

        window_debug.append(
            {
                "chunk_id": chunk_id,
                "chunk_index": chunk_index,
                "matched_anchors": matched_anchors,
                "score": round(base_score, 4),
                "neighbors_added": neighbors_added,
            }
        )

    ranked_chunk_ids = [
        chunk_id
        for chunk_id, _score in sorted(candidate_scores.items(), key=lambda item: (-item[1], item[0]))[: max(k * 3, 12)]
    ]
    materialized = fetch_chunks_by_ids(ranked_chunk_ids)
    score_by_chunk_id = {chunk_id: score for chunk_id, score in candidate_scores.items()}
    supplemental_results: List[Dict] = []
    for item in materialized:
        supplemental_results.append(
            {
                **item,
                "distance": item.get("distance"),
                "vector_score": 0.0,
                "keyword_score": 0.0,
                "rank_score": 0.0,
                "combined_score": round(float(score_by_chunk_id.get(item["chunk_id"], 0.0)), 4),
                "anchor_window_candidate": True,
            }
        )

    trace["window_candidates_added"] = len(supplemental_results)
    trace["window_debug"] = window_debug[:8]
    return supplemental_results, trace


def _run_deep_research_mode(*, request: SearchRequest, source_type: Optional[str], source_id: Optional[int], source_part_id: Optional[int], locator_filter: Optional[str]) -> tuple[List[Dict], dict]:
    rp = get_effective_retrieval()
    query_text = _resolve_query_text(request)
    anchors = _combined_anchor_terms(request, query_text)
    vector_query = embed_texts([query_text])[0]
    vector_k = max(request.k * 4, rp.vector_candidates, rp.deep_research_vector_candidates)
    keyword_k = max(request.k * 5, rp.keyword_candidates, rp.deep_research_keyword_candidates)

    vector_results = search_chunks(
        query_vector=vector_query,
        k=vector_k,
        source_type=source_type,
        source_id=source_id,
        source_part_id=source_part_id,
        locator_filter=locator_filter,
    )
    keyword_results = search_chunks_keyword(
        query_text=query_text,
        k=keyword_k,
        source_type=source_type,
        source_id=source_id,
        source_part_id=source_part_id,
        locator_filter=locator_filter,
    )

    supplemental_keyword_results: List[Dict] = []
    if request.force_rare_keyword_scan or anchors:
        anchor_query = " ".join(anchors[:8]) if anchors else query_text
        supplemental_keyword_results = search_chunks_keyword(
            query_text=anchor_query,
            k=keyword_k,
            source_type=source_type,
            source_id=source_id,
            source_part_id=source_part_id,
            locator_filter=locator_filter,
        )

    merged_keyword_results = keyword_results
    if supplemental_keyword_results:
        ranked = {item["chunk_id"]: dict(item) for item in keyword_results}
        for item in supplemental_keyword_results:
            ranked.setdefault(item["chunk_id"], dict(item))
            ranked[item["chunk_id"]]["rank_score"] = max(
                float(ranked[item["chunk_id"]].get("rank_score") or 0.0),
                float(item.get("rank_score") or 0.0),
            )
        merged_keyword_results = list(ranked.values())
        merged_keyword_results.sort(key=lambda item: (-float(item.get("rank_score") or 0.0), item.get("chunk_index", 0)))

    rr = get_effective_reranker()
    effective_k = max(request.k * 4, rp.top_k_initial if rr.enabled else request.k)
    merged = merge_hybrid_results(
        vector_results=vector_results,
        keyword_results=merged_keyword_results,
        k=effective_k,
        alpha=rp.deep_research_alpha,
    )
    merged = _apply_anchor_boost_with_terms(anchors=anchors, raw_results=merged)
    anchor_window_results, anchor_window_trace = _build_anchor_window_candidates(
        request=request,
        source_id=source_id,
        query_text=query_text,
        anchors=anchors,
        k=request.k,
    )
    merged = _integrate_supplemental_results(
        baseline_results=merged,
        supplemental_results=anchor_window_results,
        k=max(effective_k, request.k * 4),
    )
    merged = _expand_neighbor_context(raw_results=merged, request=request, k=request.k * 2)

    return merged, {
        "deep_research_used": True,
        "effective_query": query_text,
        "anchor_terms_used": anchors,
        "force_rare_keyword_scan": request.force_rare_keyword_scan,
        "neighbor_expansion_used": request.expand_neighbors,
        "vector_candidates": len(vector_results),
        "keyword_candidates": len(keyword_results),
        "supplemental_keyword_candidates": len(supplemental_keyword_results),
        **anchor_window_trace,
    }


def _apply_graph_and_temporal_layers(*, request: SearchRequest, resolved_mode: str, source_id: Optional[int], raw_results: List[Dict], effective_k: int) -> tuple[List[Dict], str, dict]:
    response_mode = "hybrid"
    trace = {
        "graph_used": False,
        "graph_reason": "not_requested",
        "temporal_used": False,
        "temporal_reason": "not_requested",
    }
    if resolved_mode not in {"graph_hybrid", "full"}:
        return raw_results, response_mode, trace

    graph_result = retrieve_graph_candidates(
        question=request.question,
        source_id=source_id,
        baseline_candidates=raw_results,
    )
    trace["graph_reason"] = graph_result.reason
    if graph_result.enabled and graph_result.candidates:
        raw_results = _integrate_graph_candidates(
            baseline_results=raw_results,
            graph_candidates=graph_result.candidates,
            k=effective_k,
        )
        response_mode = resolved_mode
        trace["graph_used"] = True
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
            trace["temporal_used"] = True
            trace["temporal_reason"] = "query_temporal_signals_matched"
        else:
            trace["temporal_reason"] = "no_temporal_query_match_or_metadata"

    return raw_results, response_mode, trace


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


def _build_score_diagnostics(raw_results: List[Dict], top_n: int = 10) -> list[dict]:
    diags = []
    for item in raw_results[:top_n]:
        diags.append({
            "chunk_id": item.get("chunk_id"),
            "vector_score": round(item["vector_score"], 4) if item.get("vector_score") is not None else None,
            "keyword_score": round(item["keyword_score"], 4) if item.get("keyword_score") is not None else None,
            "combined_score": round(item["combined_score"], 4) if item.get("combined_score") is not None else None,
            "rerank_score": round(item["rerank_score"], 4) if item.get("rerank_score") is not None else None,
            "anchor_score": round(item.get("anchor_score", 0.0), 4),
        })
    return diags


def _persist_trace(*, retrieval_trace: dict, question: str, score_diagnostics: list, answer_path: str | None = None) -> None:
    import uuid
    try:
        from app.db.repo_traces import insert_trace
        from app.profiles.resolver import get_active_profile_snapshot
        request_id = retrieval_trace.get("request_id") or str(uuid.uuid4())
        insert_trace(
            request_id=request_id,
            question=question,
            requested_mode=retrieval_trace.get("requested_mode"),
            resolved_mode=retrieval_trace.get("resolved_mode", "unknown"),
            retrieval_path=retrieval_trace.get("retrieval_path_used", "unknown"),
            candidate_counts=retrieval_trace.get("candidate_counts", {}),
            fallback_reason=retrieval_trace.get("fallback_reason"),
            answer_path=answer_path,
            latency_ms=retrieval_trace.get("latency_ms", {}),
            score_diagnostics=score_diagnostics,
            trace_json=retrieval_trace,
            active_profiles=get_active_profile_snapshot(),
        )
    except Exception as exc:
        logger.debug("Failed to persist retrieval trace: %s", exc)


def perform_search(request: SearchRequest) -> SearchResponse:
    import uuid
    start_time = time.time()
    request_id = str(uuid.uuid4())
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

    retrieval_trace: dict = {
        "request_id": request_id,
        "requested_mode": request.mode,
        "resolved_mode": resolved_mode,
        "retrieval_path_used": resolved_mode,
        "route_reason": route_decision.reason,
        "deep_research_requested": request.deep_research,
        "deep_research_used": False,
        "effective_query": _resolve_query_text(request),
        "anchor_terms_requested": _normalize_anchor_terms(request.anchor_terms),
        "fallback_reason": None,
        "graph_used": False,
        "temporal_used": False,
        "graph_reason": "not_requested",
        "temporal_reason": "not_requested",
        "candidate_counts": {},
        "latency_ms": {},
    }

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
        effective_k = request.k
        search_start = time.time()
        if request.deep_research:
            raw_results, deep_trace = _run_deep_research_mode(
                request=request,
                source_type=source_type,
                source_id=source_id,
                source_part_id=source_part_id,
                locator_filter=locator_filter,
            )
            rp = get_effective_retrieval()
            rr = get_effective_reranker()
            effective_k = max(request.k, rp.top_k_initial if rr.enabled else request.k)
            retrieval_trace.update(deep_trace)
            if resolved_mode in {"graph_hybrid", "full"}:
                raw_results, resolved_mode, graph_trace = _apply_graph_and_temporal_layers(
                    request=request,
                    resolved_mode=resolved_mode,
                    source_id=source_id,
                    raw_results=raw_results,
                    effective_k=effective_k,
                )
                retrieval_trace.update(graph_trace)
                retrieval_trace["retrieval_path_used"] = resolved_mode
        elif resolved_mode == "vector":
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
            raw_results, resolved_mode, graph_trace = _apply_graph_and_temporal_layers(
                request=request,
                resolved_mode=resolved_mode,
                source_id=source_id,
                raw_results=raw_results,
                effective_k=effective_k,
            )
            retrieval_trace.update(graph_trace)
            retrieval_trace["retrieval_path_used"] = resolved_mode
        search_ms = int((time.time() - search_start) * 1000)
        retrieval_trace["latency_ms"]["search"] = search_ms
        retrieval_trace["candidate_counts"]["pre_rerank"] = len(raw_results)
    except Exception as exc:
        retrieval_trace["fallback_reason"] = str(exc)
        retrieval_trace["latency_ms"]["search"] = int((time.time() - start_time) * 1000)
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
        total_ms = int((time.time() - start_time) * 1000)
        retrieval_trace["latency_ms"]["total"] = total_ms
        _persist_trace(retrieval_trace=retrieval_trace, question=request.question, score_diagnostics=[])
        return SearchResponse(results=[], latency_ms=total_ms, mode=resolved_mode, debug_info=retrieval_trace)

    rerank_ms = 0
    if get_effective_reranker().enabled and raw_results:
        from app.core_rag.reranker import rerank

        logger.info(f"Reranking {len(raw_results)} candidates down to {request.k}")
        rerank_start = time.time()
        raw_results = rerank(request.question, raw_results, request.k)
        rerank_ms = int((time.time() - rerank_start) * 1000)
        retrieval_trace["latency_ms"]["rerank"] = rerank_ms
    elif len(raw_results) > request.k:
        raw_results = raw_results[: request.k]

    retrieval_trace["candidate_counts"]["post_rerank"] = len(raw_results)

    score_diagnostics = _build_score_diagnostics(raw_results)
    retrieval_trace["score_diagnostics"] = score_diagnostics

    results = _materialize_search_results(raw_results=raw_results, resolved_mode=resolved_mode, debug=request.debug)

    total_ms = int((time.time() - start_time) * 1000)
    retrieval_trace["latency_ms"]["total"] = total_ms

    log_event(
        "search.completed",
        source_id=source_id,
        stage="search",
        status="completed",
        requested_mode=request.mode,
        resolved_mode=resolved_mode,
        reason=f"results={len(results)}",
    )

    _persist_trace(retrieval_trace=retrieval_trace, question=request.question, score_diagnostics=score_diagnostics)

    return SearchResponse(
        results=results,
        latency_ms=total_ms,
        mode=resolved_mode,
        debug_info=retrieval_trace,
    )


def perform_deep_lookup(request: DeepLookupRequest) -> DeepLookupResponse:
    rp = get_effective_retrieval()
    start_time = time.time()
    scoped_source_ids = list(request.source_ids)
    effective_k = max(request.k * 3, rp.deep_research_vector_candidates)
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
            k=max(request.k * 2, rp.deep_research_vector_candidates),
            source_ids=scoped_source_ids,
        )
        keyword_results = search_chunks_keyword(
            query_text=request.question,
            k=max(request.k * 3, rp.deep_research_keyword_candidates),
            source_ids=scoped_source_ids,
        )
        raw_results = merge_hybrid_results(
            vector_results=vector_results,
            keyword_results=keyword_results,
            k=effective_k,
            alpha=rp.deep_research_alpha,
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
