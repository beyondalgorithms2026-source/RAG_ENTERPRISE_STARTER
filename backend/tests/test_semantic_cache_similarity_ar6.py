import unittest
from uuid import uuid4

from sqlalchemy import text

import app.db.repo_semantic_cache as cache_module
from app.auth.context import AuthenticatedUser, reset_current_user, set_current_user
from app.db.db import engine
from app.db.migrate import run_migrations
from app.db.repo_semantic_cache import (
    bump_cache_revision,
    cache_health,
    get_cache_entry,
    store_cache_entry,
)
from app.db.repo_semantic_cache_policies import create_policy, get_policy, validate_policy_config
from app.profiles.models import RetrievalProfileConfig


# Deterministic, controlled embeddings so cosine is exact and network-free.
_VECTORS = {
    "What is the leave policy?": [1.0, 0.0, 0.0],
    "How much leave time do I get?": [0.98, 0.19899748, 0.0],   # cosine ~0.98 vs stored
    "What is the parking policy?": [0.5, 0.8660254, 0.0],        # cosine 0.50 vs stored
}




def setUpModule():
    """Skip this module when no database is reachable."""
    from tests.db_guard import require_database

    require_database()

class SemanticCacheSimilarityAR6Tests(unittest.TestCase):
    """AR6: the cache matched on an exact normalized-question hash; the
    semantic_cache_similarity_threshold field was dead code (audit). This adds a
    real embedding-similarity tier under the same governance."""

    @classmethod
    def setUpClass(cls):
        run_migrations()

    def setUp(self):
        self.actor = AuthenticatedUser(user_id=f"ar6-{uuid4().hex[:8]}", email="ar6@example.test", roles=["admin"], groups=["employees"])
        self._auth_token = set_current_user(self.actor)
        self.policy_ids: list[int] = []
        self._orig_embed = cache_module._embed_question
        cache_module._embed_question = lambda question: list(_VECTORS.get(question, []))

    def tearDown(self):
        cache_module._embed_question = self._orig_embed
        reset_current_user(self._auth_token)
        if not self.policy_ids:
            return
        with engine.begin() as conn:
            version_ids = [int(r[0]) for r in conn.execute(text("SELECT id FROM semantic_cache_policy_versions WHERE policy_id = ANY(:p)"), {"p": self.policy_ids}).fetchall()]
            if version_ids:
                conn.execute(text("DELETE FROM semantic_cache_policy_events WHERE policy_version_id = ANY(:v)"), {"v": version_ids})
                conn.execute(text("DELETE FROM semantic_cache_entries WHERE policy_version_id = ANY(:v)"), {"v": version_ids})
            conn.execute(text("DELETE FROM semantic_cache_policies WHERE id = ANY(:p)"), {"p": self.policy_ids})

    def _draft(self, **config):
        policy = create_policy(
            name=f"AR6 policy {uuid4().hex[:8]}",
            justification="AR6 test",
            owner="platform",
            review_at=None,
            config={"enabled": False, "ttl_seconds": 300, "max_active_entries": 50, "allow_groups": ["employees"], **config},
            actor=self.actor,
        )
        self.policy_ids.append(int(policy["id"]))
        return get_policy(int(policy["id"]))["draft_version"]

    def _store(self, draft, namespace):
        return store_cache_entry(
            question="What is the leave policy?",
            retrieval_mode="hybrid",
            answer_json={"answer": "Twenty days of annual leave.", "used_chunks_count": 1, "mode": "hybrid"},
            citations_json=[],
            retrieved_chunk_ids=[],
            ttl_seconds=300,
            policy=draft,
            cache_namespace=namespace,
            answer_path="llm",
            original_latency_ms=140,
        )

    def test_dead_threshold_field_removed_from_retrieval_profile(self):
        self.assertNotIn("semantic_cache_similarity_threshold", RetrievalProfileConfig().model_dump())

    def test_policy_config_accepts_and_validates_match_mode_and_threshold(self):
        cfg = validate_policy_config({"allow_questions": ["x"], "match_mode": "semantic", "similarity_threshold": 0.88})
        self.assertEqual(cfg["match_mode"], "semantic")
        self.assertEqual(cfg["similarity_threshold"], 0.88)
        with self.assertRaisesRegex(ValueError, "match_mode"):
            validate_policy_config({"allow_questions": ["x"], "match_mode": "fuzzy"})
        with self.assertRaisesRegex(ValueError, "similarity_threshold"):
            validate_policy_config({"allow_questions": ["x"], "match_mode": "semantic", "similarity_threshold": 0.2})

    def test_semantic_policy_stores_query_embedding(self):
        draft = self._draft(match_mode="semantic", similarity_threshold=0.92)
        namespace = f"ar6:store:{uuid4().hex[:6]}"
        stored = self._store(draft, namespace)
        with engine.connect() as conn:
            emb = conn.execute(text("SELECT query_embedding_json FROM semantic_cache_entries WHERE id = :id"), {"id": stored["id"]}).scalar_one()
        self.assertEqual([float(v) for v in emb], _VECTORS["What is the leave policy?"])

    def test_paraphrase_hits_under_semantic_mode(self):
        draft = self._draft(match_mode="semantic", similarity_threshold=0.92)
        namespace = f"ar6:hit:{uuid4().hex[:6]}"
        self._store(draft, namespace)
        # Exact still works and is labeled exact.
        exact = get_cache_entry(question="What is the leave policy?", retrieval_mode="hybrid", actor=self.actor, policy=draft, cache_namespace=namespace)
        self.assertEqual(exact["match_type"], "exact")
        # Paraphrase (no exact row) resolves via similarity.
        para = get_cache_entry(question="How much leave time do I get?", retrieval_mode="hybrid", actor=self.actor, policy=draft, cache_namespace=namespace)
        self.assertIsNotNone(para)
        self.assertEqual(para["match_type"], "similarity")
        self.assertGreaterEqual(para["similarity"], 0.92)

    def test_false_hit_guard_below_threshold_misses(self):
        draft = self._draft(match_mode="semantic", similarity_threshold=0.92)
        namespace = f"ar6:guard:{uuid4().hex[:6]}"
        self._store(draft, namespace)
        # Similar-looking but different-intent question is 0.50 cosine — must miss.
        self.assertIsNone(get_cache_entry(question="What is the parking policy?", retrieval_mode="hybrid", actor=self.actor, policy=draft, cache_namespace=namespace))

    def test_exact_mode_does_not_match_paraphrase(self):
        draft = self._draft(match_mode="exact")
        namespace = f"ar6:exact:{uuid4().hex[:6]}"
        self._store(draft, namespace)
        self.assertIsNotNone(get_cache_entry(question="What is the leave policy?", retrieval_mode="hybrid", actor=self.actor, policy=draft, cache_namespace=namespace))
        self.assertIsNone(get_cache_entry(question="How much leave time do I get?", retrieval_mode="hybrid", actor=self.actor, policy=draft, cache_namespace=namespace))

    def test_similarity_hit_respects_revision_governance(self):
        # A similarity hit runs the identical revision check as an exact hit.
        draft = self._draft(match_mode="semantic", similarity_threshold=0.92)
        namespace = f"ar6:rev:{uuid4().hex[:6]}"
        self._store(draft, namespace)
        self.assertIsNotNone(get_cache_entry(question="How much leave time do I get?", retrieval_mode="hybrid", actor=self.actor, policy=draft, cache_namespace=namespace))
        bump_cache_revision(scope_type="content", reason="ar6_test")
        self.assertIsNone(get_cache_entry(question="How much leave time do I get?", retrieval_mode="hybrid", actor=self.actor, policy=draft, cache_namespace=namespace))

    def test_cache_health_distinguishes_exact_from_similarity_hits(self):
        draft = self._draft(match_mode="semantic", similarity_threshold=0.92)
        namespace = f"ar6:health:{uuid4().hex[:6]}"
        self._store(draft, namespace)
        before = cache_health()
        get_cache_entry(question="What is the leave policy?", retrieval_mode="hybrid", actor=self.actor, policy=draft, cache_namespace=namespace)
        get_cache_entry(question="How much leave time do I get?", retrieval_mode="hybrid", actor=self.actor, policy=draft, cache_namespace=namespace)
        after = cache_health()
        self.assertEqual(after["exact_hit_count"], before["exact_hit_count"] + 1)
        self.assertEqual(after["similarity_hit_count"], before["similarity_hit_count"] + 1)


if __name__ == "__main__":
    unittest.main()
