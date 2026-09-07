import unittest
from unittest.mock import patch

from app.core.config import settings
from app.embedding import embedder
from app.profiles.models import EmbeddingProfileConfig


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class OpenAIEmbeddingProviderTests(unittest.TestCase):
    def setUp(self):
        self.original_api_key = settings.EMBEDDING_API_KEY
        settings.EMBEDDING_API_KEY = "test-key-not-a-real-secret"

    def tearDown(self):
        settings.EMBEDDING_API_KEY = self.original_api_key
        embedder.reset_embedder_cache()

    def test_requests_explicit_dimension_and_preserves_input_order(self):
        profile = EmbeddingProfileConfig(
            provider="openai",
            model="text-embedding-3-small",
            dimension=3,
            batch_size=2,
        )
        response = _FakeResponse(
            {
                "data": [
                    {"index": 1, "embedding": [0.0, 3.0, 4.0]},
                    {"index": 0, "embedding": [2.0, 0.0, 0.0]},
                ]
            }
        )
        with patch("httpx.post", return_value=response) as post:
            vectors = embedder._OpenAIEmbeddingProvider(profile).embed(["first", "second"])

        payload = post.call_args.kwargs["json"]
        headers = post.call_args.kwargs["headers"]
        self.assertEqual(payload["model"], "text-embedding-3-small")
        self.assertEqual(payload["dimensions"], 3)
        self.assertEqual(payload["input"], ["first", "second"])
        self.assertNotIn("api_key", payload)
        self.assertEqual(headers["Authorization"], "Bearer test-key-not-a-real-secret")
        self.assertEqual(vectors[0], [1.0, 0.0, 0.0])
        self.assertAlmostEqual(vectors[1][1], 0.6)
        self.assertAlmostEqual(vectors[1][2], 0.8)

    def test_rejects_wrong_dimension_response(self):
        profile = EmbeddingProfileConfig(
            provider="openai",
            model="text-embedding-3-small",
            dimension=3,
        )
        response = _FakeResponse({"data": [{"index": 0, "embedding": [1.0, 0.0]}]})
        with patch("httpx.post", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "returned 2 dimensions"):
                embedder._OpenAIEmbeddingProvider(profile).embed(["one"])

    def test_requires_private_api_key(self):
        settings.EMBEDDING_API_KEY = ""
        profile = EmbeddingProfileConfig(
            provider="openai",
            model="text-embedding-3-small",
            dimension=384,
        )
        with self.assertRaisesRegex(RuntimeError, "EMBEDDING_API_KEY is required"):
            embedder._OpenAIEmbeddingProvider(profile)

    def test_unknown_provider_fails_closed(self):
        profile = EmbeddingProfileConfig(
            provider="mystery", model="unknown", dimension=384
        )
        with self.assertRaisesRegex(RuntimeError, "Unsupported EMBEDDING_PROVIDER"):
            embedder._build_provider(profile)


if __name__ == "__main__":
    unittest.main()
