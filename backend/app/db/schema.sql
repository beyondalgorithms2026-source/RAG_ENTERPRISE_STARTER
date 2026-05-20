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
CREATE INDEX IF NOT EXISTS corpora_created_at_idx ON corpora(created_at);
CREATE INDEX IF NOT EXISTS auth_users_external_user_id_idx ON auth_users(external_user_id);
CREATE INDEX IF NOT EXISTS auth_groups_name_idx ON auth_groups(name);
CREATE INDEX IF NOT EXISTS user_group_memberships_group_id_idx ON user_group_memberships(group_id);
CREATE INDEX IF NOT EXISTS document_acl_group_id_idx ON document_acl(group_id);

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
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS admin_audit_events_created_at_idx ON admin_audit_events(created_at);
CREATE INDEX IF NOT EXISTS admin_audit_events_actor_idx ON admin_audit_events(actor_external_user_id);
CREATE INDEX IF NOT EXISTS admin_audit_events_action_idx ON admin_audit_events(action);
CREATE INDEX IF NOT EXISTS admin_audit_events_resource_idx ON admin_audit_events(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS admin_audit_events_source_idx ON admin_audit_events(source_id);
CREATE INDEX IF NOT EXISTS admin_audit_events_corpus_idx ON admin_audit_events(corpus_name);
CREATE INDEX IF NOT EXISTS admin_audit_events_job_idx ON admin_audit_events(job_kind, job_id);
CREATE INDEX IF NOT EXISTS admin_audit_events_trace_idx ON admin_audit_events(trace_id);

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
