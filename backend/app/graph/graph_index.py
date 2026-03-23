from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.config import settings


GRAPH_INDEX_ARTIFACT_VERSION = "m14-graph-artifact-v1"


@dataclass(frozen=True)
class GraphArtifactStatus:
    available: bool
    reason: str
    snapshot: dict[str, Any] = field(default_factory=dict)
    stats: dict[str, Any] = field(default_factory=dict)
    storage_backend: str = "noop"
    artifact_version: str = GRAPH_INDEX_ARTIFACT_VERSION


def _stable_key(*parts: Any) -> str:
    return "::".join(str(part) for part in parts if part is not None and str(part) != "")


def _compact_chunk_ref(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": chunk.get("id"),
        "source_part_id": chunk.get("source_part_id"),
        "chunk_index": chunk.get("chunk_index"),
        "locator": chunk.get("locator_json") or {},
    }


def ensure_graph_artifacts(
    *,
    source_id: Optional[int] = None,
    chunks: Optional[list[dict[str, Any]]] = None,
) -> GraphArtifactStatus:
    if not settings.ENABLE_GRAPH:
        return GraphArtifactStatus(available=False, reason="graph_disabled")

    if not settings.BUILD_GRAPH_ON_INGEST:
        return GraphArtifactStatus(available=False, reason="graph_build_disabled")

    if not chunks:
        return GraphArtifactStatus(available=False, reason=f"no_graph_ready_chunks:source_id={source_id}")

    node_map: dict[str, dict[str, Any]] = {}
    edge_map: dict[str, dict[str, Any]] = {}
    input_chunk_count = len(chunks)
    enriched_chunk_count = 0

    for chunk in chunks:
        chunk_entities = chunk.get("entities_json") or []
        chunk_relations = chunk.get("relations_json") or []
        if chunk_entities or chunk_relations:
            enriched_chunk_count += 1
        chunk_ref = _compact_chunk_ref(chunk)

        for entity in chunk_entities:
            canonical_name = entity.get("canonical_name") or entity.get("surface_text")
            if not canonical_name:
                continue
            node_id = _stable_key("node", canonical_name)
            node = node_map.setdefault(
                node_id,
                {
                    "node_id": node_id,
                    "canonical_name": canonical_name,
                    "entity_type": entity.get("entity_type") or "entity",
                    "ontology_tags": [],
                    "aliases": [],
                    "mention_count": 0,
                    "chunk_refs": [],
                },
            )
            node["mention_count"] += 1
            node["ontology_tags"] = sorted(set(node["ontology_tags"]) | set(entity.get("ontology_tags") or []))
            node["aliases"] = sorted(set(node["aliases"]) | set(entity.get("aliases") or []))
            if chunk_ref not in node["chunk_refs"]:
                node["chunk_refs"].append(chunk_ref)

        for relation in chunk_relations:
            subject = relation.get("subject")
            relation_type = relation.get("relation_type")
            obj = relation.get("object")
            if not subject or not relation_type or not obj:
                continue
            edge_id = _stable_key("edge", subject, relation_type, obj)
            edge = edge_map.setdefault(
                edge_id,
                {
                    "edge_id": edge_id,
                    "subject": subject,
                    "relation_type": relation_type,
                    "object": obj,
                    "evidence_count": 0,
                    "chunk_refs": [],
                },
            )
            edge["evidence_count"] += 1
            if chunk_ref not in edge["chunk_refs"]:
                edge["chunk_refs"].append(chunk_ref)

    if not node_map and not edge_map:
        return GraphArtifactStatus(
            available=False,
            reason=f"no_graph_ready_metadata:source_id={source_id}",
            stats={
                "source_id": source_id,
                "input_chunk_count": input_chunk_count,
                "enriched_chunk_count": 0,
                "node_count": 0,
                "edge_count": 0,
            },
            storage_backend="source_metadata_json",
        )

    nodes = sorted(node_map.values(), key=lambda item: item["canonical_name"])
    edges = sorted(edge_map.values(), key=lambda item: (item["subject"], item["relation_type"], item["object"]))
    relation_type_counts: dict[str, int] = {}
    entity_type_counts: dict[str, int] = {}
    for node in nodes:
        entity_type = node.get("entity_type") or "entity"
        entity_type_counts[entity_type] = entity_type_counts.get(entity_type, 0) + 1
    for edge in edges:
        relation_type = edge.get("relation_type") or "related_to"
        relation_type_counts[relation_type] = relation_type_counts.get(relation_type, 0) + 1

    snapshot = {
        "artifact_version": GRAPH_INDEX_ARTIFACT_VERSION,
        "source_id": source_id,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "nodes": nodes,
        "edges": edges,
    }
    stats = {
        "source_id": source_id,
        "input_chunk_count": input_chunk_count,
        "enriched_chunk_count": enriched_chunk_count,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "entity_type_counts": entity_type_counts,
        "relation_type_counts": relation_type_counts,
    }
    return GraphArtifactStatus(
        available=True,
        reason="m14_graph_artifact_built",
        snapshot=snapshot,
        stats=stats,
        storage_backend="source_metadata_json",
    )
