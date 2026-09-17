from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from app.auth.context import reset_current_user, set_current_user
from app.core.config import settings
from app.core_rag.retrieval import SearchRequest, perform_search
from app.db.db import engine
from app.db.migrate import run_migrations
from app.seed.public_demo import seed_public_demo
from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / "corpus"
if str(CORPUS_DIR) not in sys.path:
    sys.path.insert(0, str(CORPUS_DIR))

from generate_corpus import write_corpus  # noqa: E402
from library import DOCUMENTS  # noqa: E402


def setUpModule():
    from tests.db_guard import require_database

    require_database()


class PublicDemoSeedIntegrationP16Tests(unittest.TestCase):
    def setUp(self):
        run_migrations()
        self.original_strategy = settings.ACCESS_STRATEGY
        self.original_auth_mode = settings.AUTH_MODE
        settings.ACCESS_STRATEGY = "document_acl_with_time_bound_grants"
        settings.AUTH_MODE = "none"
        self.temp_dir = tempfile.TemporaryDirectory(prefix="b004-p16-seed-")
        self.corpus_path = Path(self.temp_dir.name)
        self.seed_paths = [self.corpus_path]
        write_corpus(self.corpus_path, DOCUMENTS)

    def tearDown(self):
        with engine.begin() as conn:
            for path in self.seed_paths:
                conn.execute(
                    text("DELETE FROM sources WHERE storage_path LIKE :prefix"),
                    {"prefix": f"{path}%"},
                )
        self.temp_dir.cleanup()
        settings.ACCESS_STRATEGY = self.original_strategy
        settings.AUTH_MODE = self.original_auth_mode

    def test_second_seed_is_idempotent_and_changed_hash_rechunks_one_source(self):
        first = seed_public_demo(self.corpus_path, embed=False)
        second = seed_public_demo(self.corpus_path, embed=False)
        self.assertEqual(first["sources"], 28)
        self.assertEqual(second["unchanged"], 28)
        self.assertEqual(second["chunks"], 0)

        manifest_path = self.corpus_path / "corpus-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manual_entry = next(
            item
            for item in manifest["documents"]
            if item["slug"] == "northwind-operations-manual-v3.2"
        )
        manual_path = self.corpus_path / manual_entry["filename"]
        changed = manual_path.read_text(encoding="utf-8") + "\nEditorial test amendment.\n"
        manual_path.write_text(changed, encoding="utf-8")
        manual_entry["content_sha256"] = hashlib.sha256(changed.encode("utf-8")).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        third = seed_public_demo(self.corpus_path, embed=False)
        self.assertEqual(third["unchanged"], 27)
        self.assertGreater(third["chunks"], 0)

    def test_anonymous_document_acl_can_retrieve_public_manual(self):
        seed_public_demo(self.corpus_path, embed=False)
        token = set_current_user(None)
        try:
            response = perform_search(
                SearchRequest(
                    question="cash advances limited 300 employee 10 Working Days",
                    k=10,
                    mode="keyword",
                )
            )
        finally:
            reset_current_user(token)
        self.assertTrue(
            any(
                item.file_name == "northwind-operations-manual-v3.2.md"
                and "€300" in item.snippet
                and "10 Working Days" in item.snippet
                for item in response.results
            )
        )

    def test_seed_identity_is_stable_across_two_filesystem_roots(self):
        seed_public_demo(self.corpus_path, embed=False)
        second_temp = tempfile.TemporaryDirectory(prefix="b004-p16-seed-second-")
        self.addCleanup(second_temp.cleanup)
        second_path = Path(second_temp.name)
        self.seed_paths.append(second_path)
        write_corpus(second_path, DOCUMENTS)

        second = seed_public_demo(second_path, embed=False)

        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT source_metadata_json->>'source_file' AS source_file, COUNT(*)
                    FROM sources
                    WHERE source_metadata_json->>'seed_pack' = 'public_demo'
                      AND storage_path LIKE :prefix
                    GROUP BY source_metadata_json->>'source_file'
                    """
                ),
                {"prefix": f"{second_path}%"},
            ).fetchall()
        self.assertEqual(second["sources"], 28)
        self.assertEqual(second["unchanged"], 28)
        self.assertEqual(len(rows), 28)
        self.assertTrue(all(count == 1 for _source_file, count in rows))


if __name__ == "__main__":
    unittest.main()
