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


def _seed_default_profiles() -> None:
    from app.core.config import settings
    from app.db.repo_profiles import seed_default_profiles
    seed_default_profiles(settings)


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
    ]


def describe_migration_plan() -> list[dict[str, str]]:
    return [{"step_id": step.step_id, "description": step.description} for step in _patch_steps()]


def _apply_patch_migrations() -> None:
    logger.info("Applying schema-safe patch migrations...")
    for step in _patch_steps():
        logger.info("Applying patch migration step %s: %s", step.step_id, step.description)
        step.runner()
        logger.info("Completed patch migration step %s", step.step_id)


def run_migrations() -> None:
    schema_sql = _load_schema_sql()
    _apply_canonical_schema(schema_sql)
    _apply_patch_migrations()
    logger.info("Schema migrations completed successfully.")


if __name__ == "__main__":
    run_migrations()
