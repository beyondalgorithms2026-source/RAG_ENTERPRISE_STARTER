from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.config import settings
from app.core.logging import log_event, logger
from app.db.repo_chunks import get_chunks_for_enrichment, update_chunk_enrichment
from app.db.repo_jobs import create_enrichment_job, finish_enrichment_job
from app.db.repo_sources import (
    get_source_by_id,
    record_lazy_enrichment_trace,
    remove_source_metadata_sections,
    update_source_graph_metadata,
    update_source_status,
    update_source_temporal_metadata,
)
from app.graph.graph_index import GRAPH_INDEX_ARTIFACT_VERSION, ensure_graph_artifacts
from app.graph.graph_store import get_graph_store
from app.graph.extractor import EXTRACTOR_ARTIFACT_VERSION, run_enrichment_extractors
from app.graph.ontology import ONTOLOGY_ARTIFACT_VERSION
from app.graph.temporal import TEMPORAL_ARTIFACT_VERSION, analyze_temporal_metadata, summarize_temporal_metadata


GRAPH_ARTIFACT_VERSION = GRAPH_INDEX_ARTIFACT_VERSION


@dataclass(frozen=True)
class EnrichmentRunResult:
    attempted: bool
    wrote_job: bool
    fallback_used: bool
    reason: str
    artifact_versions: dict[str, str] = field(default_factory=dict)
    chunk_updates: int = 0
    entities_extracted: int = 0
    relations_extracted: int = 0
    debug_summary: dict[str, Any] = field(default_factory=dict)
    job_id: Optional[int] = None


@dataclass(frozen=True)
class LazyEnrichmentResult:
    source_id: Optional[int]
    requested_mode: str
    attempted: bool = False
    triggered: bool = False
    wrote_job: bool = False
    artifacts_current: bool = False
    reason: str = "lazy_enrichment_disabled"
    job_id: Optional[int] = None
    debug_summary: dict[str, Any] = field(default_factory=dict)


def get_enrichment_artifact_versions() -> dict[str, str]:
    return {
        "extractor": EXTRACTOR_ARTIFACT_VERSION,
        "graph": GRAPH_ARTIFACT_VERSION,
        "ontology": ONTOLOGY_ARTIFACT_VERSION,
        "temporal": TEMPORAL_ARTIFACT_VERSION,
    }


def _artifact_current(*, artifact_metadata: Any, expected_version: str, source_hash: Optional[str]) -> bool:
    if not isinstance(artifact_metadata, dict) or not artifact_metadata:
        return False
    artifact_version = artifact_metadata.get("artifact_version") or artifact_metadata.get("provenance", {}).get("artifact_version")
    built_from_source_hash = artifact_metadata.get("built_from_source_hash") or artifact_metadata.get("provenance", {}).get("built_from_source_hash")
    if artifact_version != expected_version:
        return False
    if source_hash and built_from_source_hash and built_from_source_hash != source_hash:
        return False
    return True


def _build_lazy_trace(*, source_hash: Optional[str], requested_mode: str = "full", **extra: Any) -> dict[str, Any]:
    trace = {
        "requested_mode": requested_mode,
        "source_hash": source_hash,
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }
    trace.update(extra)
    return trace


def _record_lazy_result(
    *,
    source_id: Optional[int],
    source_hash: Optional[str],
    reason: str,
    attempted: bool,
    triggered: bool,
    wrote_job: bool = False,
    artifacts_current: bool = False,
    job_id: Optional[int] = None,
    extra_debug: Optional[dict[str, Any]] = None,
) -> LazyEnrichmentResult:
    trace = _build_lazy_trace(
        source_hash=source_hash,
        attempted=attempted,
        triggered=triggered,
        wrote_job=wrote_job,
        artifacts_current=artifacts_current,
        reason=reason,
        job_id=job_id,
        **(extra_debug or {}),
    )
    if source_id is not None:
        record_lazy_enrichment_trace(source_id, trace)
    return LazyEnrichmentResult(
        source_id=source_id,
        requested_mode="full",
        attempted=attempted,
        triggered=triggered,
        wrote_job=wrote_job,
        artifacts_current=artifacts_current,
        reason=reason,
        job_id=job_id,
        debug_summary=trace,
    )


def _lazy_feature_requirements() -> tuple[bool, bool]:
    return (
        bool(settings.ENABLE_GRAPH and settings.BUILD_GRAPH_ON_INGEST),
        bool(settings.ENABLE_TEMPORAL or settings.EXTRACT_TEMPORAL_METADATA),
    )


def _artifact_currentness_for_source(
    *,
    metadata: dict[str, Any],
    source_hash: Optional[str],
    artifact_versions: dict[str, str],
    needs_graph: bool,
    needs_temporal: bool,
) -> tuple[bool, bool]:
    graph_current = True
    temporal_current = True
    if needs_graph:
        graph_current = _artifact_current(
            artifact_metadata=metadata.get("graph"),
            expected_version=artifact_versions["graph"],
            source_hash=source_hash,
        )
    if needs_temporal:
        temporal_current = _artifact_current(
            artifact_metadata=metadata.get("temporal"),
            expected_version=artifact_versions["temporal"],
            source_hash=source_hash,
        )
    return graph_current, temporal_current


def _build_chunk_debug_entry(*, chunk_id: int, entities_json: list[dict[str, Any]], relations_json: list[dict[str, Any]], temporal_metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "entity_count": len(entities_json),
        "relation_count": len(relations_json),
        "temporal_expression_count": len(temporal_metadata.get("expressions", [])),
        "temporal_fallback_reason": temporal_metadata.get("fallback_reason"),
        "graph_ready": bool(entities_json or relations_json),
    }


def _build_graph_input_chunk(*, chunk: dict[str, Any], entities_json: list[dict[str, Any]], relations_json: list[dict[str, Any]], merged_provenance: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": chunk["id"],
        "source_id": chunk["source_id"],
        "source_part_id": chunk.get("source_part_id"),
        "chunk_index": chunk.get("chunk_index"),
        "locator_json": chunk.get("locator_json") or {},
        "entities_json": entities_json,
        "relations_json": relations_json,
        "provenance_json": merged_provenance,
    }


def _persist_source_temporal_summary(*, source_id: int, source_hash: Optional[str], temporal_enabled: bool, temporal_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    source_temporal_summary = summarize_temporal_metadata(chunk_temporal_metadata=temporal_summaries)
    if temporal_enabled:
        source_temporal_summary["built_from_source_hash"] = source_hash
        source_temporal_summary["build_status"] = (
            "fallback" if source_temporal_summary.get("fallback_reason") else "built"
        )
        update_source_temporal_metadata(source_id, source_temporal_summary)
    return source_temporal_summary


def _build_graph_metadata(*, source_id: int, source_hash: Optional[str], source_part_count: int, chunk_count: int, artifact_versions: dict[str, str], graph_status: Any, graph_store: Any) -> dict[str, Any]:
    graph_metadata = graph_store.compact_artifact(graph_status=graph_status)
    graph_metadata["built_from_source_hash"] = source_hash
    graph_metadata["build_status"] = "built" if graph_status.available else "skipped"
    graph_metadata["build_reason"] = graph_status.reason
    graph_metadata["provenance"] = {
        "artifact_version": artifact_versions["graph"],
        "extractor_artifact_version": artifact_versions["extractor"],
        "source_id": source_id,
        "source_part_count": source_part_count,
        "chunk_count": chunk_count,
        "enriched_chunk_count": graph_status.stats.get("enriched_chunk_count", 0),
        "built_from_source_hash": source_hash,
    }
    return graph_metadata


def ensure_lazy_full_mode_readiness(*, source_id: Optional[int]) -> LazyEnrichmentResult:
    artifact_versions = get_enrichment_artifact_versions()
    if not settings.ALLOW_LAZY_ENRICHMENT:
        return _record_lazy_result(
            source_id=source_id,
            source_hash=None,
            reason="lazy_enrichment_disabled",
            attempted=False,
            triggered=False,
            extra_debug={"fallback_mode": "hybrid"},
        )

    if source_id is None:
        return _record_lazy_result(
            source_id=source_id,
            source_hash=None,
            reason="source_scope_required_for_lazy_enrichment",
            attempted=False,
            triggered=False,
            extra_debug={"fallback_mode": "hybrid"},
        )

    source = get_source_by_id(source_id)
    if source is None:
        return _record_lazy_result(
            source_id=source_id,
            source_hash=None,
            reason="source_not_found",
            attempted=False,
            triggered=False,
            extra_debug={"fallback_mode": "hybrid"},
        )

    metadata = dict(source.source_metadata_json or {})
    source_hash = source.hash_sha256
    needs_graph, needs_temporal = _lazy_feature_requirements()
    if not needs_graph and not needs_temporal:
        return _record_lazy_result(
            source_id=source_id,
            source_hash=source_hash,
            reason="full_enrichment_prerequisites_disabled",
            attempted=False,
            triggered=False,
        )

    graph_current, temporal_current = _artifact_currentness_for_source(
        metadata=metadata,
        source_hash=source_hash,
        artifact_versions=artifact_versions,
        needs_graph=needs_graph,
        needs_temporal=needs_temporal,
    )

    if graph_current and temporal_current:
        return _record_lazy_result(
            source_id=source_id,
            source_hash=source_hash,
            artifacts_current=True,
            reason="artifacts_current",
            attempted=False,
            triggered=False,
        )

    chunks = get_chunks_for_enrichment(source_id)
    source_part_ids = {chunk.get("source_part_id") for chunk in chunks if chunk.get("source_part_id") is not None}
    base_trace = {
        "graph_needed": needs_graph,
        "temporal_needed": needs_temporal,
        "graph_current_before": graph_current,
        "temporal_current_before": temporal_current,
        "chunk_count": len(chunks),
        "source_part_count": len(source_part_ids),
    }
    try:
        log_event(
            "lazy_enrich.started",
            source_id=source_id,
            stage="lazy_enrich",
            status="processing",
            requested_mode="full",
        )
        result = run_post_ingestion_enrichment(
            source_id=source_id,
            source_part_count=len(source_part_ids),
            chunk_count=len(chunks),
            record_job=True,
        )
        return _record_lazy_result(
            source_id=source_id,
            source_hash=source_hash,
            attempted=True,
            triggered=True,
            wrote_job=result.wrote_job,
            reason=result.reason,
            job_id=result.job_id,
            extra_debug={
                **base_trace,
                "graph_artifact_available_after": result.debug_summary.get("graph_artifact_available", False),
                "temporal_metadata_produced_after": result.debug_summary.get("temporal_metadata_produced", False),
            },
        )
    except Exception as exc:
        log_event(
            "lazy_enrich.failed",
            level=40,
            source_id=source_id,
            stage="lazy_enrich",
            status="failed",
            requested_mode="full",
            reason=str(exc),
        )
        return _record_lazy_result(
            source_id=source_id,
            source_hash=source_hash,
            attempted=True,
            triggered=True,
            reason="lazy_trigger_failed",
            extra_debug={**base_trace, "error": str(exc)},
        )


def enrichment_features_enabled() -> bool:
    return bool(
        settings.EXTRACT_ENTITIES
        or settings.EXTRACT_RELATIONS
        or settings.ENABLE_ONTOLOGY
        or settings.ENABLE_TEMPORAL
        or settings.EXTRACT_TEMPORAL_METADATA
        or (settings.ENABLE_GRAPH and settings.BUILD_GRAPH_ON_INGEST)
    )


def run_post_ingestion_enrichment(
    *,
    source_id: int,
    source_part_count: int,
    chunk_count: int,
    record_job: bool = False,
) -> EnrichmentRunResult:
    artifact_versions = get_enrichment_artifact_versions()
    source = get_source_by_id(source_id)
    source_hash = source.hash_sha256 if source is not None else None
    if not enrichment_features_enabled():
        log_event("build_graph.skipped", source_id=source_id, job_id=None, stage="build_graph", status="skipped", reason="enrichment_flags_disabled")
        log_event("enrich.skipped", source_id=source_id, stage="enrich", status="skipped", reason="enrichment_flags_disabled")
        return EnrichmentRunResult(
            attempted=False,
            wrote_job=False,
            fallback_used=True,
            reason="enrichment_flags_disabled",
            artifact_versions=artifact_versions,
        )

    chunks = get_chunks_for_enrichment(source_id)
    if not chunks:
        log_event("build_graph.skipped", source_id=source_id, job_id=None, stage="build_graph", status="skipped", reason="no_chunks_found")
        log_event("enrich.skipped", source_id=source_id, stage="enrich", status="skipped", reason="no_chunks_found")
        return EnrichmentRunResult(
            attempted=False,
            wrote_job=False,
            fallback_used=True,
            reason="no_chunks_found",
            artifact_versions=artifact_versions,
        )

    job_id = None
    if record_job:
        enrichment_type = "chunk_entity_relation_enrichment"
        artifact_version = artifact_versions["extractor"]
        if settings.ENABLE_GRAPH and settings.BUILD_GRAPH_ON_INGEST:
            enrichment_type = "graph_artifact_build"
            artifact_version = artifact_versions["graph"]
        job_id = create_enrichment_job(
            source_id=source_id,
            enrichment_type=enrichment_type,
            status="processing",
            stage="extracting",
            artifact_version=artifact_version,
            job_metadata_json={
                "source_part_count": source_part_count,
                "chunk_count": chunk_count,
                "artifact_versions": artifact_versions,
            },
        )
    try:
        log_event("enrich.started", source_id=source_id, job_id=job_id, stage="enrich", status="processing")
        extraction_enabled = bool(settings.EXTRACT_ENTITIES or settings.EXTRACT_RELATIONS or settings.ENABLE_ONTOLOGY)
        temporal_enabled = bool(settings.ENABLE_TEMPORAL or settings.EXTRACT_TEMPORAL_METADATA)
        graph_build_enabled = bool(settings.ENABLE_GRAPH and settings.BUILD_GRAPH_ON_INGEST)
        graph_store = get_graph_store()
        chunk_updates = 0
        entity_total = 0
        relation_total = 0
        temporal_chunks_with_metadata = 0
        temporal_fallback_chunks = 0
        temporal_summaries = []
        graph_input_chunks = []
        debug_chunks = []
        for chunk in chunks:
            merged_provenance = dict(chunk.get("provenance_json") or {})
            entities_json = list(chunk.get("entities_json") or [])
            relations_json = list(chunk.get("relations_json") or [])
            temporal_metadata = dict(chunk.get("temporal_json") or {})
            ontology_tags = sorted({tag for entity in entities_json for tag in entity.get("ontology_tags", [])})

            if extraction_enabled:
                artifacts = run_enrichment_extractors(
                    chunk_text=chunk["chunk_text"],
                    source_id=source_id,
                    chunk_id=chunk["id"],
                )
                entities_json = artifacts.entities
                relations_json = artifacts.relations
                ontology_tags = artifacts.ontology_tags
                merged_provenance["enrichment"] = {
                    "artifact_version": artifact_versions["extractor"],
                    "reason": artifacts.provenance.get("reason"),
                    "entity_count": len(artifacts.entities),
                    "relation_count": len(artifacts.relations),
                    "ontology_tags": artifacts.ontology_tags,
                    "debug": artifacts.provenance.get("debug", {}),
                }

            if temporal_enabled:
                temporal_result = analyze_temporal_metadata(text=chunk["chunk_text"])
                temporal_metadata = temporal_result.metadata if temporal_result.enabled else {}
                merged_provenance["temporal"] = {
                    "artifact_version": artifact_versions["temporal"],
                    "reason": temporal_result.reason,
                    "confidence": temporal_metadata.get("confidence"),
                    "fallback_reason": temporal_metadata.get("fallback_reason"),
                    "expression_count": len(temporal_metadata.get("expressions", [])),
                    "version_reference_count": len(temporal_metadata.get("document_version_refs", [])),
                    "evidence": [item.get("evidence") for item in temporal_metadata.get("expressions", [])[:3]],
                }

            if extraction_enabled or temporal_enabled:
                update_chunk_enrichment(
                    chunk_id=chunk["id"],
                    entities_json=entities_json,
                    relations_json=relations_json,
                    temporal_json=temporal_metadata,
                    provenance_json=merged_provenance,
                )
                chunk_updates += 1

            entity_total += len(entities_json)
            relation_total += len(relations_json)
            temporal_summaries.append(temporal_metadata)
            if temporal_metadata:
                if temporal_metadata.get("fallback_reason"):
                    temporal_fallback_chunks += 1
                elif temporal_metadata.get("expressions") or temporal_metadata.get("document_version_refs"):
                    temporal_chunks_with_metadata += 1
            graph_input_chunks.append(
                _build_graph_input_chunk(
                    chunk=chunk,
                    entities_json=entities_json,
                    relations_json=relations_json,
                    merged_provenance=merged_provenance,
                )
            )
            debug_chunks.append(
                _build_chunk_debug_entry(
                    chunk_id=chunk["id"],
                    entities_json=entities_json,
                    relations_json=relations_json,
                    temporal_metadata=temporal_metadata,
                )
            )

        source_temporal_summary = _persist_source_temporal_summary(
            source_id=source_id,
            source_hash=source_hash,
            temporal_enabled=temporal_enabled,
            temporal_summaries=temporal_summaries,
        )

        graph_status = None
        graph_store_invoked = False
        if graph_build_enabled:
            log_event("build_graph.started", source_id=source_id, job_id=job_id, stage="build_graph", status="processing")
            graph_status = ensure_graph_artifacts(source_id=source_id, chunks=graph_input_chunks)
            graph_store_invoked = graph_store.status().enabled
            graph_metadata = _build_graph_metadata(
                source_id=source_id,
                source_hash=source_hash,
                source_part_count=source_part_count,
                chunk_count=chunk_count,
                artifact_versions=artifact_versions,
                graph_status=graph_status,
                graph_store=graph_store,
            )
            update_source_graph_metadata(source_id, graph_metadata)
            log_event(
                "build_graph.completed",
                source_id=source_id,
                job_id=job_id,
                stage="build_graph",
                status="completed",
                reason=graph_status.reason,
            )
        else:
            log_event("build_graph.skipped", source_id=source_id, job_id=job_id, stage="build_graph", status="skipped", reason="graph_build_disabled")

        debug_summary = {
            "source_part_count": source_part_count,
            "chunk_count": chunk_count,
            "chunk_updates": chunk_updates,
            "entities_extracted": entity_total,
            "relations_extracted": relation_total,
            "temporal_chunks_with_metadata": temporal_chunks_with_metadata,
            "temporal_fallback_chunks": temporal_fallback_chunks,
            "source_temporal_summary": source_temporal_summary,
            "graph_artifact_available": bool(graph_status.available) if graph_status is not None else False,
            "graph_artifact_reason": graph_status.reason if graph_status is not None else "graph_build_disabled",
            "graph_artifact_stats": graph_status.stats if graph_status is not None else {},
            "chunk_debug": debug_chunks,
            "graph_index_invoked": graph_build_enabled,
            "graph_store_invoked": graph_store_invoked,
            "temporal_metadata_produced": temporal_chunks_with_metadata > 0 or temporal_fallback_chunks > 0,
        }
        log_event(
            "enrich.completed",
            source_id=source_id,
            job_id=job_id,
            stage="enrich",
            status="completed",
            reason="enrichment_complete",
        )
        if record_job and job_id is not None:
            finish_enrichment_job(job_id, status="completed")
        if graph_build_enabled:
            reason = "m14_graph_artifact_complete"
        elif temporal_enabled:
            reason = "m13_rule_based_temporal_complete"
        else:
            reason = "m12_rule_based_complete"
        return EnrichmentRunResult(
            attempted=True,
            wrote_job=bool(record_job),
            fallback_used=False,
            reason=reason,
            artifact_versions=artifact_versions,
            chunk_updates=chunk_updates,
            entities_extracted=entity_total,
            relations_extracted=relation_total,
            debug_summary=debug_summary,
            job_id=job_id,
        )
    except Exception as exc:
        if job_id is not None:
            finish_enrichment_job(job_id, status="failed", error_message=str(exc))
        log_event(
            "enrich.failed",
            level=40,
            source_id=source_id,
            job_id=job_id,
            stage="enrich",
            status="failed",
            reason=str(exc),
        )
        raise


def admin_rerun_enrichment(*, source_id: int, force: bool = False) -> EnrichmentRunResult:
    source = get_source_by_id(source_id)
    if source is None:
        raise ValueError(f"Source {source_id} not found")
    if source.enrichment_status == "processing" and not force:
        raise ValueError(f"Source {source_id} enrichment is already processing; rerun with force to override")
    if source.ingestion_status not in {"chunked", "embedded"}:
        raise ValueError(f"Source {source_id} must be chunked or embedded before enrichment rerun")

    chunks = get_chunks_for_enrichment(source_id)
    if not chunks:
        raise ValueError(f"Source {source_id} has no chunks available for enrichment rerun")

    source_part_ids = {chunk.get("source_part_id") for chunk in chunks if chunk.get("source_part_id") is not None}
    remove_source_metadata_sections(source_id, ["graph", "temporal"])
    update_source_status(source_id, enrichment_status="processing")
    log_event("admin.enrich.started", source_id=source_id, stage="admin_enrich", status="processing")
    try:
        result = run_post_ingestion_enrichment(
            source_id=source_id,
            source_part_count=len(source_part_ids),
            chunk_count=len(chunks),
            record_job=True,
        )
        update_source_status(source_id, enrichment_status="completed")
        log_event(
            "admin.enrich.completed",
            source_id=source_id,
            job_id=result.job_id,
            stage="admin_enrich",
            status="completed",
            reason=result.reason,
        )
        return result
    except Exception:
        update_source_status(source_id, enrichment_status="failed")
        log_event("admin.enrich.failed", level=40, source_id=source_id, stage="admin_enrich", status="failed")
        raise
