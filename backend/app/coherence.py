"""Configuration coherence invariants (AR2).

The audit found the governance workflows (promotion, registries, rollback)
did not enforce their own invariants: the dev environment carried wrong
embedding dimension metadata, an unpromoted draft profile active as live,
and a migration ledger behind the code's plan. This module makes those
states detectable (health checks) and, via the write-time validators,
impossible to create through the API.
"""
from typing import Any, Optional

from sqlalchemy import text

from app.core.config import settings
from app.core.logging import logger
from app.db.db import engine

_MODEL_DIM_CACHE: dict[str, int] = {}


def model_output_dimension(model_name: str) -> int:
    """Load the embedding model and return its actual output dimension."""
    cached = _MODEL_DIM_CACHE.get(model_name)
    if cached is not None:
        return cached
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    dimension = model.get_sentence_embedding_dimension()
    if dimension is None:
        dimension = len(model.encode(["dimension probe"], normalize_embeddings=True)[0])
    _MODEL_DIM_CACHE[model_name] = int(dimension)
    return int(dimension)


def validate_embedding_profile_dimension(*, model_name: str, declared_dimension: int) -> None:
    """Raise ValueError when a profile declares a dimension its model does not produce."""
    actual = model_output_dimension(model_name)
    if int(declared_dimension) != actual:
        raise ValueError(
            f"Embedding profile declares dimension {declared_dimension} but model "
            f"'{model_name}' produces {actual}-dimensional vectors."
        )


def is_draft_profile_name(profile_name: str) -> bool:
    return str(profile_name or "").strip().lower().startswith("draft-")


def index_vector_dimension() -> Optional[int]:
    with engine.connect() as conn:
        typmod = conn.execute(
            text(
                "SELECT atttypmod FROM pg_attribute "
                "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
            )
        ).scalar()
    if typmod is None or int(typmod) <= 0:
        return None
    return int(typmod)


def _invariant(name: str, passed: bool, reason: str, **details: Any) -> dict[str, Any]:
    payload = {"invariant": name, "status": "pass" if passed else "fail", "reason": reason}
    if details:
        payload["details"] = {k: v for k, v in details.items() if v is not None}
    return payload


def check_embedding_dimension(*, load_model: bool = False) -> dict[str, Any]:
    from app.profiles.resolver import get_effective_embedding

    profile = get_effective_embedding()
    declared = int(profile.dimension)
    column = index_vector_dimension()
    if column is not None and declared != column:
        return _invariant(
            "embedding_dimension",
            False,
            f"Active embedding profile declares dimension {declared} but chunks.embedding is vector({column}).",
            declared=declared,
            index_column=column,
            model=profile.model,
        )
    if load_model:
        actual = model_output_dimension(profile.model)
        if actual != declared:
            return _invariant(
                "embedding_dimension",
                False,
                f"Active embedding profile declares dimension {declared} but model '{profile.model}' produces {actual}.",
                declared=declared,
                model_output=actual,
                model=profile.model,
            )
    return _invariant(
        "embedding_dimension",
        True,
        f"Declared dimension {declared} matches the index column" + (" and the model output." if load_model else "."),
        declared=declared,
        index_column=column,
        model=profile.model,
    )


def check_embedding_registry_metadata(*, load_models: bool = False) -> dict[str, Any]:
    """Validate declared dimensions across all embedding registry rows.

    Without load_models, only rows whose model has already been dimension-probed
    (cache) are checked; with load_models, every distinct model is loaded.
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT name, config_json->>'model' AS model, config_json->>'dimension' AS dimension "
                "FROM profiles WHERE profile_type = 'embedding' ORDER BY name"
            )
        ).fetchall()
    mismatches: list[dict[str, Any]] = []
    unchecked: list[str] = []
    for name, model, dimension in rows:
        if not model or dimension is None:
            mismatches.append({"profile": name, "reason": "missing model or dimension"})
            continue
        if not load_models and model not in _MODEL_DIM_CACHE:
            unchecked.append(name)
            continue
        actual = model_output_dimension(model)
        if int(dimension) != actual:
            mismatches.append({"profile": name, "model": model, "declared": int(dimension), "model_output": actual})
    if mismatches:
        return _invariant(
            "embedding_registry_metadata",
            False,
            f"{len(mismatches)} embedding registry row(s) declare a dimension their model does not produce.",
            mismatches=mismatches,
            unchecked=unchecked or None,
        )
    return _invariant(
        "embedding_registry_metadata",
        True,
        "All checked embedding registry rows declare their model's actual output dimension.",
        unchecked=unchecked or None,
    )


def check_active_profiles_promoted() -> dict[str, Any]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT profile_type, profile_name FROM active_profiles ORDER BY profile_type")).fetchall()
    draft_active = [{"profile_type": pt, "profile_name": pn} for pt, pn in rows if is_draft_profile_name(pn)]
    if draft_active:
        return _invariant(
            "active_profiles_promoted",
            False,
            "Unpromoted draft profile(s) are active as live configuration.",
            draft_active=draft_active,
        )
    return _invariant("active_profiles_promoted", True, "No active profile is an unpromoted draft.")


def check_migration_ledger() -> dict[str, Any]:
    from app.db.migrate import describe_migration_plan, recorded_migration_steps

    plan_ids = [item["step_id"] for item in describe_migration_plan()]
    recorded = set(recorded_migration_steps())
    missing = [step_id for step_id in plan_ids if step_id not in recorded]
    unknown = sorted(recorded - set(plan_ids))
    if missing or unknown:
        return _invariant(
            "migration_ledger",
            False,
            "Migration ledger disagrees with the code's plan.",
            missing=missing or None,
            unknown=unknown or None,
        )
    return _invariant("migration_ledger", True, f"Ledger records all {len(plan_ids)} plan steps.")


def run_coherence_checks(*, deep: bool = False) -> dict[str, Any]:
    invariants = [
        check_embedding_dimension(load_model=deep),
        check_embedding_registry_metadata(load_models=deep),
        check_active_profiles_promoted(),
        check_migration_ledger(),
    ]
    failed = [item for item in invariants if item["status"] == "fail"]
    return {"status": "fail" if failed else "pass", "deep": deep, "invariants": invariants}


def enforce_startup_coherence() -> dict[str, Any]:
    """Warn in local/dev, refuse to start otherwise, when invariants fail."""
    report = run_coherence_checks(deep=False)
    if report["status"] == "pass":
        return report
    reasons = "; ".join(item["reason"] for item in report["invariants"] if item["status"] == "fail")
    if (settings.APP_ENV or "local").strip().lower() in {"local", "dev"}:
        logger.warning("Configuration coherence check failed (continuing in %s): %s", settings.APP_ENV, reasons)
        return report
    raise RuntimeError(f"Configuration coherence check failed: {reasons}")
