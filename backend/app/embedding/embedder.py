from __future__ import annotations

import math
from typing import Protocol

from app.core.config import settings
from app.core.logging import logger
from app.profiles.models import EmbeddingProfileConfig


class _EmbeddingProvider(Protocol):
    def expected_dimension(self) -> int: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class _SentenceTransformerProvider:
    def __init__(self, profile: EmbeddingProfileConfig):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for EMBEDDING_PROVIDER=sentence_transformers. "
                "Install backend/requirements-local.txt or select a hosted provider."
            ) from exc

        logger.info("Loading local embedding model: %s", profile.model)
        self._profile = profile
        self._model = SentenceTransformer(profile.model)
        dimension = self._model.get_sentence_embedding_dimension()
        if dimension is None:
            dimension = len(self._model.encode(["dimension probe"], normalize_embeddings=True)[0])
        self._dimension = int(dimension)
        if self._dimension != int(profile.dimension):
            raise RuntimeError(
                f"Embedding profile declares {profile.dimension} dimensions but "
                f"model '{profile.model}' produces {self._dimension}."
            )

    def expected_dimension(self) -> int:
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(
            texts,
            batch_size=self._profile.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return embeddings.tolist()


class _OpenAIEmbeddingProvider:
    def __init__(self, profile: EmbeddingProfileConfig):
        if not settings.EMBEDDING_API_KEY:
            raise RuntimeError("EMBEDDING_API_KEY is required for EMBEDDING_PROVIDER=openai.")
        if not profile.model.startswith("text-embedding-3-"):
            raise RuntimeError(
                "The configured OpenAI embedding model must support the dimensions parameter "
                "(text-embedding-3 family)."
            )
        if int(profile.dimension) <= 0:
            raise RuntimeError("EMBEDDING_DIMENSIONS must be a positive integer.")
        self._profile = profile

    def expected_dimension(self) -> int:
        return int(self._profile.dimension)

    def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        url = settings.EMBEDDING_BASE_URL.rstrip("/") + "/embeddings"
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {settings.EMBEDDING_API_KEY}"},
            json={
                "input": texts,
                "model": self._profile.model,
                "dimensions": int(self._profile.dimension),
                "encoding_format": "float",
            },
            timeout=settings.EMBEDDING_TIMEOUT_S,
        )
        response.raise_for_status()
        payload = response.json()
        rows = sorted(payload.get("data") or [], key=lambda item: item.get("index", -1))
        if len(rows) != len(texts):
            raise RuntimeError(
                f"Embedding provider returned {len(rows)} vectors for {len(texts)} inputs."
            )

        vectors: list[list[float]] = []
        for expected_index, row in enumerate(rows):
            if row.get("index") != expected_index:
                raise RuntimeError("Embedding provider returned incomplete or duplicate indexes.")
            vector = [float(value) for value in row.get("embedding") or []]
            if len(vector) != int(self._profile.dimension):
                raise RuntimeError(
                    f"Embedding provider returned {len(vector)} dimensions; "
                    f"expected {self._profile.dimension}."
                )
            magnitude = math.sqrt(sum(value * value for value in vector))
            if magnitude <= 0:
                raise RuntimeError("Embedding provider returned a zero-length vector.")
            vectors.append([value / magnitude for value in vector])
        return vectors


_model: _EmbeddingProvider | None = None
_EXPECTED_DIM = None
_loaded_profile_key: tuple[str, str, int, int] | None = None


def _provider_name(value: str) -> str:
    normalized = (value or "sentence_transformers").strip().lower().replace("-", "_")
    if normalized in {"local", "sentence_transformer"}:
        return "sentence_transformers"
    return normalized


def _build_provider(profile: EmbeddingProfileConfig) -> _EmbeddingProvider:
    provider = _provider_name(profile.provider)
    if provider == "sentence_transformers":
        return _SentenceTransformerProvider(profile)
    if provider == "openai":
        return _OpenAIEmbeddingProvider(profile)
    raise RuntimeError(
        f"Unsupported EMBEDDING_PROVIDER '{profile.provider}'. "
        "Supported providers: sentence_transformers, openai."
    )


def get_model():
    global _model, _EXPECTED_DIM, _loaded_profile_key
    from app.profiles.resolver import get_effective_embedding

    profile = get_effective_embedding()
    profile_key = (
        _provider_name(profile.provider),
        profile.model,
        int(profile.dimension),
        int(profile.batch_size),
    )
    if _model is None or _loaded_profile_key != profile_key:
        _model = _build_provider(profile)
        _loaded_profile_key = profile_key
        _EXPECTED_DIM = _model.expected_dimension()
        logger.info(
            "Embedding provider ready: provider=%s model=%s dimensions=%s",
            profile_key[0],
            profile.model,
            _EXPECTED_DIM,
        )
    return _model


def get_expected_dim() -> int:
    get_model()
    return _EXPECTED_DIM


def reset_embedder_cache() -> None:
    """Force the next get_model() to reload from the active profile (AR7:
    after a swap activates a different embedding model)."""
    global _model, _EXPECTED_DIM, _loaded_profile_key
    _model = None
    _EXPECTED_DIM = None
    _loaded_profile_key = None


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    provider = get_model()
    return provider.embed(texts)
