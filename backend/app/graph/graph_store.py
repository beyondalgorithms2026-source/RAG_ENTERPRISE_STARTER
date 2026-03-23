from dataclasses import dataclass
from typing import Any

from app.core.config import settings


GRAPH_STORE_ARTIFACT_VERSION = "m14-graph-store-v1"


@dataclass(frozen=True)
class GraphStoreStatus:
    backend: str
    enabled: bool
    reason: str
    artifact_version: str = GRAPH_STORE_ARTIFACT_VERSION


class NoOpGraphStore:
    def status(self) -> GraphStoreStatus:
        if settings.ENABLE_GRAPH and settings.BUILD_GRAPH_ON_INGEST:
            return GraphStoreStatus(backend="noop", enabled=False, reason="graph_store_unavailable")
        return GraphStoreStatus(backend="noop", enabled=False, reason="graph_disabled")


class SourceMetadataGraphStore:
    def status(self) -> GraphStoreStatus:
        if settings.ENABLE_GRAPH and settings.BUILD_GRAPH_ON_INGEST:
            return GraphStoreStatus(backend="source_metadata_json", enabled=True, reason="m14_metadata_store_ready")
        return GraphStoreStatus(backend="source_metadata_json", enabled=False, reason="graph_build_disabled")

    def compact_artifact(self, *, graph_status: Any) -> dict[str, Any]:
        return {
            "artifact_version": getattr(graph_status, "artifact_version", GRAPH_STORE_ARTIFACT_VERSION),
            "build_status": "built" if getattr(graph_status, "available", False) else "skipped",
            "build_reason": getattr(graph_status, "reason", "graph_build_unknown"),
            "storage_backend": "source_metadata_json",
            "stats": getattr(graph_status, "stats", {}) or {},
            "snapshot": getattr(graph_status, "snapshot", {}) or {},
        }


def get_graph_store() -> Any:
    if settings.ENABLE_GRAPH and settings.BUILD_GRAPH_ON_INGEST:
        return SourceMetadataGraphStore()
    return NoOpGraphStore()
