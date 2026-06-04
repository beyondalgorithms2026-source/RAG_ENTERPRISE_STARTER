from typing import Any, Optional

from sqlalchemy import text

from app.core.logging import logger
from app.db.db import engine

PROFILE_TYPES_FOR_TUNING = ("embedding", "reranker", "llm", "retrieval")

APPROVED_PROFILE_SEEDS: dict[str, list[dict[str, Any]]] = {
    "embedding": [
        {
            "name": "bge-small-en-v1_5",
            "config": {
                "model": "BAAI/bge-small-en-v1.5",
                "dimension": 384,
                "batch_size": 32,
                "display_name": "BGE Small v1.5",
                "registry_entry": True,
                "approval_status": "approved",
            },
        },
        {
            "name": "bge-base-en-v1_5",
            "config": {
                "model": "BAAI/bge-base-en-v1.5",
                "dimension": 768,
                "batch_size": 16,
                "display_name": "BGE Base v1.5",
                "registry_entry": True,
                "approval_status": "approved",
            },
        },
        {
            "name": "nomic-embed-text",
            "config": {
                "model": "nomic-ai/nomic-embed-text-v1.5",
                "dimension": 768,
                "batch_size": 16,
                "display_name": "Nomic Embed Text",
                "registry_entry": True,
                "approval_status": "approved",
            },
        },
    ],
    "reranker": [
        {
            "name": "off",
            "config": {
                "enabled": False,
                "model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
                "top_n": None,
                "score_threshold": None,
                "enabled_modes": [],
                "enabled_corpora": [],
                "min_candidate_count": 0,
                "max_candidate_count": None,
                "latency_budget_ms": None,
                "mmr_enabled": False,
                "mmr_lambda": 0.5,
                "display_name": "Reranker Off",
                "registry_entry": True,
                "approval_status": "approved",
            },
        },
        {
            "name": "tinybert-lite",
            "config": {
                "enabled": True,
                "model": "cross-encoder/ms-marco-TinyBERT-L-2-v2",
                "top_n": 8,
                "score_threshold": None,
                "enabled_modes": [],
                "enabled_corpora": [],
                "min_candidate_count": 2,
                "max_candidate_count": None,
                "latency_budget_ms": None,
                "mmr_enabled": False,
                "mmr_lambda": 0.5,
                "display_name": "TinyBERT Lite",
                "registry_entry": True,
                "approval_status": "approved",
            },
        },
        {
            "name": "minilm-quality",
            "config": {
                "enabled": True,
                "model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
                "top_n": 8,
                "score_threshold": None,
                "enabled_modes": [],
                "enabled_corpora": [],
                "min_candidate_count": 2,
                "max_candidate_count": None,
                "latency_budget_ms": None,
                "mmr_enabled": False,
                "mmr_lambda": 0.5,
                "display_name": "MiniLM Quality",
                "registry_entry": True,
                "approval_status": "approved",
            },
        },
        {
            "name": "bge-reranker-base",
            "config": {
                "enabled": True,
                "model": "BAAI/bge-reranker-base",
                "top_n": 8,
                "score_threshold": None,
                "enabled_modes": [],
                "enabled_corpora": [],
                "min_candidate_count": 2,
                "max_candidate_count": None,
                "latency_budget_ms": None,
                "mmr_enabled": False,
                "mmr_lambda": 0.5,
                "display_name": "BGE Reranker Base",
                "registry_entry": True,
                "approval_status": "approved",
            },
        },
    ],
    "llm": [
        {
            "name": "llama3_2_3b",
            "config": {
                "provider": "ollama",
                "model": "llama3.2:3b",
                "base_url": "http://localhost:11434",
                "api_key": "",
                "timeout_s": 60,
                "temperature": 0.0,
                "max_tokens": None,
                "display_name": "Llama 3.2 3B",
                "registry_entry": True,
                "approval_status": "approved",
            },
        },
        {
            "name": "phi3_mini",
            "config": {
                "provider": "ollama",
                "model": "phi3:mini",
                "base_url": "http://localhost:11434",
                "api_key": "",
                "timeout_s": 60,
                "temperature": 0.0,
                "max_tokens": None,
                "display_name": "Phi-3 Mini",
                "registry_entry": True,
                "approval_status": "approved",
            },
        },
        {
            "name": "ministral_3_8b_instruct",
            "config": {
                "provider": "ollama",
                "model": "ministral-3:8b-instruct-2512-q4_K_M",
                "base_url": "http://localhost:11434",
                "api_key": "",
                "timeout_s": 60,
                "temperature": 0.0,
                "max_tokens": None,
                "display_name": "Ministral 3 8B Instruct",
                "registry_entry": True,
                "approval_status": "approved",
            },
        },
        {
            "name": "deepseek_v3_1_cloud",
            "config": {
                "provider": "ollama",
                "model": "deepseek-v3.1:671b-cloud",
                "base_url": "http://localhost:11434",
                "api_key": "",
                "timeout_s": 60,
                "temperature": 0.0,
                "max_tokens": None,
                "display_name": "DeepSeek v3.1 Cloud",
                "registry_entry": True,
                "approval_status": "approved",
            },
        },
    ],
}


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


def delete_profile(profile_type: str, name: str) -> int:
    sql = "DELETE FROM profiles WHERE profile_type = :pt AND name = :n"
    with engine.begin() as conn:
        stmt = text(sql).bindparams(pt=profile_type, n=name)
        result = conn.execute(stmt)
    return int(result.rowcount or 0)


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


def get_active_profile_map(profile_types: Optional[list[str]] = None) -> dict[str, str]:
    sql = "SELECT profile_type, profile_name FROM active_profiles"
    with engine.connect() as conn:
        stmt = text(sql)
        rows = conn.execute(stmt).fetchall()
    payload = {str(row[0]): str(row[1]) for row in rows}
    if profile_types:
        return {profile_type: payload[profile_type] for profile_type in profile_types if profile_type in payload}
    return payload


def list_approved_registry_profiles(profile_type: Optional[str] = None) -> list[dict[str, Any]]:
    rows = list_profiles(profile_type)
    approved: list[dict[str, Any]] = []
    for row in rows:
        config = row["config_json"] or {}
        if config.get("registry_entry") and str(config.get("approval_status", "")).lower() == "approved":
            approved.append(
                {
                    "id": row["id"],
                    "profile_type": row["profile_type"],
                    "name": row["name"],
                    "config": config,
                    "is_default": row["is_default"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
    return approved


def is_registry_approved_profile(profile_type: str, profile_name: str) -> bool:
    profile = get_profile(profile_type, profile_name)
    if not profile:
        return False
    config = profile["config_json"] or {}
    return bool(config.get("registry_entry")) and str(config.get("approval_status", "")).lower() == "approved"


def seed_default_profiles(settings) -> None:
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM profiles")).scalar()
    first_seed = not count or count <= 0
    if first_seed:
        logger.info("Seeding default profiles from current settings...")
    else:
        logger.info("Ensuring default and approved profile registry entries exist...")

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
        "query_transform_enabled": False,
        "rewrite_enabled": False,
        "expansion_enabled": False,
        "hyde_enabled": False,
        "transform_timeout_ms": 750,
        "transform_max_variants": 3,
    }, is_default=True)

    upsert_profile("eval_pack", "default", {
        "dataset_name": "retrieval_cases",
        "cases_path": "backend/tests/fixtures/eval/retrieval_cases.json",
        "description": "Baseline retrieval evaluation pack",
    }, is_default=True)

    for profile_type, seeds in APPROVED_PROFILE_SEEDS.items():
        for entry in seeds:
            if profile_type == "embedding" and entry["config"].get("model") == settings.EMBEDDING_MODEL:
                entry_config = dict(entry["config"])
                entry_config["dimension"] = dim if entry_config.get("model") == settings.EMBEDDING_MODEL else entry_config.get("dimension")
                upsert_profile(profile_type, entry["name"], entry_config, is_default=False)
            else:
                upsert_profile(profile_type, entry["name"], dict(entry["config"]), is_default=False)

    # Set all as active on first seed only or when missing.
    for pt in ("embedding", "reranker", "llm", "retrieval", "eval_pack"):
        if first_seed or not get_active_profile_name(pt):
            set_active_profile(pt, "default")

    logger.info("Profile defaults and approved registry entries are ready.")
