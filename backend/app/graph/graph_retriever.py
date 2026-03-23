from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.config import settings
from app.db.repo_search import fetch_chunks_by_ids
from app.db.repo_sources import get_source_by_id
from app.graph.graph_index import GRAPH_INDEX_ARTIFACT_VERSION


GRAPH_RETRIEVER_ARTIFACT_VERSION = "m16-graph-retriever-v1"


@dataclass(frozen=True)
class GraphRetrievalResult:
    candidates: list[dict[str, Any]] = field(default_factory=list)
    enabled: bool = False
    reason: str = "graph_disabled"
    artifact_version: str = GRAPH_RETRIEVER_ARTIFACT_VERSION
    used_artifact_version: Optional[str] = None


def _graph_artifact_current(graph_metadata: Any, source_hash: Optional[str]) -> bool:
    if not isinstance(graph_metadata, dict) or not graph_metadata:
        return False
    if graph_metadata.get("artifact_version") != GRAPH_INDEX_ARTIFACT_VERSION:
        return False
    if graph_metadata.get("build_status") != "built":
        return False
    built_from_source_hash = graph_metadata.get("built_from_source_hash") or graph_metadata.get("provenance", {}).get(
        "built_from_source_hash"
    )
    if source_hash and built_from_source_hash and built_from_source_hash != source_hash:
        return False
    snapshot = graph_metadata.get("snapshot")
    return isinstance(snapshot, dict)


def _match_graph_chunk_scores(*, question: str, graph_metadata: dict[str, Any]) -> dict[int, float]:
    snapshot = graph_metadata.get("snapshot") or {}
    question_lower = question.lower()
    question_compact = " ".join(question_lower.split())
    chunk_scores: dict[int, float] = {}

    for node in snapshot.get("nodes", []):
        terms = {str(node.get("canonical_name") or "").strip().lower()}
        terms.update(str(alias).strip().lower() for alias in (node.get("aliases") or []) if str(alias).strip())
        matched = any(term and term in question_lower for term in terms)
        if not matched:
            continue
        for chunk_ref in node.get("chunk_refs", []):
            chunk_id = chunk_ref.get("chunk_id")
            if chunk_id is None:
                continue
            chunk_scores[chunk_id] = max(chunk_scores.get(chunk_id, 0.0), 0.12)

    for edge in snapshot.get("edges", []):
        relation_type = str(edge.get("relation_type") or "").replace("_", " ").strip().lower()
        subject = str(edge.get("subject") or "").strip().lower()
        obj = str(edge.get("object") or "").strip().lower()
        matched = False
        if relation_type and relation_type in question_compact:
            matched = True
        elif subject and obj and subject in question_lower and obj in question_lower:
            matched = True
        if not matched:
            continue
        for chunk_ref in edge.get("chunk_refs", []):
            chunk_id = chunk_ref.get("chunk_id")
            if chunk_id is None:
                continue
            chunk_scores[chunk_id] = max(chunk_scores.get(chunk_id, 0.0), 0.18)

    return chunk_scores


def retrieve_graph_candidates(
    *,
    question: str,
    source_id: Optional[int] = None,
    baseline_candidates: Optional[list[dict[str, Any]]] = None,
) -> GraphRetrievalResult:
    if not settings.ENABLE_GRAPH:
        return GraphRetrievalResult(reason="graph_disabled")
    if source_id is None:
        return GraphRetrievalResult(reason="graph_source_scope_required")

    source = get_source_by_id(source_id)
    if source is None:
        return GraphRetrievalResult(reason="graph_source_not_found")

    graph_metadata = dict(source.source_metadata_json or {}).get("graph")
    if not _graph_artifact_current(graph_metadata, source.hash_sha256):
        return GraphRetrievalResult(reason="graph_artifact_missing_or_stale")

    chunk_scores = _match_graph_chunk_scores(question=question, graph_metadata=graph_metadata)
    if not chunk_scores:
        return GraphRetrievalResult(
            enabled=True,
            reason="graph_no_query_matches",
            used_artifact_version=graph_metadata.get("artifact_version"),
        )

    baseline_ids = {item.get("chunk_id") for item in (baseline_candidates or [])}
    supplemental_chunk_ids = [chunk_id for chunk_id in chunk_scores if chunk_id not in baseline_ids]
    supplemental_candidates = fetch_chunks_by_ids(supplemental_chunk_ids)
    for item in supplemental_candidates:
        item["graph_score"] = chunk_scores.get(item["chunk_id"], 0.0)
        item["combined_score"] = item["graph_score"]

    candidates: list[dict[str, Any]] = []
    for chunk_id, graph_score in sorted(chunk_scores.items(), key=lambda item: (-item[1], item[0])):
        candidate = next((item for item in supplemental_candidates if item["chunk_id"] == chunk_id), None)
        if candidate is None:
            candidate = {"chunk_id": chunk_id, "graph_score": graph_score}
        else:
            candidate = dict(candidate)
        candidate["graph_score"] = graph_score
        candidates.append(candidate)

    return GraphRetrievalResult(
        candidates=candidates,
        enabled=True,
        reason="m16_graph_candidates_ready",
        used_artifact_version=graph_metadata.get("artifact_version"),
    )
