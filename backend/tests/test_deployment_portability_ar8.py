import threading
import unittest
from pathlib import Path

from app.profiles.models import RerankerProfileConfig, RetrievalProfileConfig
from app.profiles.resolver import current_profile_overrides, get_effective_retrieval, profile_overrides

REPO_ROOT = Path(__file__).resolve().parents[2]


class ProfileOverrideConcurrencyAR8Tests(unittest.TestCase):
    """AR8: sandbox/candidate profiles applied via request-scoped ContextVar
    overrides must never bleed into a concurrent live request (audit: sandbox
    compare monkeypatched module-level resolvers — a concurrency hazard)."""

    def test_override_context_sets_and_resets(self):
        self.assertEqual(current_profile_overrides(), {})
        candidate = RetrievalProfileConfig(top_k_initial=999)
        with profile_overrides(retrieval=candidate):
            self.assertEqual(get_effective_retrieval().top_k_initial, 999)
            self.assertEqual(current_profile_overrides()["retrieval"].top_k_initial, 999)
        self.assertEqual(current_profile_overrides(), {})
        self.assertNotEqual(get_effective_retrieval().top_k_initial, 999)

    def test_override_does_not_bleed_into_concurrent_thread(self):
        candidate = RetrievalProfileConfig(top_k_initial=12345)
        thread_seen = {}
        entered = threading.Event()
        release = threading.Event()

        def live_worker():
            # A separate thread starts from a clean context (ContextVars do not
            # propagate), simulating a concurrent live request.
            entered.set()
            release.wait(timeout=5)
            thread_seen["top_k"] = get_effective_retrieval().top_k_initial

        worker = threading.Thread(target=live_worker)
        with profile_overrides(retrieval=candidate):
            worker.start()
            entered.wait(timeout=5)
            main_inside = get_effective_retrieval().top_k_initial
            release.set()
            worker.join(timeout=5)

        self.assertEqual(main_inside, 12345)  # the sandbox context sees the candidate
        self.assertNotEqual(thread_seen["top_k"], 12345)  # the live thread never does

    def test_sandbox_temporary_helpers_apply_via_overrides(self):
        from app.tuning.sandbox_compare import _temporary_reranker_profile, _temporary_retrieval_profile

        with _temporary_retrieval_profile(RetrievalProfileConfig(top_k_initial=777)):
            with _temporary_reranker_profile(RerankerProfileConfig(top_n=5, enabled=True)):
                from app.profiles.resolver import get_effective_reranker

                self.assertEqual(get_effective_retrieval().top_k_initial, 777)
                self.assertEqual(get_effective_reranker().top_n, 5)
        self.assertNotEqual(get_effective_retrieval().top_k_initial, 777)


class WorkerSafetyAR8Tests(unittest.TestCase):
    def test_refuses_multi_worker_unless_allowed(self):
        from app.core.config import settings
        from app.core.runtime_safety import assert_worker_safety, configured_worker_count

        self.assertEqual(configured_worker_count({"WEB_CONCURRENCY": "1"}), 1)
        self.assertEqual(configured_worker_count({"UVICORN_WORKERS": "4"}), 4)

        original = settings.ALLOW_MULTI_WORKER
        try:
            settings.ALLOW_MULTI_WORKER = False
            assert_worker_safety({"WEB_CONCURRENCY": "1"})  # ok
            with self.assertRaisesRegex(RuntimeError, "single-process"):
                assert_worker_safety({"WEB_CONCURRENCY": "2"})
            settings.ALLOW_MULTI_WORKER = True
            self.assertEqual(assert_worker_safety({"WEB_CONCURRENCY": "2"}), 2)  # explicit override
        finally:
            settings.ALLOW_MULTI_WORKER = original


class DeploymentPortabilityAR8Tests(unittest.TestCase):
    def test_compose_has_no_hardcoded_host_path(self):
        compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertNotIn("/Users/", compose)
        self.assertIn("rag_enterprise_pgdata", compose)  # portable named volume

    def test_readme_and_quickstart_have_no_absolute_machine_paths(self):
        for name in ("README.md", "docs/01_quickstart.md"):
            content = (REPO_ROOT / name).read_text(encoding="utf-8")
            with self.subTest(doc=name):
                self.assertNotIn("/Users/Work", content)


if __name__ == "__main__":
    unittest.main()
