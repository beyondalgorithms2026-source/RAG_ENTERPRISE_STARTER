from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.config import settings


GRAPH_EXPLAIN_ARTIFACT_VERSION = "m14-graph-explain-v1"


@dataclass(frozen=True)
class GraphExplainResult:
    enabled: bool = False
    reason: str = "graph_explainability_disabled"
    details: dict[str, Any] = field(default_factory=dict)
    artifact_version: str = GRAPH_EXPLAIN_ARTIFACT_VERSION


def explain_graph_result(*, result_count: int, graph_artifact: Optional[dict[str, Any]] = None) -> GraphExplainResult:
    if not settings.ENABLE_GRAPH_EXPLAINABILITY:
        return GraphExplainResult()
    details = {"result_count": result_count}
    if graph_artifact:
        stats = graph_artifact.get("stats") or {}
        details.update(
            {
                "graph_artifact_version": graph_artifact.get("artifact_version"),
                "node_count": stats.get("node_count"),
                "edge_count": stats.get("edge_count"),
                "storage_backend": graph_artifact.get("storage_backend"),
            }
        )
    return GraphExplainResult(
        enabled=True,
        reason="m14_graph_artifact_summary",
        details=details,
    )
