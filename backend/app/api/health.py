from fastapi import APIRouter

from app.core.config import settings
from app.db.repo_sources import list_sources

router = APIRouter()


@router.get("/health")
def health_check():
    sources = list_sources()
    total_sources = len(sources)
    embedded_sources = sum(1 for source in sources if source.ingestion_status == "embedded")
    enriched_sources = sum(1 for source in sources if source.enrichment_status == "completed")
    graph_ready_sources = sum(
        1
        for source in sources
        if isinstance(source.source_metadata_json, dict)
        and isinstance(source.source_metadata_json.get("graph"), dict)
        and source.source_metadata_json.get("graph", {}).get("build_status") == "built"
    )
    temporal_ready_sources = sum(
        1
        for source in sources
        if isinstance(source.source_metadata_json, dict)
        and isinstance(source.source_metadata_json.get("temporal"), dict)
        and source.source_metadata_json.get("temporal", {}).get("build_status") == "built"
    )

    return {
        "status": "ok",
        "retrieval_defaults": {
            "mode": settings.RETRIEVAL_MODE,
            "rerank_enabled": settings.RERANK_ENABLED,
        },
        "features": {
            "graph_enabled": settings.ENABLE_GRAPH,
            "temporal_enabled": settings.ENABLE_TEMPORAL,
            "ontology_enabled": settings.ENABLE_ONTOLOGY,
            "deep_research_available": True,
            "graph_build_on_ingest": settings.BUILD_GRAPH_ON_INGEST,
            "entity_extraction_enabled": settings.EXTRACT_ENTITIES,
            "relation_extraction_enabled": settings.EXTRACT_RELATIONS,
            "temporal_extraction_enabled": settings.EXTRACT_TEMPORAL_METADATA,
        },
        "corpus": {
            "total_sources": total_sources,
            "embedded_sources": embedded_sources,
            "enriched_sources": enriched_sources,
            "graph_ready_sources": graph_ready_sources,
            "temporal_ready_sources": temporal_ready_sources,
        },
    }
