import os
from dataclasses import dataclass
from typing import Callable, Optional

from sqlalchemy import text

from app.core.logging import logger
from app.db.db import engine


@dataclass(frozen=True)
class MigrationStep:
    step_id: str
    description: str
    runner: Callable[[], None]


def _schema_path() -> str:
    return os.path.join(os.path.dirname(__file__), "schema.sql")


def _load_schema_sql() -> str:
    schema_path = _schema_path()
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found at {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as handle:
        return handle.read()


def _apply_canonical_schema(schema_sql: str) -> None:
    logger.info("Running canonical schema migration...")
    with engine.begin() as conn:
        conn.execute(text(schema_sql))
    logger.info("Base schema created successfully.")


def _create_search_tsv_trigger() -> None:
    trigger_sql = """
    CREATE OR REPLACE FUNCTION chunks_search_tsv_update() RETURNS trigger AS $$
    BEGIN
        NEW.search_tsv := to_tsvector('english', COALESCE(NEW.chunk_text, ''));
        RETURN NEW;
    END
    $$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS chunks_search_tsv_trigger ON chunks;

    CREATE TRIGGER chunks_search_tsv_trigger
    BEFORE INSERT OR UPDATE OF chunk_text
    ON chunks
    FOR EACH ROW
    EXECUTE FUNCTION chunks_search_tsv_update();
    """
    with engine.begin() as conn:
        conn.execute(text(trigger_sql))
        conn.execute(text("UPDATE chunks SET search_tsv = to_tsvector('english', COALESCE(chunk_text, '')) WHERE search_tsv IS NULL;"))


def _patch_enrichment_job_artifact_version() -> None:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE enrichment_jobs ADD COLUMN IF NOT EXISTS artifact_version TEXT;"))


def _current_embedding_dimension(conn) -> Optional[int]:
    row = conn.execute(
        text(
            """
            SELECT format_type(a.atttypid, a.atttypmod)
            FROM pg_attribute a
            JOIN pg_class c ON a.attrelid = c.oid
            WHERE c.relname = 'chunks' AND a.attname = 'embedding';
            """
        )
    ).first()
    if not row or not row[0]:
        return None

    raw_type = str(row[0]).strip()
    if not raw_type.startswith("vector(") or not raw_type.endswith(")"):
        return None

    try:
        return int(raw_type[len("vector(") : -1])
    except ValueError:
        return None


def _align_embedding_dimension() -> None:
    try:
        from app.embedding.embedder import get_expected_dim

        expected_dim = get_expected_dim()
    except Exception as exc:
        logger.warning(f"Could not resolve embedding dimension dynamically during migration: {exc}")
        return

    with engine.begin() as conn:
        conn.execute(text("DROP INDEX IF EXISTS chunks_embedding_hnsw;"))
        conn.execute(text("DROP INDEX IF EXISTS chunks_embedding_ivfflat;"))
        current_dim = _current_embedding_dimension(conn)
        if current_dim is not None and current_dim != expected_dim:
            conn.execute(text("UPDATE chunks SET embedding = NULL WHERE embedding IS NOT NULL;"))
            logger.info(
                "Cleared stale chunk embeddings before resizing vector column from %s to %s.",
                current_dim,
                expected_dim,
            )
        conn.execute(text(f"ALTER TABLE chunks ALTER COLUMN embedding TYPE vector({expected_dim});"))
    logger.info(f"Aligned chunks.embedding to vector({expected_dim}).")


def _create_vector_index() -> None:
    with engine.begin() as conn:
        logger.info("Attempting to create HNSW vector index on chunks.embedding...")
        try:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw "
                    "ON chunks USING hnsw (embedding vector_cosine_ops);"
                )
            )
            logger.info("HNSW vector index created successfully.")
            return
        except Exception as exc:
            logger.warning(f"Failed to create HNSW index: {exc}")

    with engine.begin() as conn:
        logger.info("Falling back to IVFFLAT vector index on chunks.embedding...")
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS chunks_embedding_ivfflat "
                "ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
            )
        )
        logger.info("IVFFLAT vector index created successfully.")


def _create_profiles_tables() -> None:
    ddl = """
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
    CREATE INDEX IF NOT EXISTS profiles_type_idx ON profiles(profile_type);
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _create_tuning_config_versions_table() -> None:
    ddl = """
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
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _create_m17_b3_to_m21_tables() -> None:
    ddl = """
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

    CREATE TABLE IF NOT EXISTS semantic_cache_entries (
        id BIGSERIAL PRIMARY KEY,
        normalized_question TEXT NOT NULL,
        query_embedding_json JSONB NOT NULL DEFAULT '[]'::jsonb,
        acl_scope_hash TEXT NOT NULL,
        profile_snapshot_hash TEXT NOT NULL,
        corpus_scope_hash TEXT NOT NULL DEFAULT '',
        retrieval_mode TEXT NOT NULL DEFAULT '',
        answer_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        citations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
        retrieved_chunk_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
        metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        expires_at TIMESTAMPTZ NOT NULL,
        invalidated_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        last_hit_at TIMESTAMPTZ
    );
    CREATE INDEX IF NOT EXISTS semantic_cache_lookup_idx ON semantic_cache_entries(normalized_question, acl_scope_hash, profile_snapshot_hash, corpus_scope_hash, retrieval_mode);
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
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _create_negative_feedback_events_table() -> None:
    ddl = """
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
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _create_m33_semantic_cache_governance_tables() -> None:
    ddl = """
    ALTER TABLE semantic_cache_entries ADD COLUMN IF NOT EXISTS policy_version_id BIGINT;
    ALTER TABLE semantic_cache_entries ADD COLUMN IF NOT EXISTS cache_namespace TEXT NOT NULL DEFAULT '';
    ALTER TABLE semantic_cache_entries ADD COLUMN IF NOT EXISTS corpus_names_json JSONB NOT NULL DEFAULT '[]'::jsonb;
    ALTER TABLE semantic_cache_entries ADD COLUMN IF NOT EXISTS source_revisions_json JSONB NOT NULL DEFAULT '{}'::jsonb;
    ALTER TABLE semantic_cache_entries ADD COLUMN IF NOT EXISTS revision_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb;
    ALTER TABLE semantic_cache_entries ADD COLUMN IF NOT EXISTS answer_path TEXT;
    ALTER TABLE semantic_cache_entries ADD COLUMN IF NOT EXISTS original_latency_ms INTEGER;
    CREATE INDEX IF NOT EXISTS semantic_cache_namespace_lookup_idx
        ON semantic_cache_entries(cache_namespace, normalized_question, acl_scope_hash, profile_snapshot_hash, retrieval_mode);

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
    CREATE INDEX IF NOT EXISTS semantic_cache_policy_versions_status_idx
        ON semantic_cache_policy_versions(status, activated_at DESC);
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
    CREATE INDEX IF NOT EXISTS semantic_cache_policy_events_created_idx
        ON semantic_cache_policy_events(created_at DESC);
    CREATE INDEX IF NOT EXISTS semantic_cache_policy_events_type_idx
        ON semantic_cache_policy_events(event_type, created_at DESC);

    CREATE TABLE IF NOT EXISTS semantic_cache_revisions (
        scope_type TEXT NOT NULL,
        scope_key TEXT NOT NULL,
        revision BIGINT NOT NULL DEFAULT 1,
        reason TEXT,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (scope_type, scope_key)
    );
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _patch_m25_m26_security_columns() -> None:
    ddl = """
    ALTER TABLE admin_audit_events
        ADD COLUMN IF NOT EXISTS previous_event_hash TEXT,
        ADD COLUMN IF NOT EXISTS event_hash TEXT,
        ADD COLUMN IF NOT EXISTS integrity_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb;
    CREATE INDEX IF NOT EXISTS admin_audit_events_event_hash_idx ON admin_audit_events(event_hash);
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _create_corpus_access_grants_table() -> None:
    ddl = """
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
    CREATE INDEX IF NOT EXISTS corpus_access_grants_corpus_idx ON corpus_access_grants(corpus_name);
    CREATE INDEX IF NOT EXISTS corpus_access_grants_user_idx ON corpus_access_grants(grantee_external_user_id);
    CREATE INDEX IF NOT EXISTS corpus_access_grants_email_idx ON corpus_access_grants(grantee_email);
    CREATE INDEX IF NOT EXISTS corpus_access_grants_group_idx ON corpus_access_grants(group_id);
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _create_retrieval_traces_table() -> None:
    ddl = """
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
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _create_acl_tables() -> None:
    ddl = """
    ALTER TABLE sources ADD COLUMN IF NOT EXISTS sensitivity_label TEXT NOT NULL DEFAULT 'internal';
    CREATE INDEX IF NOT EXISTS sources_sensitivity_label_idx ON sources(sensitivity_label);

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
    CREATE INDEX IF NOT EXISTS auth_users_external_user_id_idx ON auth_users(external_user_id);
    CREATE INDEX IF NOT EXISTS auth_groups_name_idx ON auth_groups(name);
    CREATE INDEX IF NOT EXISTS user_group_memberships_group_id_idx ON user_group_memberships(group_id);
    CREATE INDEX IF NOT EXISTS document_acl_group_id_idx ON document_acl(group_id);
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _create_corpora_table() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS corpora (
        name TEXT PRIMARY KEY,
        description TEXT NOT NULL DEFAULT '',
        metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS corpora_created_at_idx ON corpora(created_at);
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _patch_ingestion_queue_tables() -> None:
    ddl = """
    ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 100;
    ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS owner_external_user_id TEXT;
    ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS owner_email TEXT;
    ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS owner_display_name TEXT;
    CREATE INDEX IF NOT EXISTS ingestion_jobs_priority_idx ON ingestion_jobs(priority, created_at, id);
    CREATE INDEX IF NOT EXISTS ingestion_jobs_owner_idx ON ingestion_jobs(owner_external_user_id);

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
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _create_db_connectors_table() -> None:
    ddl = """
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
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _create_tools_approvals_feedback_tables() -> None:
    ddl = """
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
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _create_access_request_tables() -> None:
    ddl = """
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
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _seed_default_profiles() -> None:
    from app.core.config import settings
    from app.db.repo_profiles import seed_default_profiles
    seed_default_profiles(settings)


def _sync_live_tuning_configuration() -> None:
    from app.db.repo_tuning_configs import sync_live_configuration_record

    sync_live_configuration_record()


def _create_generation_usage_events_table() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS generation_usage_events (
        id BIGSERIAL PRIMARY KEY,
        request_id TEXT,
        provider TEXT,
        model TEXT,
        retrieval_mode TEXT,
        answer_path TEXT,
        prompt_tokens INTEGER NOT NULL DEFAULT 0,
        completion_tokens INTEGER NOT NULL DEFAULT 0,
        total_tokens INTEGER NOT NULL DEFAULT 0,
        estimated BOOLEAN NOT NULL DEFAULT FALSE,
        cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        latency_ms INTEGER,
        call_count INTEGER NOT NULL DEFAULT 1,
        over_budget BOOLEAN NOT NULL DEFAULT FALSE,
        actor_external_user_id TEXT,
        actor_email TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS generation_usage_events_model_idx ON generation_usage_events(model, created_at DESC);
    CREATE INDEX IF NOT EXISTS generation_usage_events_mode_idx ON generation_usage_events(retrieval_mode, created_at DESC);
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _create_embedding_swap_runs_table() -> None:
    ddl = """
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
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _add_semantic_cache_similarity_threshold() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE semantic_cache_policy_versions "
                "ADD COLUMN IF NOT EXISTS similarity_threshold DOUBLE PRECISION NOT NULL DEFAULT 0.92;"
            )
        )
        # AR6: similarity lookup ranks stored query embeddings within an already
        # ACL/profile/corpus/mode-scoped candidate set; index the scope columns.
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS semantic_cache_similarity_scope_idx "
                "ON semantic_cache_entries(cache_namespace, acl_scope_hash, profile_snapshot_hash, "
                "corpus_scope_hash, retrieval_mode) WHERE invalidated_at IS NULL;"
            )
        )


def _create_tuning_eval_runs_table() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS tuning_eval_runs (
        id BIGSERIAL PRIMARY KEY,
        run_label TEXT NOT NULL,
        draft_id BIGINT REFERENCES tuning_config_versions(id) ON DELETE SET NULL,
        config_fingerprint TEXT NOT NULL,
        gate_status TEXT NOT NULL,
        gate_aggregates_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        thresholds_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        selected_profiles_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        report_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        sample_size INTEGER,
        duration_s DOUBLE PRECISION,
        actor_external_user_id TEXT,
        actor_email TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS tuning_eval_runs_draft_idx ON tuning_eval_runs(draft_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS tuning_eval_runs_created_idx ON tuning_eval_runs(created_at DESC);

    ALTER TABLE tuning_promotion_events ADD COLUMN IF NOT EXISTS eval_evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb;
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _create_connector_operations_tables() -> None:
    ddl = """
    ALTER TABLE sources ADD COLUMN IF NOT EXISTS last_ingested_at TIMESTAMPTZ;
    ALTER TABLE sources ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ;
    ALTER TABLE sources ADD COLUMN IF NOT EXISTS last_enriched_at TIMESTAMPTZ;
    UPDATE sources
    SET last_ingested_at = COALESCE(last_ingested_at, updated_at)
    WHERE ingestion_status = 'embedded' AND last_ingested_at IS NULL;
    UPDATE sources
    SET last_enriched_at = COALESCE(last_enriched_at, updated_at)
    WHERE enrichment_status = 'completed' AND last_enriched_at IS NULL;

    ALTER TABLE db_connectors ADD COLUMN IF NOT EXISTS schedule_enabled BOOLEAN NOT NULL DEFAULT FALSE;
    ALTER TABLE db_connectors ADD COLUMN IF NOT EXISTS sync_interval_minutes INTEGER NOT NULL DEFAULT 60;
    ALTER TABLE db_connectors ADD COLUMN IF NOT EXISTS next_run_at TIMESTAMPTZ;
    ALTER TABLE db_connectors ADD COLUMN IF NOT EXISTS consecutive_failures INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE db_connectors ADD COLUMN IF NOT EXISTS retry_at TIMESTAMPTZ;
    ALTER TABLE db_connectors ADD COLUMN IF NOT EXISTS last_success_at TIMESTAMPTZ;
    ALTER TABLE db_connectors ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ;
    CREATE INDEX IF NOT EXISTS db_connectors_due_idx ON db_connectors(schedule_enabled, next_run_at);

    CREATE TABLE IF NOT EXISTS connector_sync_runs (
        id BIGSERIAL PRIMARY KEY,
        connector_id BIGINT NOT NULL REFERENCES db_connectors(id) ON DELETE CASCADE,
        trigger_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'running',
        attempt_number INTEGER NOT NULL DEFAULT 1,
        rows_ingested INTEGER NOT NULL DEFAULT 0,
        source_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
        error_message TEXT,
        retry_at TIMESTAMPTZ,
        started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        completed_at TIMESTAMPTZ
    );
    CREATE INDEX IF NOT EXISTS connector_sync_runs_connector_idx
        ON connector_sync_runs(connector_id, started_at DESC);
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _patch_steps() -> list[MigrationStep]:
    return [
        MigrationStep(
            step_id="MIG-P001",
            description="Ensure enrichment_jobs.artifact_version exists",
            runner=_patch_enrichment_job_artifact_version,
        ),
        MigrationStep(
            step_id="MIG-P002",
            description="Install chunks.search_tsv trigger and backfill missing search_tsv values",
            runner=_create_search_tsv_trigger,
        ),
        MigrationStep(
            step_id="MIG-P003",
            description="Align chunks.embedding vector dimension with the configured embedding model",
            runner=_align_embedding_dimension,
        ),
        MigrationStep(
            step_id="MIG-P004",
            description="Create vector index for chunks.embedding with HNSW/IVFFLAT fallback",
            runner=_create_vector_index,
        ),
        MigrationStep(
            step_id="MIG-P005",
            description="Create profiles and active_profiles tables",
            runner=_create_profiles_tables,
        ),
        MigrationStep(
            step_id="MIG-P006",
            description="Seed default profiles from current settings",
            runner=_seed_default_profiles,
        ),
        MigrationStep(
            step_id="MIG-P007",
            description="Create retrieval_traces table for observability",
            runner=_create_retrieval_traces_table,
        ),
        MigrationStep(
            step_id="MIG-P008",
            description="Create authz and ACL tables plus source sensitivity label",
            runner=_create_acl_tables,
        ),
        MigrationStep(
            step_id="MIG-P009",
            description="Create corpora registry table for admin control plane",
            runner=_create_corpora_table,
        ),
        MigrationStep(
            step_id="MIG-P010",
            description="Patch ingestion job tables for queue priority ownership and user escalation requests",
            runner=_patch_ingestion_queue_tables,
        ),
        MigrationStep(
            step_id="MIG-P011",
            description="Create DB connector configuration and sync cursor table",
            runner=_create_db_connectors_table,
        ),
        MigrationStep(
            step_id="MIG-P012",
            description="Create tool invocation, approval workflow, and query feedback tables",
            runner=_create_tools_approvals_feedback_tables,
        ),
        MigrationStep(
            step_id="MIG-P013",
            description="Create access request routing, direct grants, and notification tables",
            runner=_create_access_request_tables,
        ),
        MigrationStep(
            step_id="MIG-P014",
            description="Create tuning configuration version table",
            runner=_create_tuning_config_versions_table,
        ),
        MigrationStep(
            step_id="MIG-P015",
            description="Sync the current live configuration into tuning version storage",
            runner=_sync_live_tuning_configuration,
        ),
        MigrationStep(
            step_id="MIG-P016",
            description="Create M17.b.3-M21 promotion, cache, query mining, and governance tables",
            runner=_create_m17_b3_to_m21_tables,
        ),
        MigrationStep(
            step_id="MIG-P017",
            description="Create structured negative feedback event table",
            runner=_create_negative_feedback_events_table,
        ),
        MigrationStep(
            step_id="MIG-P018",
            description="Add M25/M26 audit integrity columns",
            runner=_patch_m25_m26_security_columns,
        ),
        MigrationStep(
            step_id="MIG-P019",
            description="Create corpus-level access grants for M28 access strategies",
            runner=_create_corpus_access_grants_table,
        ),
        MigrationStep(
            step_id="MIG-P020",
            description="Create independent governed semantic cache policies, events, and revisions",
            runner=_create_m33_semantic_cache_governance_tables,
        ),
        MigrationStep(
            step_id="MIG-P021",
            description="Create tuning_eval_runs evidence table and promotion-event eval evidence column (AR4)",
            runner=_create_tuning_eval_runs_table,
        ),
        MigrationStep(
            step_id="MIG-P022",
            description="Add semantic cache similarity threshold column and similarity-scope index (AR6)",
            runner=_add_semantic_cache_similarity_threshold,
        ),
        MigrationStep(
            step_id="MIG-P023",
            description="Create embedding_swap_runs lifecycle table for managed reindexing (AR7)",
            runner=_create_embedding_swap_runs_table,
        ),
        MigrationStep(
            step_id="MIG-P024",
            description="Create generation_usage_events table for token/cost governance (AR11)",
            runner=_create_generation_usage_events_table,
        ),
        MigrationStep(
            step_id="MIG-P025",
            description="Create connector scheduling/run history and source freshness timestamps (AR13)",
            runner=_create_connector_operations_tables,
        ),
    ]


def describe_migration_plan() -> list[dict[str, str]]:
    return [{"step_id": step.step_id, "description": step.description} for step in _patch_steps()]


def _ensure_migration_ledger_table() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migration_ledger (
                    step_id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    first_applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    last_applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )


def _record_migration_step(step: MigrationStep) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO schema_migration_ledger (step_id, description)
                VALUES (:step_id, :description)
                ON CONFLICT (step_id)
                DO UPDATE SET description = EXCLUDED.description, last_applied_at = now()
                """
            ),
            {"step_id": step.step_id, "description": step.description},
        )


def recorded_migration_steps() -> list[str]:
    _ensure_migration_ledger_table()
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT step_id FROM schema_migration_ledger ORDER BY step_id ASC")).fetchall()
    return [row[0] for row in rows]


def verify_migration_ledger() -> dict[str, list[str]]:
    """Assert ledger == plan (AR1). Returns the mismatch report; raises on drift."""
    plan_ids = [step.step_id for step in _patch_steps()]
    recorded = set(recorded_migration_steps())
    missing = [step_id for step_id in plan_ids if step_id not in recorded]
    unknown = sorted(recorded - set(plan_ids))
    if missing or unknown:
        raise RuntimeError(
            f"Migration ledger disagrees with the plan: missing={missing} unknown={unknown}. "
            "Run migrations (python -m app.db.migrate) to reconcile."
        )
    return {"plan": plan_ids, "missing": missing, "unknown": unknown}


def _apply_patch_migrations() -> None:
    logger.info("Applying schema-safe patch migrations...")
    _ensure_migration_ledger_table()
    for step in _patch_steps():
        logger.info("Applying patch migration step %s: %s", step.step_id, step.description)
        step.runner()
        _record_migration_step(step)
        logger.info("Completed patch migration step %s", step.step_id)


def run_migrations() -> None:
    schema_sql = _load_schema_sql()
    _apply_canonical_schema(schema_sql)
    _apply_patch_migrations()
    verify_migration_ledger()
    logger.info("Schema migrations completed successfully.")


if __name__ == "__main__":
    run_migrations()
