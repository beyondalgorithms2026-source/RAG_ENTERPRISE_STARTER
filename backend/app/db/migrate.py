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
