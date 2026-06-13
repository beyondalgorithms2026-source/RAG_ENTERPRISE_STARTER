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
    priority INTEGER NOT NULL DEFAULT 100,
    triggered_by TEXT NOT NULL DEFAULT 'system',
    owner_external_user_id TEXT,
    owner_email TEXT,
    owner_display_name TEXT,
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

CREATE TABLE IF NOT EXISTS corpora (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL DEFAULT '',
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS active_profiles (
    profile_type TEXT        PRIMARY KEY,
    profile_name TEXT        NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tuning_config_versions (
    id BIGSERIAL PRIMARY KEY,
    version_label TEXT NOT NULL UNIQUE,
    config_kind TEXT NOT NULL DEFAULT 'candidate',
    status TEXT NOT NULL DEFAULT 'draft',
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    selected_profiles_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    resolved_config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    lineage_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by_external_user_id TEXT,
    created_by_email TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS tuning_config_versions_kind_status_idx ON tuning_config_versions(config_kind, status, created_at DESC);
CREATE INDEX IF NOT EXISTS tuning_config_versions_status_idx ON tuning_config_versions(status, created_at DESC);

CREATE TABLE IF NOT EXISTS tuning_promotion_events (
    id BIGSERIAL PRIMARY KEY,
    promoted_config_id BIGINT REFERENCES tuning_config_versions(id) ON DELETE SET NULL,
    previous_live_version_label TEXT,
    new_live_version_label TEXT NOT NULL,
    action TEXT NOT NULL,
    promotion_note TEXT NOT NULL DEFAULT '',
    selected_profiles_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    rollback_target_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    actor_external_user_id TEXT,
    actor_email TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS tuning_promotion_events_created_idx ON tuning_promotion_events(created_at DESC);

CREATE TABLE IF NOT EXISTS embedding_experiment_runs (
    id BIGSERIAL PRIMARY KEY,
    candidate_config_id BIGINT REFERENCES tuning_config_versions(id) ON DELETE SET NULL,
    basis_embedding_profile TEXT NOT NULL,
    target_embedding_profile TEXT NOT NULL,
    scope_type TEXT NOT NULL,
    locked_source_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'locked',
    warning_acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    confirmation_count INTEGER NOT NULL DEFAULT 0,
    job_id BIGINT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    actor_external_user_id TEXT,
    actor_email TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS embedding_experiment_runs_status_idx ON embedding_experiment_runs(status, created_at DESC);

CREATE TABLE IF NOT EXISTS embedding_experiment_chunks (
    id BIGSERIAL PRIMARY KEY,
    experiment_id BIGINT NOT NULL REFERENCES embedding_experiment_runs(id) ON DELETE CASCADE,
    source_id BIGINT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    chunk_id BIGINT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    embedding_profile TEXT NOT NULL,
    embedding_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (experiment_id, chunk_id)
);

CREATE TABLE IF NOT EXISTS embedding_swap_runs (
    id BIGSERIAL PRIMARY KEY,
    target_profile_name TEXT NOT NULL,
    basis_profile_name TEXT,
    target_model TEXT NOT NULL,
    target_dimension INTEGER NOT NULL,
    source_dimension INTEGER,
    requires_reindex BOOLEAN NOT NULL DEFAULT TRUE,
    status TEXT NOT NULL DEFAULT 'planned',
    total_chunks INTEGER NOT NULL DEFAULT 0,
    embedded_chunks INTEGER NOT NULL DEFAULT 0,
    failed_chunks INTEGER NOT NULL DEFAULT 0,
    verification_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    error TEXT,
    actor_external_user_id TEXT,
    actor_email TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS embedding_swap_runs_status_idx ON embedding_swap_runs(status, created_at DESC);

CREATE TABLE IF NOT EXISTS model_warmup_runs (
    id BIGSERIAL PRIMARY KEY,
    model_type TEXT NOT NULL,
    model_name TEXT NOT NULL,
    status TEXT NOT NULL,
    latency_ms INTEGER,
    error_message TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS model_warmup_runs_model_idx ON model_warmup_runs(model_type, model_name, created_at DESC);

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

CREATE TABLE IF NOT EXISTS corpus_access_grants (
    id BIGSERIAL PRIMARY KEY,
    corpus_name TEXT NOT NULL,
    grantee_external_user_id TEXT,
    grantee_email TEXT,
    group_id BIGINT REFERENCES auth_groups(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        grantee_external_user_id IS NOT NULL
        OR grantee_email IS NOT NULL
        OR group_id IS NOT NULL
    ),
    UNIQUE (corpus_name, grantee_external_user_id, grantee_email, group_id)
);

CREATE INDEX IF NOT EXISTS profiles_type_idx ON profiles(profile_type);
CREATE INDEX IF NOT EXISTS corpora_created_at_idx ON corpora(created_at);
CREATE INDEX IF NOT EXISTS auth_users_external_user_id_idx ON auth_users(external_user_id);
CREATE INDEX IF NOT EXISTS auth_groups_name_idx ON auth_groups(name);
CREATE INDEX IF NOT EXISTS user_group_memberships_group_id_idx ON user_group_memberships(group_id);
CREATE INDEX IF NOT EXISTS document_acl_group_id_idx ON document_acl(group_id);
CREATE INDEX IF NOT EXISTS corpus_access_grants_corpus_idx ON corpus_access_grants(corpus_name);
CREATE INDEX IF NOT EXISTS corpus_access_grants_user_idx ON corpus_access_grants(grantee_external_user_id);
CREATE INDEX IF NOT EXISTS corpus_access_grants_email_idx ON corpus_access_grants(grantee_email);
CREATE INDEX IF NOT EXISTS corpus_access_grants_group_idx ON corpus_access_grants(group_id);

CREATE TABLE IF NOT EXISTS source_access_contacts (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    contact_role TEXT NOT NULL,
    contact_external_user_id TEXT,
    contact_email TEXT,
    contact_display_name TEXT,
    contact_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS source_access_contacts_source_role_idx ON source_access_contacts(source_id, contact_role);
CREATE INDEX IF NOT EXISTS source_access_contacts_email_idx ON source_access_contacts(contact_email);

CREATE TABLE IF NOT EXISTS access_requests (
    id BIGSERIAL PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'submitted',
    question TEXT NOT NULL,
    business_reason TEXT NOT NULL DEFAULT '',
    source_hint TEXT,
    request_id TEXT,
    answer_path TEXT,
    requester_external_user_id TEXT,
    requester_email TEXT,
    requester_display_name TEXT,
    requester_manager_external_user_id TEXT,
    requester_manager_email TEXT,
    requester_manager_display_name TEXT,
    approved_duration_hours INTEGER,
    business_approval_status TEXT,
    business_approval_decision TEXT,
    business_approval_reason TEXT,
    business_approved_at TIMESTAMPTZ,
    granted_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    granted_by_external_user_id TEXT,
    granted_by_email TEXT,
    review_reason TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS access_requests_status_idx ON access_requests(status, created_at DESC);
CREATE INDEX IF NOT EXISTS access_requests_requester_idx ON access_requests(requester_external_user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS access_request_targets (
    id BIGSERIAL PRIMARY KEY,
    access_request_id BIGINT NOT NULL REFERENCES access_requests(id) ON DELETE CASCADE,
    source_id BIGINT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'mapped',
    mapped_by_external_user_id TEXT,
    mapped_by_email TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (access_request_id, source_id)
);
CREATE INDEX IF NOT EXISTS access_request_targets_request_idx ON access_request_targets(access_request_id, created_at DESC);

CREATE TABLE IF NOT EXISTS access_request_routing (
    id BIGSERIAL PRIMARY KEY,
    access_request_id BIGINT NOT NULL UNIQUE REFERENCES access_requests(id) ON DELETE CASCADE,
    admin_coordinator_external_user_id TEXT,
    admin_coordinator_email TEXT,
    business_approver_external_user_id TEXT,
    business_approver_email TEXT,
    business_approver_display_name TEXT,
    acl_manager_external_user_id TEXT,
    acl_manager_email TEXT,
    acl_manager_display_name TEXT,
    requester_manager_external_user_id TEXT,
    requester_manager_email TEXT,
    requester_manager_display_name TEXT,
    routed_at TIMESTAMPTZ,
    responded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_source_access_grants (
    id BIGSERIAL PRIMARY KEY,
    access_request_id BIGINT REFERENCES access_requests(id) ON DELETE SET NULL,
    source_id BIGINT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    grantee_external_user_id TEXT,
    grantee_email TEXT,
    grant_reason TEXT NOT NULL DEFAULT '',
    granted_by_external_user_id TEXT,
    granted_by_email TEXT,
    starts_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    revoked_by_external_user_id TEXT,
    revoked_by_email TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS user_source_access_grants_user_idx ON user_source_access_grants(grantee_external_user_id, expires_at DESC);
CREATE INDEX IF NOT EXISTS user_source_access_grants_email_idx ON user_source_access_grants(grantee_email, expires_at DESC);
CREATE INDEX IF NOT EXISTS user_source_access_grants_source_idx ON user_source_access_grants(source_id, expires_at DESC);

CREATE TABLE IF NOT EXISTS notification_events (
    id BIGSERIAL PRIMARY KEY,
    access_request_id BIGINT REFERENCES access_requests(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    recipient_external_user_id TEXT,
    recipient_email TEXT,
    recipient_display_name TEXT,
    recipient_role TEXT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    email_subject TEXT,
    email_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'unread',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    read_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS notification_events_recipient_idx ON notification_events(recipient_external_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS notification_events_email_idx ON notification_events(recipient_email, created_at DESC);

CREATE TABLE IF NOT EXISTS approval_inbox_items (
    id BIGSERIAL PRIMARY KEY,
    access_request_id BIGINT NOT NULL REFERENCES access_requests(id) ON DELETE CASCADE,
    routing_id BIGINT REFERENCES access_request_routing(id) ON DELETE CASCADE,
    assigned_external_user_id TEXT,
    assigned_email TEXT,
    assigned_display_name TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    decision TEXT,
    decision_reason TEXT,
    request_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    resolution_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS approval_inbox_items_assignee_idx ON approval_inbox_items(assigned_external_user_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS approval_inbox_items_email_idx ON approval_inbox_items(assigned_email, status, created_at DESC);

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

CREATE TABLE IF NOT EXISTS admin_audit_events (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    action TEXT NOT NULL,
    outcome TEXT NOT NULL DEFAULT 'completed',
    actor_external_user_id TEXT,
    actor_email TEXT,
    actor_roles_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    resource_type TEXT,
    resource_id TEXT,
    resource_name TEXT,
    source_id BIGINT,
    corpus_name TEXT,
    profile_type TEXT,
    profile_name TEXT,
    job_kind TEXT,
    job_id BIGINT,
    trace_id BIGINT,
    request_id TEXT,
    before_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    after_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    event_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    previous_event_hash TEXT,
    event_hash TEXT,
    integrity_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE admin_audit_events
    ADD COLUMN IF NOT EXISTS previous_event_hash TEXT,
    ADD COLUMN IF NOT EXISTS event_hash TEXT,
    ADD COLUMN IF NOT EXISTS integrity_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS admin_audit_events_created_at_idx ON admin_audit_events(created_at);
CREATE INDEX IF NOT EXISTS admin_audit_events_actor_idx ON admin_audit_events(actor_external_user_id);
CREATE INDEX IF NOT EXISTS admin_audit_events_action_idx ON admin_audit_events(action);
CREATE INDEX IF NOT EXISTS admin_audit_events_resource_idx ON admin_audit_events(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS admin_audit_events_source_idx ON admin_audit_events(source_id);
CREATE INDEX IF NOT EXISTS admin_audit_events_corpus_idx ON admin_audit_events(corpus_name);
CREATE INDEX IF NOT EXISTS admin_audit_events_job_idx ON admin_audit_events(job_kind, job_id);
CREATE INDEX IF NOT EXISTS admin_audit_events_trace_idx ON admin_audit_events(trace_id);
CREATE INDEX IF NOT EXISTS admin_audit_events_event_hash_idx ON admin_audit_events(event_hash);

CREATE TABLE IF NOT EXISTS ingestion_priority_requests (
    id BIGSERIAL PRIMARY KEY,
    job_id BIGINT NOT NULL REFERENCES ingestion_jobs(id) ON DELETE CASCADE,
    source_id BIGINT REFERENCES sources(id) ON DELETE SET NULL,
    requester_external_user_id TEXT,
    requester_email TEXT,
    requester_display_name TEXT,
    requested_priority INTEGER NOT NULL DEFAULT 200,
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'submitted',
    review_reason TEXT,
    reviewed_by_external_user_id TEXT,
    reviewed_by_email TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ingestion_priority_requests_job_idx ON ingestion_priority_requests(job_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ingestion_priority_requests_status_idx ON ingestion_priority_requests(status, created_at DESC);
CREATE INDEX IF NOT EXISTS ingestion_priority_requests_requester_idx ON ingestion_priority_requests(requester_external_user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS db_connectors (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    connector_type TEXT NOT NULL,
    db_url TEXT NOT NULL,
    table_name TEXT NOT NULL,
    id_column TEXT NOT NULL DEFAULT 'id',
    updated_at_column TEXT NOT NULL DEFAULT 'updated_at',
    text_columns_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata_columns_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    corpus_name TEXT,
    acl_group_names_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'configured',
    last_cursor_updated_at TEXT,
    last_cursor_id TEXT,
    last_run_at TIMESTAMPTZ,
    last_error TEXT,
    connector_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS db_connectors_type_idx ON db_connectors(connector_type);
CREATE INDEX IF NOT EXISTS db_connectors_status_idx ON db_connectors(status);

CREATE TABLE IF NOT EXISTS connector_requests (
    id BIGSERIAL PRIMARY KEY,
    connector_type TEXT NOT NULL,
    requested_system TEXT NOT NULL,
    business_reason TEXT NOT NULL DEFAULT '',
    requested_scope_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'submitted',
    review_reason TEXT,
    requester_external_user_id TEXT,
    requester_email TEXT,
    requester_display_name TEXT,
    reviewed_by_external_user_id TEXT,
    reviewed_by_email TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS connector_requests_status_idx ON connector_requests(status, created_at DESC);
CREATE INDEX IF NOT EXISTS connector_requests_requester_idx ON connector_requests(requester_external_user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS tool_invocations (
    id BIGSERIAL PRIMARY KEY,
    tool_name TEXT NOT NULL,
    status TEXT NOT NULL,
    actor_external_user_id TEXT,
    actor_email TEXT,
    actor_roles_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    corpus_name TEXT,
    request_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    denial_reason TEXT,
    approval_request_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS tool_invocations_tool_status_idx ON tool_invocations(tool_name, status, created_at DESC);

CREATE TABLE IF NOT EXISTS approval_requests (
    id BIGSERIAL PRIMARY KEY,
    approval_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    reason TEXT NOT NULL DEFAULT '',
    requester_external_user_id TEXT,
    requester_email TEXT,
    requester_display_name TEXT,
    requested_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    response_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewed_by_external_user_id TEXT,
    reviewed_by_email TEXT,
    review_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS approval_requests_status_idx ON approval_requests(status, created_at DESC);
CREATE INDEX IF NOT EXISTS approval_requests_requester_idx ON approval_requests(requester_external_user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS query_feedback (
    id BIGSERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    feedback_type TEXT NOT NULL,
    rating TEXT,
    reason TEXT NOT NULL DEFAULT '',
    suggested_source TEXT,
    request_id TEXT,
    answer_path TEXT,
    actor_external_user_id TEXT,
    actor_email TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS query_feedback_type_idx ON query_feedback(feedback_type, created_at DESC);
CREATE INDEX IF NOT EXISTS query_feedback_request_idx ON query_feedback(request_id);

CREATE TABLE IF NOT EXISTS negative_feedback_events (
    id BIGSERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    answer_text TEXT NOT NULL DEFAULT '',
    negative_reason TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    request_id TEXT,
    answer_path TEXT,
    used_chunks_count INTEGER NOT NULL DEFAULT 0,
    actor_external_user_id TEXT,
    actor_email TEXT,
    citations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    cited_source_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    cited_chunk_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    active_profile_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS negative_feedback_events_reason_idx ON negative_feedback_events(negative_reason, created_at DESC);
CREATE INDEX IF NOT EXISTS negative_feedback_events_request_idx ON negative_feedback_events(request_id);
CREATE INDEX IF NOT EXISTS negative_feedback_events_actor_idx ON negative_feedback_events(actor_external_user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS semantic_cache_entries (
    id BIGSERIAL PRIMARY KEY,
    policy_version_id BIGINT,
    cache_namespace TEXT NOT NULL DEFAULT '',
    normalized_question TEXT NOT NULL,
    query_embedding_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    acl_scope_hash TEXT NOT NULL,
    profile_snapshot_hash TEXT NOT NULL,
    corpus_scope_hash TEXT NOT NULL DEFAULT '',
    corpus_names_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_revisions_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    revision_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    retrieval_mode TEXT NOT NULL DEFAULT '',
    answer_path TEXT,
    original_latency_ms INTEGER,
    answer_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    citations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    retrieved_chunk_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    expires_at TIMESTAMPTZ NOT NULL,
    invalidated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_hit_at TIMESTAMPTZ
);
ALTER TABLE semantic_cache_entries
    ADD COLUMN IF NOT EXISTS policy_version_id BIGINT,
    ADD COLUMN IF NOT EXISTS cache_namespace TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS corpus_names_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS source_revisions_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS revision_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS answer_path TEXT,
    ADD COLUMN IF NOT EXISTS original_latency_ms INTEGER;
CREATE INDEX IF NOT EXISTS semantic_cache_lookup_idx ON semantic_cache_entries(normalized_question, acl_scope_hash, profile_snapshot_hash, corpus_scope_hash, retrieval_mode);
CREATE INDEX IF NOT EXISTS semantic_cache_namespace_lookup_idx ON semantic_cache_entries(cache_namespace, normalized_question, acl_scope_hash, profile_snapshot_hash, retrieval_mode);
CREATE INDEX IF NOT EXISTS semantic_cache_expiry_idx ON semantic_cache_entries(expires_at, invalidated_at);

CREATE TABLE IF NOT EXISTS semantic_cache_hits (
    id BIGSERIAL PRIMARY KEY,
    cache_entry_id BIGINT REFERENCES semantic_cache_entries(id) ON DELETE SET NULL,
    hit_type TEXT NOT NULL,
    latency_saved_ms INTEGER,
    actor_external_user_id TEXT,
    actor_email TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS semantic_cache_hits_created_idx ON semantic_cache_hits(created_at DESC);

CREATE TABLE IF NOT EXISTS semantic_cache_policies (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    justification TEXT NOT NULL DEFAULT '',
    owner TEXT NOT NULL DEFAULT '',
    review_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'draft',
    active_version_id BIGINT,
    created_by_external_user_id TEXT,
    created_by_email TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS semantic_cache_policy_versions (
    id BIGSERIAL PRIMARY KEY,
    policy_id BIGINT NOT NULL REFERENCES semantic_cache_policies(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    cache_namespace TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'draft',
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    match_mode TEXT NOT NULL DEFAULT 'exact',
    similarity_threshold DOUBLE PRECISION NOT NULL DEFAULT 0.92,
    ttl_seconds INTEGER NOT NULL DEFAULT 900,
    max_active_entries INTEGER NOT NULL DEFAULT 1000,
    allow_corpora_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    deny_corpora_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    allow_groups_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    deny_groups_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    allow_questions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    deny_questions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    safety_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by_external_user_id TEXT,
    created_by_email TEXT,
    approved_by_external_user_id TEXT,
    approved_by_email TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    activated_at TIMESTAMPTZ,
    UNIQUE (policy_id, version_number)
);
CREATE INDEX IF NOT EXISTS semantic_cache_policy_versions_status_idx ON semantic_cache_policy_versions(status, activated_at DESC);

DO $$ BEGIN
    ALTER TABLE semantic_cache_policies
        ADD CONSTRAINT semantic_cache_policies_active_version_fk
        FOREIGN KEY (active_version_id) REFERENCES semantic_cache_policy_versions(id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE semantic_cache_entries
        ADD CONSTRAINT semantic_cache_entries_policy_version_fk
        FOREIGN KEY (policy_version_id) REFERENCES semantic_cache_policy_versions(id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS semantic_cache_policy_events (
    id BIGSERIAL PRIMARY KEY,
    policy_version_id BIGINT REFERENCES semantic_cache_policy_versions(id) ON DELETE SET NULL,
    cache_entry_id BIGINT REFERENCES semantic_cache_entries(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    reason TEXT,
    latency_saved_ms INTEGER,
    estimated_cost_saved_usd NUMERIC(14, 6),
    actor_external_user_id TEXT,
    actor_email TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS semantic_cache_policy_events_created_idx ON semantic_cache_policy_events(created_at DESC);
CREATE INDEX IF NOT EXISTS semantic_cache_policy_events_type_idx ON semantic_cache_policy_events(event_type, created_at DESC);

CREATE TABLE IF NOT EXISTS semantic_cache_revisions (
    scope_type TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    revision BIGINT NOT NULL DEFAULT 1,
    reason TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (scope_type, scope_key)
);

CREATE TABLE IF NOT EXISTS query_events (
    id BIGSERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    normalized_question TEXT NOT NULL,
    event_type TEXT NOT NULL,
    answer_path TEXT,
    request_id TEXT,
    retrieval_mode TEXT,
    latency_ms INTEGER,
    feedback_type TEXT,
    actor_external_user_id TEXT,
    actor_email TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS query_events_normalized_idx ON query_events(normalized_question, created_at DESC);
CREATE INDEX IF NOT EXISTS query_events_type_idx ON query_events(event_type, created_at DESC);

CREATE TABLE IF NOT EXISTS query_failure_clusters (
    id BIGSERIAL PRIMARY KEY,
    cluster_key TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    query_count INTEGER NOT NULL DEFAULT 0,
    sample_questions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    annotation_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS derived_eval_packs (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    cluster_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    cases_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'draft',
    created_by_external_user_id TEXT,
    created_by_email TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS access_request_risk_signals (
    id BIGSERIAL PRIMARY KEY,
    requester_external_user_id TEXT,
    requester_email TEXT,
    signal_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    question TEXT,
    access_request_id BIGINT REFERENCES access_requests(id) ON DELETE SET NULL,
    evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS access_request_risk_requester_idx ON access_request_risk_signals(requester_external_user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS user_governance_restrictions (
    id BIGSERIAL PRIMARY KEY,
    user_external_user_id TEXT,
    user_email TEXT,
    restriction_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    reason TEXT NOT NULL DEFAULT '',
    starts_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    created_by_external_user_id TEXT,
    created_by_email TEXT,
    lifted_by_external_user_id TEXT,
    lifted_by_email TEXT,
    lifted_reason TEXT,
    lifted_at TIMESTAMPTZ,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS user_governance_restrictions_user_idx ON user_governance_restrictions(user_external_user_id, status, restriction_type);

CREATE TABLE IF NOT EXISTS user_governance_events (
    id BIGSERIAL PRIMARY KEY,
    user_external_user_id TEXT,
    user_email TEXT,
    action TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    restriction_id BIGINT REFERENCES user_governance_restrictions(id) ON DELETE SET NULL,
    actor_external_user_id TEXT,
    actor_email TEXT,
    event_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
