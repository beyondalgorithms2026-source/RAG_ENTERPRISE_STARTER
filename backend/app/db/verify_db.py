import sys

from sqlalchemy import text

from app.core.logging import logger
from app.db.db import engine


def _expected_embedding_dim():
    try:
        from app.embedding.embedder import get_expected_dim

        return get_expected_dim()
    except Exception as exc:
        logger.warning(f"Could not resolve embedding dimension dynamically: {exc}")
        return None


def collect_db_checks() -> dict[str, bool]:
    expected_dim = _expected_embedding_dim()
    checks = {
        "pgvector extension exists": False,
        "sources table exists": False,
        "source_parts table exists": False,
        "chunks table exists": False,
        "ingestion_jobs table exists": False,
        "enrichment_jobs table exists": False,
        "attachments table exists": False,
        "db_connectors table exists": False,
        "connector_requests table exists": False,
        "tool_invocations table exists": False,
        "approval_requests table exists": False,
        "query_feedback table exists": False,
        "enrichment_jobs.artifact_version column exists": False,
        "chunks.embedding column exists": False,
        "chunks.search_tsv column exists": False,
        "chunks.locator_json column exists": False,
        "source_parts.locator_json column exists": False,
        "chunks.embedding dimension matches model": expected_dim is None,
        "keyword index exists on chunks.search_tsv": False,
        "vector index exists on chunks.embedding": False,
    }

    try:
        with engine.connect() as conn:
            if conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector';")).first():
                checks["pgvector extension exists"] = True

            for table_name in (
                "sources", "source_parts", "chunks", "ingestion_jobs", "enrichment_jobs",
                "attachments", "db_connectors", "connector_requests", "tool_invocations",
                "approval_requests", "query_feedback",
            ):
                exists = conn.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename = :table_name;"),
                    {"table_name": table_name},
                ).first()
                checks[f"{table_name} table exists"] = bool(exists)

            chunk_columns = {
                row[0]
                for row in conn.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = 'chunks';
                        """
                    )
                ).fetchall()
            }
            checks["chunks.embedding column exists"] = "embedding" in chunk_columns
            checks["chunks.search_tsv column exists"] = "search_tsv" in chunk_columns
            checks["chunks.locator_json column exists"] = "locator_json" in chunk_columns

            enrichment_job_columns = {
                row[0]
                for row in conn.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = 'enrichment_jobs';
                        """
                    )
                ).fetchall()
            }
            checks["enrichment_jobs.artifact_version column exists"] = "artifact_version" in enrichment_job_columns

            source_part_columns = {
                row[0]
                for row in conn.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = 'source_parts';
                        """
                    )
                ).fetchall()
            }
            checks["source_parts.locator_json column exists"] = "locator_json" in source_part_columns

            if expected_dim is not None:
                res = conn.execute(
                    text(
                        """
                        SELECT format_type(a.atttypid, a.atttypmod)
                        FROM pg_attribute a
                        JOIN pg_class c ON a.attrelid = c.oid
                        WHERE c.relname = 'chunks' AND a.attname = 'embedding';
                        """
                    )
                ).first()
                checks["chunks.embedding dimension matches model"] = bool(res and res[0] == f"vector({expected_dim})")

            keyword_index = conn.execute(
                text(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = 'chunks'
                      AND indexname = 'chunks_search_tsv_gin';
                    """
                )
            ).first()
            checks["keyword index exists on chunks.search_tsv"] = bool(keyword_index)

            vector_index = conn.execute(
                text(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = 'chunks'
                      AND indexname IN ('chunks_embedding_hnsw', 'chunks_embedding_ivfflat');
                    """
                )
            ).first()
            checks["vector index exists on chunks.embedding"] = bool(vector_index)
    except Exception as exc:
        logger.error(f"Error connecting or executing DB verification queries: {exc}")

    return checks


def verify_db() -> None:
    checks = collect_db_checks()

    all_passed = True
    print("\n--- DB VERIFICATION RESULTS ---")
    for check_name, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {check_name}")
        if not passed:
            all_passed = False

    if not all_passed:
        print("\nVerification FAIL. Some checks did not pass.")
        sys.exit(1)

    print("\nVerification SUCCESS. All checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    verify_db()
