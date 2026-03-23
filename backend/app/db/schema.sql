CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS sources (
    id BIGSERIAL PRIMARY KEY,
    file_name TEXT NOT NULL,
    storage_path TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL,
    mime_type TEXT,
    hash_sha256 TEXT NOT NULL,
    file_size_bytes BIGINT,
    ingestion_status TEXT NOT NULL DEFAULT 'pending',
    enrichment_status TEXT NOT NULL DEFAULT 'not_started',
    source_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS source_parts (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    parent_part_id BIGINT REFERENCES source_parts(id) ON DELETE CASCADE,
    part_type TEXT NOT NULL,
    part_index INTEGER NOT NULL DEFAULT 0,
    title TEXT,
    locator_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_text TEXT,
    provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_id, part_type, part_index)
);

CREATE TABLE IF NOT EXISTS chunks (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    source_part_id BIGINT REFERENCES source_parts(id) ON DELETE SET NULL,
    chunk_index INTEGER NOT NULL,
    heading TEXT NOT NULL DEFAULT '',
    section_path TEXT NOT NULL DEFAULT '',
    chunk_text TEXT NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0,
    locator_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    entities_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    relations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    temporal_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    search_tsv tsvector,
    embedding vector(384),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT REFERENCES sources(id) ON DELETE SET NULL,
    status TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT 'queued',
    triggered_by TEXT NOT NULL DEFAULT 'system',
    error_message TEXT,
    job_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS enrichment_jobs (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT REFERENCES sources(id) ON DELETE SET NULL,
    source_part_id BIGINT REFERENCES source_parts(id) ON DELETE SET NULL,
    enrichment_type TEXT NOT NULL,
    artifact_version TEXT,
    status TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT 'queued',
    error_message TEXT,
    job_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS attachments (
    id BIGSERIAL PRIMARY KEY,
    parent_source_id BIGINT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    child_source_id BIGINT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL DEFAULT 'attachment',
    attachment_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (parent_source_id, child_source_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS sources_source_type_idx ON sources(source_type);
CREATE INDEX IF NOT EXISTS sources_ingestion_status_idx ON sources(ingestion_status);
CREATE INDEX IF NOT EXISTS sources_enrichment_status_idx ON sources(enrichment_status);
CREATE INDEX IF NOT EXISTS source_parts_source_id_idx ON source_parts(source_id);
CREATE INDEX IF NOT EXISTS chunks_source_id_idx ON chunks(source_id);
CREATE INDEX IF NOT EXISTS chunks_source_part_id_idx ON chunks(source_part_id);
CREATE INDEX IF NOT EXISTS chunks_search_tsv_gin ON chunks USING gin(search_tsv);
CREATE INDEX IF NOT EXISTS ingestion_jobs_source_id_idx ON ingestion_jobs(source_id);
CREATE INDEX IF NOT EXISTS ingestion_jobs_status_idx ON ingestion_jobs(status);
CREATE INDEX IF NOT EXISTS enrichment_jobs_source_id_idx ON enrichment_jobs(source_id);
CREATE INDEX IF NOT EXISTS enrichment_jobs_source_part_id_idx ON enrichment_jobs(source_part_id);
CREATE INDEX IF NOT EXISTS enrichment_jobs_status_idx ON enrichment_jobs(status);
CREATE INDEX IF NOT EXISTS enrichment_jobs_type_idx ON enrichment_jobs(enrichment_type);
CREATE INDEX IF NOT EXISTS attachments_parent_source_idx ON attachments(parent_source_id);
CREATE INDEX IF NOT EXISTS attachments_child_source_idx ON attachments(child_source_id);
