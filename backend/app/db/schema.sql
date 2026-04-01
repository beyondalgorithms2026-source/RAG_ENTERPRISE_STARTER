CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS sources (
    id BIGSERIAL PRIMARY KEY,
    file_name TEXT NOT NULL,
    storage_path TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL,
    sensitivity_label TEXT NOT NULL DEFAULT 'internal',
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

CREATE TABLE IF NOT EXISTS profiles (
    id           BIGSERIAL    PRIMARY KEY,
    profile_type TEXT         NOT NULL,
    name         TEXT         NOT NULL,
    config_json  JSONB        NOT NULL DEFAULT '{}'::jsonb,
    is_default   BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (profile_type, name)
);

CREATE TABLE IF NOT EXISTS active_profiles (
    profile_type TEXT        PRIMARY KEY,
    profile_name TEXT        NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS auth_users (
    id BIGSERIAL PRIMARY KEY,
    external_user_id TEXT NOT NULL UNIQUE,
    email TEXT,
    display_name TEXT,
    provider_issuer TEXT,
    user_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS auth_groups (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_group_memberships (
    user_id BIGINT NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    group_id BIGINT NOT NULL REFERENCES auth_groups(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, group_id)
);

CREATE TABLE IF NOT EXISTS document_acl (
    source_id BIGINT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    group_id BIGINT NOT NULL REFERENCES auth_groups(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source_id, group_id)
);

CREATE INDEX IF NOT EXISTS profiles_type_idx ON profiles(profile_type);
CREATE INDEX IF NOT EXISTS auth_users_external_user_id_idx ON auth_users(external_user_id);
CREATE INDEX IF NOT EXISTS auth_groups_name_idx ON auth_groups(name);
CREATE INDEX IF NOT EXISTS user_group_memberships_group_id_idx ON user_group_memberships(group_id);
CREATE INDEX IF NOT EXISTS document_acl_group_id_idx ON document_acl(group_id);

CREATE TABLE IF NOT EXISTS retrieval_traces (
    id              BIGSERIAL    PRIMARY KEY,
    request_id      TEXT         NOT NULL,
    question        TEXT         NOT NULL,
    requested_mode  TEXT,
    resolved_mode   TEXT         NOT NULL,
    retrieval_path  TEXT         NOT NULL,
    candidate_counts JSONB       NOT NULL DEFAULT '{}'::jsonb,
    fallback_reason TEXT,
    answer_path     TEXT,
    latency_ms      JSONB       NOT NULL DEFAULT '{}'::jsonb,
    score_diagnostics JSONB     NOT NULL DEFAULT '[]'::jsonb,
    trace_json      JSONB       NOT NULL DEFAULT '{}'::jsonb,
    active_profiles JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS retrieval_traces_request_id_idx ON retrieval_traces(request_id);
CREATE INDEX IF NOT EXISTS retrieval_traces_created_at_idx ON retrieval_traces(created_at);
