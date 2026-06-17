from app.core.logging import logger


_model = None
_EXPECTED_DIM = None
_loaded_model_name: str | None = None


def get_model():
    global _model, _EXPECTED_DIM, _loaded_model_name
    from app.profiles.resolver import get_effective_embedding
    profile = get_effective_embedding()
    if _model is None or _loaded_model_name != profile.model:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required to load the embedding model."
            ) from exc

        logger.info(f"Loading embedding model: {profile.model}")
        _model = SentenceTransformer(profile.model)
        _loaded_model_name = profile.model
        _EXPECTED_DIM = _model.get_sentence_embedding_dimension()
        if _EXPECTED_DIM is None:
            dummy_embedding = _model.encode(["test dummy"], normalize_embeddings=True)[0]
            _EXPECTED_DIM = len(dummy_embedding)
        logger.info(f"Model loaded successfully. Expected vector dimensions: {_EXPECTED_DIM}")
    return _model


def get_expected_dim() -> int:
    get_model()
    return _EXPECTED_DIM


def reset_embedder_cache() -> None:
    """Force the next get_model() to reload from the active profile (AR7:
    after a swap activates a different embedding model)."""
    global _model, _EXPECTED_DIM, _loaded_model_name
    _model = None
    _EXPECTED_DIM = None
    _loaded_model_name = None


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    from app.profiles.resolver import get_effective_embedding
    profile = get_effective_embedding()
    model = get_model()
    embeddings = model.encode(
        texts,
        batch_size=profile.batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return embeddings.tolist()
