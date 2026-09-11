from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from app.auth.context import AuthenticatedUser, reset_current_user, set_current_user
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


class Rt06AclBoundaryP11Tests(unittest.TestCase):
    def setUp(self):
        run_migrations()
        self.original_strategy = settings.ACCESS_STRATEGY
        self.original_auth_mode = settings.AUTH_MODE
        settings.ACCESS_STRATEGY = "document_acl_with_time_bound_grants"
        settings.AUTH_MODE = "dev"
        self.temp_dir = tempfile.TemporaryDirectory(prefix="b004-rt06-")
        self.corpus_path = Path(self.temp_dir.name)
        write_corpus(self.corpus_path, DOCUMENTS)
        seed_public_demo(self.corpus_path, embed=False)

    def tearDown(self):
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM sources WHERE storage_path LIKE :prefix"),
                {"prefix": f"{self.corpus_path}%"},
            )
        self.temp_dir.cleanup()
        settings.ACCESS_STRATEGY = self.original_strategy
        settings.AUTH_MODE = self.original_auth_mode

    @staticmethod
    def _search_as(actor: AuthenticatedUser):
        context_token = set_current_user(actor)
        try:
            return perform_search(
                SearchRequest(
                    question="What is the Band 6 salary range?",
                    k=10,
                    mode="keyword",
                )
            )
        finally:
            reset_current_user(context_token)

    def test_rt06_employee_is_trimmed_while_hr_can_retrieve_same_restricted_source(self):
        employee = AuthenticatedUser(
            user_id="demo-employee",
            email="demo.employee@northwind.example",
            roles=["user"],
            groups=["all-employees"],
        )
        hr_user = AuthenticatedUser(
            user_id="demo-hr",
            email="demo.hr@northwind.example",
            roles=["user"],
            groups=["all-employees", "people-operations"],
        )

        employee_response = self._search_as(employee)
        hr_response = self._search_as(hr_user)

        employee_text = " ".join(
            f"{item.file_name} {item.snippet}" for item in employee_response.results
        ).lower()
        self.assertNotIn("compensation-bands-2026", employee_text)
        self.assertNotIn("76,000 to 98,000", employee_text)

        restricted_results = [
            item for item in hr_response.results if item.file_name == "compensation-bands-2026.md"
        ]
        self.assertTrue(restricted_results, "authorized control must find the seeded source")
        self.assertTrue(
            any("76,000 to 98,000" in item.snippet for item in restricted_results),
            "authorized control must find the restricted Band 6 fact",
        )


if __name__ == "__main__":
    unittest.main()
