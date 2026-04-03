from typing import Any, Optional

from sqlalchemy import text

from app.core.logging import logger
from app.db.db import engine


def list_profiles(profile_type: Optional[str] = None) -> list[dict[str, Any]]:
    sql = "SELECT id, profile_type, name, config_json, is_default, created_at, updated_at FROM profiles"
    params: dict[str, Any] = {}
    if profile_type:
        sql += " WHERE profile_type = :pt"
        params["pt"] = profile_type
    sql += " ORDER BY profile_type, name"
    with engine.connect() as conn:
        stmt = text(sql)
        if params:
            stmt = stmt.bindparams(**params)
        rows = conn.execute(stmt).mappings().all()
        return [dict(r) for r in rows]


def get_profile(profile_type: str, name: str) -> Optional[dict[str, Any]]:
    sql = "SELECT id, profile_type, name, config_json, is_default, created_at, updated_at FROM profiles WHERE profile_type = :pt AND name = :n"
    with engine.connect() as conn:
        stmt = text(sql).bindparams(pt=profile_type, n=name)
        row = conn.execute(stmt).mappings().first()
        return dict(row) if row else None


def upsert_profile(profile_type: str, name: str, config_json: dict, is_default: bool = False) -> int:
    sql = """
        INSERT INTO profiles (profile_type, name, config_json, is_default)
        VALUES (:pt, :n, CAST(:cj AS jsonb), :d)
        ON CONFLICT (profile_type, name)
        DO UPDATE SET config_json = EXCLUDED.config_json,
                      is_default = EXCLUDED.is_default,
                      updated_at = now()
        RETURNING id
    """
    import json
    with engine.begin() as conn:
        stmt = text(sql).bindparams(
            pt=profile_type,
            n=name,
            cj=json.dumps(config_json),
            d=is_default
        )
        row = conn.execute(stmt).first()
        return row[0]


def get_active_profile_name(profile_type: str) -> Optional[str]:
    sql = "SELECT profile_name FROM active_profiles WHERE profile_type = :pt"
    with engine.connect() as conn:
        stmt = text(sql).bindparams(pt=profile_type)
        row = conn.execute(stmt).first()
        return row[0] if row else None


def set_active_profile(profile_type: str, profile_name: str) -> None:
    profile = get_profile(profile_type, profile_name)
    if not profile:
        raise ValueError(f"Profile '{profile_name}' of type '{profile_type}' not found")
    sql = """
        INSERT INTO active_profiles (profile_type, profile_name, updated_at)
        VALUES (:pt, :pn, now())
        ON CONFLICT (profile_type)
        DO UPDATE SET profile_name = EXCLUDED.profile_name, updated_at = now()
    """
    with engine.begin() as conn:
        stmt = text(sql).bindparams(pt=profile_type, pn=profile_name)
        conn.execute(stmt)


def get_active_profile_config(profile_type: str) -> Optional[dict[str, Any]]:
    sql = """
        SELECT p.config_json
        FROM active_profiles ap
        JOIN profiles p ON p.profile_type = ap.profile_type AND p.name = ap.profile_name
        WHERE ap.profile_type = :pt
    """
    with engine.connect() as conn:
        stmt = text(sql).bindparams(pt=profile_type)
        row = conn.execute(stmt).first()
        return row[0] if row else None


def seed_default_profiles(settings) -> None:
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM profiles")).scalar()
    if count and count > 0:
        logger.info("Profiles already seeded (%d rows), skipping.", count)
        return

    logger.info("Seeding default profiles from current settings...")

    # Embedding — dimension resolved dynamically
    try:
        from app.embedding.embedder import get_expected_dim
        dim = get_expected_dim()
    except Exception:
        dim = 384

    upsert_profile("embedding", "default", {
        "model": settings.EMBEDDING_MODEL,
        "dimension": dim,
        "batch_size": settings.EMBEDDING_BATCH_SIZE,
    }, is_default=True)

    upsert_profile("reranker", "default", {
        "enabled": settings.RERANK_ENABLED,
        "model": settings.RERANK_MODEL,
        "enabled_modes": [],
        "enabled_corpora": [],
        "min_candidate_count": 0,
        "max_candidate_count": None,
        "latency_budget_ms": None,
        "mmr_enabled": False,
        "mmr_lambda": 0.5,
    }, is_default=True)

    upsert_profile("llm", "default", {
        "provider": settings.LLM_PROVIDER,
        "model": settings.LLM_MODEL,
        "base_url": settings.LLM_BASE_URL,
        "api_key": settings.LLM_API_KEY,
        "timeout_s": settings.LLM_TIMEOUT_S,
        "temperature": 0.0,
    }, is_default=True)

    upsert_profile("retrieval", "default", {
        "default_mode": settings.RETRIEVAL_MODE,
        "top_k_initial": settings.TOP_K_INITIAL,
        "hybrid_alpha": settings.HYBRID_ALPHA,
        "vector_candidates": settings.VECTOR_CANDIDATES,
        "keyword_candidates": settings.KEYWORD_CANDIDATES,
        "deep_research_alpha": 0.2,
        "deep_research_vector_candidates": 24,
        "deep_research_keyword_candidates": 36,
        "fusion_method": "linear",
        "rrf_k": 60,
    }, is_default=True)

    upsert_profile("eval_pack", "default", {
        "dataset_name": "retrieval_cases",
        "cases_path": "backend/tests/fixtures/eval/retrieval_cases.json",
        "description": "Baseline retrieval evaluation pack",
    }, is_default=True)

    # Set all as active
    for pt in ("embedding", "reranker", "llm", "retrieval", "eval_pack"):
        set_active_profile(pt, "default")

    logger.info("Default profiles seeded and activated.")
