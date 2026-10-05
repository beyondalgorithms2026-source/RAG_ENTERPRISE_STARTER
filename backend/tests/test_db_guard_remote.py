import os
import unittest
from unittest import mock

from tests import db_guard
from tests.db_guard import remote_database_reason

SUPABASE = "postgresql://u:p@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"


class RemoteDatabaseGuardTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("RAG_TEST_ALLOW_REMOTE_DB", None)
        os.environ.pop("RAG_REQUIRE_DB", None)

    def test_local_hosts_are_allowed(self):
        for url in (
            "postgresql://u:p@localhost:55432/db",
            "postgresql://u:p@127.0.0.1:55432/db",
            "postgresql://u:p@[::1]:5432/db",
            "postgresql://u:p@postgres:5432/db",
            "postgresql://u:p@pg.localhost/db",
        ):
            self.assertEqual(remote_database_reason(url), "", url)

    def test_hosted_database_is_refused(self):
        reason = remote_database_reason(SUPABASE)
        self.assertIn("pooler.supabase.com", reason)
        self.assertNotIn(":p@", reason)

    def test_explicit_opt_in_allows_remote(self):
        os.environ["RAG_TEST_ALLOW_REMOTE_DB"] = "1"
        self.assertEqual(remote_database_reason(SUPABASE), "")

    def test_remote_database_is_never_connected_to(self):
        with (
            mock.patch.object(db_guard, "_status", None),
            mock.patch("app.core.config.settings.DATABASE_URL", SUPABASE),
            mock.patch("sqlalchemy.engine.Engine.connect") as connect,
        ):
            with self.assertRaises(unittest.SkipTest):
                db_guard.require_database()
            os.environ["RAG_REQUIRE_DB"] = "1"
            with self.assertRaises(AssertionError):
                db_guard.require_database()
            connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
