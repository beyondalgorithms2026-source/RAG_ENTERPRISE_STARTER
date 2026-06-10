import unittest
from uuid import uuid4

from sqlalchemy import text

from app.auth.context import AuthenticatedUser
from app.db.db import engine
from app.db.migrate import run_migrations
from app.db.repo_semantic_cache import (
    bump_cache_revision,
    get_cache_entry,
    policy_allows,
    store_cache_entry,
)
from app.db.repo_semantic_cache_policies import (
    activate_policy,
    create_policy,
    disable_policy,
    get_policy,
    validate_policy_config,
)
from app.db.repo_tuning_configs import list_candidate_drafts


class SemanticCacheGovernanceM33Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_migrations()

    def setUp(self):
        self.actor = AuthenticatedUser(
            user_id=f"m33-{uuid4().hex[:8]}",
            email="m33-admin@example.test",
            roles=["admin"],
            groups=["employees"],
        )
        self.policy_ids: list[int] = []

    def tearDown(self):
        if not self.policy_ids:
            return
        with engine.begin() as conn:
            version_ids = [
                int(row[0])
                for row in conn.execute(
                    text("SELECT id FROM semantic_cache_policy_versions WHERE policy_id = ANY(:policy_ids)"),
                    {"policy_ids": self.policy_ids},
                ).fetchall()
            ]
            if version_ids:
                conn.execute(text("DELETE FROM semantic_cache_policy_events WHERE policy_version_id = ANY(:version_ids)"), {"version_ids": version_ids})
                conn.execute(text("DELETE FROM semantic_cache_entries WHERE policy_version_id = ANY(:version_ids)"), {"version_ids": version_ids})
            conn.execute(text("DELETE FROM semantic_cache_policies WHERE id = ANY(:policy_ids)"), {"policy_ids": self.policy_ids})

    def _create(self, **config):
        policy = create_policy(
            name=f"M33 policy {uuid4().hex[:8]}",
            justification="M33 test",
            owner="platform",
            review_at=None,
            config={
                "enabled": False,
                "ttl_seconds": 300,
                "max_active_entries": 10,
                "allow_corpora": [],
                "deny_corpora": [],
                "allow_groups": [],
                "deny_groups": [],
                "allow_questions": ["What is the leave policy?"],
                "deny_questions": [],
                **config,
            },
            actor=self.actor,
        )
        self.policy_ids.append(int(policy["id"]))
        return policy

    def test_activation_requires_positive_scope(self):
        with self.assertRaisesRegex(ValueError, "At least one allowed"):
            validate_policy_config(
                {
                    "allow_corpora": [],
                    "allow_groups": [],
                    "allow_questions": [],
                }
            )

    def test_denies_override_allows_and_multi_corpus_requires_full_allow(self):
        policy = validate_policy_config(
            {
                "allow_corpora": ["handbook", "benefits"],
                "deny_corpora": ["restricted"],
                "allow_groups": ["employees"],
                "deny_groups": ["contractors"],
                "allow_questions": ["What is the leave policy?"],
                "deny_questions": ["Show secrets"],
            }
        )
        self.assertEqual(policy_allows(policy, question="Show secrets", corpus_names=["handbook"], groups=["employees"]), (False, "question_denied"))
        self.assertEqual(policy_allows(policy, question="What is the leave policy?", corpus_names=["restricted"], groups=["employees"]), (False, "corpus_denied"))
        self.assertEqual(policy_allows(policy, question="What is the leave policy?", corpus_names=["handbook"], groups=["contractors"]), (False, "group_denied"))
        self.assertEqual(policy_allows(policy, question="What is the leave policy?", corpus_names=["handbook", "other"], groups=["employees"]), (False, "corpus_not_fully_eligible"))
        self.assertEqual(policy_allows(policy, question="What is the leave policy?", corpus_names=["handbook", "benefits"], groups=["employees"]), (True, "eligible"))

    def test_policy_lifecycle_does_not_create_tuning_candidate(self):
        before = len(list_candidate_drafts())
        policy = self._create()
        activated = activate_policy(int(policy["id"]), confirmation=policy["name"], actor=self.actor)
        self.assertEqual(activated["status"], "active")
        self.assertEqual(len(list_candidate_drafts()), before)
        disabled = disable_policy(int(policy["id"]))
        self.assertEqual(disabled["status"], "disabled")
        self.assertIsNone(disabled["active_version"])

    def test_namespace_isolation_and_revision_change_prevent_reuse(self):
        policy = self._create()
        draft = get_policy(int(policy["id"]))["draft_version"]
        question = "What is the leave policy?"
        stored = store_cache_entry(
            question=question,
            retrieval_mode="hybrid",
            answer_json={"answer": "Twenty days.", "used_chunks_count": 1, "mode": "hybrid"},
            citations_json=[],
            retrieved_chunk_ids=[],
            ttl_seconds=300,
            policy=draft,
            cache_namespace="m33:test:a",
            answer_path="llm",
            original_latency_ms=120,
        )
        self.assertIsNotNone(stored["id"])
        self.assertIsNotNone(
            get_cache_entry(
                question=question,
                retrieval_mode="hybrid",
                actor=self.actor,
                policy=draft,
                cache_namespace="m33:test:a",
            )
        )
        self.assertIsNone(
            get_cache_entry(
                question=question,
                retrieval_mode="hybrid",
                actor=self.actor,
                policy=draft,
                cache_namespace="m33:test:b",
            )
        )
        bump_cache_revision(scope_type="content", reason="m33_test")
        self.assertIsNone(
            get_cache_entry(
                question=question,
                retrieval_mode="hybrid",
                actor=self.actor,
                policy=draft,
                cache_namespace="m33:test:a",
            )
        )


if __name__ == "__main__":
    unittest.main()
