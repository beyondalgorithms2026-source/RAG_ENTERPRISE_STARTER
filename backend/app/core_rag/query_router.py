from dataclasses import dataclass
from typing import Optional

from app.core.config import settings
from app.db.repo_sources import get_source_by_id
from app.graph.graph_index import GRAPH_INDEX_ARTIFACT_VERSION
from app.graph.temporal import TEMPORAL_ARTIFACT_VERSION, analyze_temporal_metadata


@dataclass(frozen=True)
class QueryRouteDecision:
    selected_mode: str
    preferred_mode: str
    reason: str
    router_applied: bool
    manual_mode: bool
    fallback_reason: Optional[str] = None
    graph_ready: bool = False
    temporal_ready: bool = False
    source_scoped: bool = False


def _artifact_current(*, artifact_metadata, expected_version: str, source_hash: Optional[str]) -> bool:
    if not isinstance(artifact_metadata, dict) or not artifact_metadata:
        return False
    artifact_version = artifact_metadata.get("artifact_version") or artifact_metadata.get("provenance", {}).get("artifact_version")
    built_from_source_hash = artifact_metadata.get("built_from_source_hash") or artifact_metadata.get(
        "provenance", {}
    ).get("built_from_source_hash")
    if artifact_version != expected_version:
        return False
    if source_hash and built_from_source_hash and built_from_source_hash != source_hash:
        return False
    return True


def _has_exact_lookup_signal(question: str) -> bool:
    question_lower = question.lower()
    return any(
        token in question_lower
        for token in (
            '"',
            "find ",
            "mention",
            "contains",
            "exact",
            "locate",
            "where does",
        )
    )


def _has_graph_signal(question: str) -> bool:
    question_lower = question.lower()
    return any(
        token in question_lower
        for token in (
            "reports to",
            "works with",
            "related to",
            "relationship",
            "connected to",
            "linked to",
            "who reports",
            "who works with",
        )
    )


def _has_temporal_signal(question: str) -> bool:
    question_lower = question.lower()
    analysis = analyze_temporal_metadata(text=question)
    return bool(
        analysis.metadata.get("normalized_dates")
        or analysis.metadata.get("document_version_refs")
        or any(
            token in question_lower
            for token in (
                "timeline",
                "latest as of",
                "as of ",
                "effective",
                "valid until",
                "valid through",
                "expires",
                "version",
            )
        )
    )


def route_query(
    *,
    question: str,
    explicit_mode: Optional[str],
    default_mode: str,
    source_id: Optional[int] = None,
) -> QueryRouteDecision:
    if explicit_mode is not None:
        return QueryRouteDecision(
            selected_mode=explicit_mode,
            preferred_mode=explicit_mode,
            reason="manual_mode_selected",
            router_applied=False,
            manual_mode=True,
            source_scoped=source_id is not None,
        )

    if not settings.USE_QUERY_ROUTER:
        return QueryRouteDecision(
            selected_mode=default_mode,
            preferred_mode=default_mode,
            reason="router_disabled",
            router_applied=False,
            manual_mode=False,
            source_scoped=source_id is not None,
        )

    source_scoped = source_id is not None
    graph_ready = False
    temporal_ready = False
    if source_scoped:
        source = get_source_by_id(source_id)
        if source is not None:
            metadata = dict(source.source_metadata_json or {})
            graph_ready = bool(settings.ENABLE_GRAPH) and _artifact_current(
                artifact_metadata=metadata.get("graph"),
                expected_version=GRAPH_INDEX_ARTIFACT_VERSION,
                source_hash=source.hash_sha256,
            )
            temporal_ready = bool(
                settings.ENABLE_TEMPORAL or settings.EXTRACT_TEMPORAL_METADATA or settings.TEMPORAL_RERANK_ENABLED
            ) and _artifact_current(
                artifact_metadata=metadata.get("temporal"),
                expected_version=TEMPORAL_ARTIFACT_VERSION,
                source_hash=source.hash_sha256,
            )

    has_graph_signal = _has_graph_signal(question)
    has_temporal_signal = _has_temporal_signal(question)
    has_exact_lookup_signal = _has_exact_lookup_signal(question)

    if has_temporal_signal:
        if temporal_ready:
            return QueryRouteDecision(
                selected_mode="full",
                preferred_mode="full",
                reason="temporal_signal_with_ready_artifacts",
                router_applied=True,
                manual_mode=False,
                graph_ready=graph_ready,
                temporal_ready=temporal_ready,
                source_scoped=source_scoped,
            )
        return QueryRouteDecision(
            selected_mode="hybrid",
            preferred_mode="full",
            reason="temporal_signal_fallback_to_hybrid",
            router_applied=True,
            manual_mode=False,
            fallback_reason="temporal_artifacts_unavailable",
            graph_ready=graph_ready,
            temporal_ready=temporal_ready,
            source_scoped=source_scoped,
        )

    if has_graph_signal:
        if graph_ready:
            return QueryRouteDecision(
                selected_mode="graph_hybrid",
                preferred_mode="graph_hybrid",
                reason="relationship_signal_with_ready_graph",
                router_applied=True,
                manual_mode=False,
                graph_ready=graph_ready,
                temporal_ready=temporal_ready,
                source_scoped=source_scoped,
            )
        return QueryRouteDecision(
            selected_mode="hybrid",
            preferred_mode="graph_hybrid",
            reason="relationship_signal_fallback_to_hybrid",
            router_applied=True,
            manual_mode=False,
            fallback_reason="graph_artifacts_unavailable",
            graph_ready=graph_ready,
            temporal_ready=temporal_ready,
            source_scoped=source_scoped,
        )

    if has_exact_lookup_signal:
        return QueryRouteDecision(
            selected_mode="keyword",
            preferred_mode="keyword",
            reason="exact_lookup_signal",
            router_applied=True,
            manual_mode=False,
            graph_ready=graph_ready,
            temporal_ready=temporal_ready,
            source_scoped=source_scoped,
        )

    return QueryRouteDecision(
        selected_mode="hybrid",
        preferred_mode="hybrid",
        reason="default_hybrid_router_policy",
        router_applied=True,
        manual_mode=False,
        graph_ready=graph_ready,
        temporal_ready=temporal_ready,
        source_scoped=source_scoped,
    )
