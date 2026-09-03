# Internal Metadata Contracts

Active technical reference.

See also:
- [docs/README.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/README.md)
- [docs/architecture_overview.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/architecture_overview.md)

This document records the current internal JSON contracts relied on by the codebase after M19. These are implementation-facing contracts, not public API contracts.

Purpose:
- make implicit metadata assumptions explicit
- reduce accidental breakage in later milestones
- clarify merge/update expectations for source and chunk metadata

## Contract Rules

- Source metadata is stored in `sources.source_metadata_json`.
- Chunk metadata is stored across `chunks.entities_json`, `chunks.relations_json`, `chunks.temporal_json`, and `chunks.provenance_json`.
- Dict sections should be merged conservatively.
- Lists are replacement-valued, not deep-merged.
- Unknown keys may exist, but core readers assume the required keys below when a section is present.

## `sources.source_metadata_json["graph"]`

Produced by:
- `backend/app/graph/graph_index.py`
- `backend/app/graph/graph_store.py`
- persisted via `backend/app/db/repo_sources.py`

Expected shape:
- `artifact_version: str`
- `build_status: str`
- `build_reason: str`
- `storage_backend: str`
- `built_from_source_hash: str | null`
- `stats: object`
- `snapshot: object`
- `provenance: object`

Expected `stats` fields in current code:
- `source_id`
- `input_chunk_count`
- `enriched_chunk_count`
- `node_count`
- `edge_count`
- `entity_type_counts`
- `relation_type_counts`

Expected `snapshot` fields:
- `artifact_version`
- `source_id`
- `built_at`
- `nodes`
- `edges`

Node expectations:
- `node_id`
- `canonical_name`
- `entity_type`
- `ontology_tags`
- `aliases`
- `mention_count`
- `chunk_refs`

Edge expectations:
- `edge_id`
- `subject`
- `relation_type`
- `object`
- `evidence_count`
- `chunk_refs`

`chunk_refs` are lightweight only:
- `chunk_id`
- `source_part_id`
- `chunk_index`
- `locator`

## `sources.source_metadata_json["temporal"]`

Produced by:
- `backend/app/graph/temporal.py`
- `backend/app/ingestion/enrichment.py`

Expected shape:
- `artifact_version: str`
- `built_from_source_hash: str | null`
- `build_status: str`
- `date_bounds: object | null`
- `effective_window: object | null`
- `document_version_refs: list`
- `fallback_reason: str | null`

Expected `date_bounds` fields:
- `earliest`
- `latest`

Expected `effective_window` fields:
- `start`
- `end`
- `confidence`

## `sources.source_metadata_json["lazy_enrichment"]`

Produced by:
- `backend/app/ingestion/enrichment.py`

Expected shape:
- `requested_mode`
- `attempted`
- `triggered`
- `reason`
- `source_hash`
- `requested_at`

Optional current fields:
- `artifacts_current`
- `graph_needed`
- `temporal_needed`
- `graph_current_before`
- `temporal_current_before`
- `chunk_count`
- `source_part_count`
- `wrote_job`
- `job_id`
- `graph_artifact_available_after`
- `temporal_metadata_produced_after`
- `error`
- `fallback_mode`

## `chunks.entities_json`

Produced by:
- `backend/app/graph/extractor.py`
- persisted through `backend/app/db/repo_chunks.py`

Current expected entity item shape:
- `surface_text`
- `canonical_name`
- `entity_type`
- `ontology_tags`
- `aliases`
- `provenance`

Expected `provenance` fields:
- `artifact_version`
- `method`

## `chunks.relations_json`

Produced by:
- `backend/app/graph/extractor.py`

Current expected relation item shape:
- `relation_type`
- `subject`
- `object`
- `subject_surface_text`
- `object_surface_text`
- `evidence_text`
- `provenance`

Expected `provenance` fields:
- `artifact_version`
- `method`

## `chunks.temporal_json`

Produced by:
- `backend/app/graph/temporal.py`

Current expected shape:
- `expressions`
- `normalized_dates`
- `document_version_refs`
- `artifact_version`
- `fallback_reason`
- `effective_window`
- `confidence`

`effective_window` may be `null`.

## `chunks.provenance_json`

Current code uses this as a mixed provenance/debug container.

Current reserved sections:
- `enrichment`
- `temporal`

`provenance_json["enrichment"]` currently carries:
- `artifact_version`
- `reason`
- `entity_count`
- `relation_count`
- `ontology_tags`
- `debug`

`provenance_json["temporal"]` currently carries:
- `artifact_version`
- `reason`
- `confidence`
- `fallback_reason`
- `expression_count`
- `version_reference_count`
- `evidence`

## Merge Semantics

Authoritative merge behavior for source metadata:
- dict + dict => recursive merge
- scalar/list patch => replace target value
- unrelated top-level sections must be preserved

This is intended to allow safe coexistence of:
- upload metadata
- graph metadata
- temporal metadata
- lazy enrichment trace metadata

## Hardening Notes

- These contracts are internal and may evolve, but any change should update this file first or alongside code changes.
- Readers in retrieval, router, enrichment, and eval paths assume these sections are present in approximately the shapes documented here.
