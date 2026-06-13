"""Managed embedding/index swap lifecycle (AR7).

The single failure that disabled the regression suite (AR1) was an
embedding/index dimension drift: a 768-dim profile was activated against a
column the code assumed was 384-dim, nothing blocked it, surfaced it, or
orchestrated the reindex. Reindex existed only as a per-source action.

This module makes a model/dimension swap a guided, resumable, verifiable
operation over a state machine persisted in `embedding_swap_runs`:

    planned -> reindexing -> verifying -> completed
                   |             |
                   +--> aborted  +--> failed

While a swap is mid-flight the active embedding dimension diverges from the
index, so vector search degrades to keyword-only (see
app.coherence.vector_serving_state and the retrieval hard block) rather than
erroring or serving corrupt neighbours.

The column resize and re-embedding are real; the heavy steps go through the
module-level `_resize_vector_column` and `_reembed_pending` indirections so the
unit tests can drive the state machine without re-embedding a whole corpus.
"""
from typing import Any, Optional

from sqlalchemy import text

from app.auth.context import AuthenticatedUser
from app.core.logging import logger
from app.db.db import engine

_RUN_COLUMNS = """
    id, target_profile_name, basis_profile_name, target_model, target_dimension,
    source_dimension, requires_reindex, status, total_chunks, embedded_chunks,
    failed_chunks, verification_json, error, actor_external_user_id, actor_email,
    created_at, updated_at
"""

ACTIVE_STATUSES = ("planned", "reindexing", "verifying")


def _serialize(row: Any) -> dict[str, Any]:
    payload = dict(row)
    for key, value in list(payload.items()):
        if hasattr(value, "isoformat"):
            payload[key] = value.isoformat()
    return payload


def _embedding_profile(profile_name: str) -> dict[str, Any]:
    from app.db.repo_profiles import get_profile

    profile = get_profile("embedding", profile_name)
    if not profile:
        raise ValueError(f"Embedding profile '{profile_name}' not found")
    return profile


def _chunk_counts() -> tuple[int, int]:
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM chunks WHERE COALESCE(TRIM(chunk_text), '') <> ''")).scalar_one()
        embedded = conn.execute(text("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL")).scalar_one()
    return int(total), int(embedded)


def plan_embedding_swap(*, target_profile_name: str) -> dict[str, Any]:
    """Validate the target profile and report what a swap would entail. Pure read."""
    from app.coherence import index_vector_dimension, model_output_dimension, validate_embedding_profile_dimension

    profile = _embedding_profile(target_profile_name)
    config = profile["config_json"] or {}
    model = str(config.get("model") or "")
    declared = int(config.get("dimension") or 0)
    validate_embedding_profile_dimension(model_name=model, declared_dimension=declared)
    actual = model_output_dimension(model)
    index_dim = index_vector_dimension()
    total, embedded = _chunk_counts()
    return {
        "target_profile_name": target_profile_name,
        "target_model": model,
        "target_dimension": actual,
        "source_dimension": index_dim,
        "requires_reindex": index_dim is None or actual != index_dim or embedded < total,
        "requires_column_resize": index_dim is not None and actual != index_dim,
        "total_chunks": total,
        "already_embedded": embedded,
    }


def begin_embedding_swap(*, target_profile_name: str, actor: Optional[AuthenticatedUser] = None) -> dict[str, Any]:
    from app.db.repo_profiles import get_active_profile_name

    plan = plan_embedding_swap(target_profile_name=target_profile_name)
    with engine.begin() as conn:
        active = conn.execute(text("SELECT id FROM embedding_swap_runs WHERE status = ANY(:s)"), {"s": list(ACTIVE_STATUSES)}).first()
        if active:
            raise ValueError(f"An embedding swap is already in progress (run {int(active[0])}); finish or abort it first.")
        row = conn.execute(
            text(
                f"""
                INSERT INTO embedding_swap_runs (
                    target_profile_name, basis_profile_name, target_model, target_dimension,
                    source_dimension, requires_reindex, status, total_chunks, embedded_chunks,
                    actor_external_user_id, actor_email
                )
                VALUES (
                    :target_profile_name, :basis, :target_model, :target_dimension,
                    :source_dimension, :requires_reindex, 'planned', :total_chunks, 0,
                    :actor_id, :actor_email
                )
                RETURNING {_RUN_COLUMNS}
                """
            ),
            {
                "target_profile_name": target_profile_name,
                "basis": get_active_profile_name("embedding"),
                "target_model": plan["target_model"],
                "target_dimension": plan["target_dimension"],
                "source_dimension": plan["source_dimension"],
                "requires_reindex": plan["requires_reindex"],
                "total_chunks": plan["total_chunks"],
                "actor_id": actor.user_id if actor else None,
                "actor_email": actor.email if actor else None,
            },
        ).mappings().one()
    return _serialize(row)


def get_swap_run(run_id: int) -> Optional[dict[str, Any]]:
    with engine.connect() as conn:
        row = conn.execute(text(f"SELECT {_RUN_COLUMNS} FROM embedding_swap_runs WHERE id = :id"), {"id": run_id}).mappings().first()
    return _serialize(row) if row else None


def list_swap_runs(limit: int = 50) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"SELECT {_RUN_COLUMNS} FROM embedding_swap_runs ORDER BY created_at DESC, id DESC LIMIT :l"), {"l": limit}).mappings().all()
    return [_serialize(row) for row in rows]


def _update_run(run_id: int, **fields: Any) -> dict[str, Any]:
    assignments = ", ".join(f"{key} = :{key}" for key in fields)
    fields["id"] = run_id
    with engine.begin() as conn:
        row = conn.execute(
            text(f"UPDATE embedding_swap_runs SET {assignments}, updated_at = now() WHERE id = :id RETURNING {_RUN_COLUMNS}"),
            fields,
        ).mappings().one()
    return _serialize(row)


def _resize_vector_column(dimension: int) -> None:
    """Rebuild the vector column to the target dimension, dropping indexes and
    clearing now-incompatible embeddings. Indexes are recreated after re-embed."""
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX IF EXISTS chunks_embedding_hnsw;"))
        conn.execute(text("DROP INDEX IF EXISTS chunks_embedding_ivfflat;"))
        conn.execute(text("UPDATE chunks SET embedding = NULL WHERE embedding IS NOT NULL;"))
        conn.execute(text(f"ALTER TABLE chunks ALTER COLUMN embedding TYPE vector({int(dimension)});"))


def _reembed_pending(batch_limit: Optional[int] = None) -> dict[str, Any]:
    from app.embedding.process import process_embeddings

    return process_embeddings(force=False, limit=batch_limit)


def _rebuild_vector_index() -> None:
    from app.db.migrate import _create_vector_index

    _create_vector_index()


def run_embedding_swap(*, run_id: int, batch_limit: Optional[int] = None) -> dict[str, Any]:
    """Advance a swap run: activate the target profile, (re)size the column on
    first entry, re-embed pending chunks (resumable across calls), then move to
    verifying once every chunk is embedded."""
    run = get_swap_run(run_id)
    if not run:
        raise ValueError(f"Swap run {run_id} not found")
    if run["status"] in ("completed", "aborted", "failed"):
        return run

    from app.db.repo_profiles import set_active_profile
    from app.embedding.embedder import reset_embedder_cache
    from app.profiles.resolver import invalidate_cache

    try:
        if run["status"] == "planned":
            # Point the system at the target model; vector search degrades to
            # keyword-only from here until the reindex completes (by design).
            set_active_profile("embedding", run["target_profile_name"])
            invalidate_cache("embedding")
            reset_embedder_cache()
            if run["requires_reindex"] and run["source_dimension"] != run["target_dimension"]:
                _resize_vector_column(int(run["target_dimension"]))
            run = _update_run(run_id, status="reindexing")

        if run["status"] == "reindexing":
            stats = _reembed_pending(batch_limit=batch_limit)
            total, embedded = _chunk_counts()
            run = _update_run(
                run_id,
                embedded_chunks=embedded,
                failed_chunks=int(stats.get("chunks_failed") or 0),
                total_chunks=total,
            )
            if embedded >= total:
                _rebuild_vector_index()
                run = _update_run(run_id, status="verifying")
    except Exception as exc:  # surface the failure on the run, never crash the caller
        logger.error("Embedding swap run %s failed: %s", run_id, exc)
        return _update_run(run_id, status="failed", error=str(exc))
    return run


def verify_embedding_swap(*, run_id: int, sample_size: int = 10) -> dict[str, Any]:
    """Counts reconciliation + sampled re-embedding distance check. A correctly
    reindexed corpus re-embeds its own chunk text to ~cosine 1.0 against the
    stored vector."""
    run = get_swap_run(run_id)
    if not run:
        raise ValueError(f"Swap run {run_id} not found")
    if run["status"] not in ("verifying", "completed"):
        raise ValueError(f"Swap run {run_id} is {run['status']}, not ready for verification")

    from app.db.repo_semantic_cache import _cosine
    from app.embedding.embedder import embed_texts

    total, embedded = _chunk_counts()
    counts_ok = embedded >= total and total > 0
    with engine.connect() as conn:
        sample = conn.execute(
            text(
                "SELECT id, chunk_text, embedding::text AS emb FROM chunks "
                "WHERE embedding IS NOT NULL AND COALESCE(TRIM(chunk_text), '') <> '' "
                "ORDER BY id LIMIT :n"
            ),
            {"n": sample_size},
        ).mappings().all()
    distances: list[float] = []
    if sample:
        re_embedded = embed_texts([row["chunk_text"] for row in sample])
        for row, fresh in zip(sample, re_embedded):
            stored = [float(v) for v in str(row["emb"]).strip("[]").split(",") if v.strip()]
            distances.append(_cosine(stored, fresh))
    min_similarity = round(min(distances), 4) if distances else None
    sample_ok = bool(distances) and min(distances) >= 0.999
    verification = {
        "counts_ok": counts_ok,
        "total_chunks": total,
        "embedded_chunks": embedded,
        "sample_size": len(sample),
        "min_self_similarity": min_similarity,
        "sample_ok": sample_ok,
    }
    if counts_ok and sample_ok:
        return _update_run(run_id, status="completed", verification_json=__import__("json").dumps(verification), error=None)
    return _update_run(
        run_id,
        status="failed",
        verification_json=__import__("json").dumps(verification),
        error="counts_reconciliation_failed" if not counts_ok else "sample_distance_check_failed",
    )


def abort_embedding_swap(*, run_id: int, reason: str) -> dict[str, Any]:
    run = get_swap_run(run_id)
    if not run:
        raise ValueError(f"Swap run {run_id} not found")
    if run["status"] in ("completed", "aborted", "failed"):
        return run
    return _update_run(run_id, status="aborted", error=f"aborted: {reason}")
