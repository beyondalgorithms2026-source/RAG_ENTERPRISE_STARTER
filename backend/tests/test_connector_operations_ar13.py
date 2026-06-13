from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import text

from tests.smoke_test_base import SmokeTestBase


class ConnectorOperationsAR13Tests(SmokeTestBase):
    def _delete_connector(self, connector_id: int) -> None:
        from app.db.db import engine

        with engine.begin() as conn:
            conn.execute(text("DELETE FROM db_connectors WHERE id = :connector_id"), {"connector_id": connector_id})

    def test_unreachable_upstream_degrades_health_and_persists_backoff(self):
        from app.connectors.runtime import retry_delay_seconds, run_connector_sync
        from app.core.config import settings
        from app.db.repo_connectors import get_db_connector, list_connector_sync_runs, upsert_db_connector

        connector_id = upsert_db_connector(
            name=f"ar13-unreachable-{uuid4().hex[:8]}",
            connector_type="postgres",
            db_url="postgresql://invalid:invalid@127.0.0.1:1/unreachable",
            table_name="public.missing",
            id_column="id",
            updated_at_column="updated_at",
            text_columns=["body"],
            metadata_columns=[],
            corpus_name="db_rows",
            acl_group_names=[],
            schedule_enabled=True,
            sync_interval_minutes=5,
        )
        original_base = settings.CONNECTOR_RETRY_BASE_SECONDS
        original_max = settings.CONNECTOR_RETRY_MAX_SECONDS
        try:
            settings.CONNECTOR_RETRY_BASE_SECONDS = 2
            settings.CONNECTOR_RETRY_MAX_SECONDS = 30
            self.assertEqual(retry_delay_seconds(0), 2)
            self.assertEqual(retry_delay_seconds(1), 4)
            self.assertEqual(retry_delay_seconds(20), 30)
            with self.assertRaises(Exception):
                run_connector_sync(connector_id, trigger_type="scheduled", row_limit=1)

            connector = get_db_connector(connector_id)
            runs = list_connector_sync_runs(connector_id)
            self.assertEqual(connector.status, "degraded")
            self.assertEqual(connector.consecutive_failures, 1)
            self.assertIsNotNone(connector.retry_at)
            self.assertEqual(runs[0].status, "failed")
            self.assertEqual(runs[0].attempt_number, 1)
            self.assertIsNotNone(runs[0].retry_at)
            self.assertTrue(runs[0].error_message)
        finally:
            settings.CONNECTOR_RETRY_BASE_SECONDS = original_base
            settings.CONNECTOR_RETRY_MAX_SECONDS = original_max
            self._delete_connector(connector_id)

    def test_connector_claim_rejects_duplicate_concurrent_run(self):
        from app.db.repo_connectors import claim_db_connector, upsert_db_connector

        connector_id = upsert_db_connector(
            name=f"ar13-claim-{uuid4().hex[:8]}",
            connector_type="postgres",
            db_url="postgresql://example",
            table_name="public.example",
            id_column="id",
            updated_at_column="updated_at",
            text_columns=["body"],
            metadata_columns=[],
            corpus_name="db_rows",
            acl_group_names=[],
        )
        try:
            self.assertIsNotNone(claim_db_connector(connector_id, lease_seconds=60))
            self.assertIsNone(claim_db_connector(connector_id, lease_seconds=60))
        finally:
            self._delete_connector(connector_id)

    def test_freshness_marks_old_and_missing_sources_visibly(self):
        from app.freshness import source_freshness

        now = datetime.now(timezone.utc)
        stale = SimpleNamespace(
            source_type="pdf",
            source_metadata_json={"freshness_threshold_hours": 24},
            last_ingested_at=now - timedelta(hours=25),
            last_synced_at=None,
            last_enriched_at=now - timedelta(hours=2),
        )
        unknown = SimpleNamespace(
            source_type="pdf",
            source_metadata_json={},
            last_ingested_at=None,
            last_synced_at=None,
            last_enriched_at=None,
        )
        self.assertEqual(source_freshness(stale, now=now)["status"], "stale")
        self.assertEqual(source_freshness(unknown, now=now)["status"], "unknown")

    def test_cached_citation_freshness_is_rehydrated_from_source(self):
        from app.core_rag.answering import CitationItem, _refresh_citation_freshness
        from app.db.db import engine

        source_id = None
        with engine.begin() as conn:
            source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, last_ingested_at, source_metadata_json
                    )
                    VALUES (
                        :file_name, :storage_path, 'txt', :hash_sha256, 1,
                        'embedded', 'not_started', now() - interval '8 days', '{}'::jsonb
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"ar13-cache-{uuid4().hex[:8]}.txt",
                    "storage_path": f"test/ar13-cache-{uuid4().hex}",
                    "hash_sha256": uuid4().hex,
                },
            ).scalar_one()
        try:
            citation = CitationItem(
                citation_id="S1",
                source_id=source_id,
                chunk_id=1,
                file_name="cached.txt",
                source_type="txt",
                heading="Body",
                snippet="cached",
                freshness={"status": "fresh", "threshold_hours": 168},
            )
            refreshed = _refresh_citation_freshness([citation])
            self.assertEqual(refreshed[0].freshness["status"], "stale")
        finally:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM sources WHERE id = :source_id"), {"source_id": source_id})

    def test_source_status_updates_persist_lifecycle_timestamps(self):
        from app.db.db import engine
        from app.db.repo_sources import get_source_by_id, update_source_status

        with engine.begin() as conn:
            source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (:file_name, :storage_path, 'txt', :hash_sha256, 1, 'processing', 'processing', '{}'::jsonb)
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"ar13-lifecycle-{uuid4().hex[:8]}.txt",
                    "storage_path": f"test/ar13-lifecycle-{uuid4().hex}",
                    "hash_sha256": uuid4().hex,
                },
            ).scalar_one()
        try:
            update_source_status(source_id, ingestion_status="embedded", enrichment_status="completed")
            source = get_source_by_id(source_id)
            self.assertIsNotNone(source.last_ingested_at)
            self.assertIsNotNone(source.last_enriched_at)
        finally:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM sources WHERE id = :source_id"), {"source_id": source_id})


if __name__ == "__main__":
    import unittest

    unittest.main()
