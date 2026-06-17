"""AR2 data repair: fix the audit-observed incoherent states in an existing DB.

Repairs, with admin-audit entries:
1. Embedding registry rows whose declared dimension does not match the model's
   actual output (the audit found BAAI/bge-small-en-v1.5 registered as 768; it
   produces 384).
2. An active retrieval profile carrying a draft name: re-registered under a
   promoted repair name and re-activated, so the draft-activation guard holds.

Run: python -m app.db.repair_coherence
"""
from sqlalchemy import text

from app.coherence import is_draft_profile_name, model_output_dimension
from app.core.logging import logger
from app.db.db import engine


def _audit(action: str, resource_id: str, before: dict, after: dict) -> None:
    from app.db.repo_admin_audit import insert_admin_audit_event

    insert_admin_audit_event(
        event_type="coherence_repair",
        action=action,
        resource_type="profile",
        resource_id=resource_id,
        resource_name=resource_id,
        before_json=before,
        after_json=after,
    )


def repair_embedding_registry_dimensions() -> list[dict]:
    repaired: list[dict] = []
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT name, config_json->>'model' AS model, (config_json->>'dimension')::int AS dimension "
                "FROM profiles WHERE profile_type = 'embedding'"
            )
        ).fetchall()
    for name, model, declared in rows:
        if not model or declared is None:
            continue
        try:
            actual = model_output_dimension(model)
        except Exception as exc:
            logger.warning("Skipping dimension repair for %s: model %s not loadable (%s)", name, model, exc)
            continue
        if int(declared) == actual:
            continue
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE profiles SET config_json = jsonb_set(config_json, '{dimension}', to_jsonb(CAST(:actual AS int)), true), "
                    "updated_at = now() WHERE profile_type = 'embedding' AND name = :name"
                ),
                {"actual": actual, "name": name},
            )
        _audit(
            "coherence.repair.embedding_dimension",
            f"embedding:{name}",
            {"model": model, "dimension": int(declared)},
            {"model": model, "dimension": actual},
        )
        logger.info("Repaired embedding registry row %s: dimension %s -> %s (model %s)", name, declared, actual, model)
        repaired.append({"profile": name, "model": model, "from": int(declared), "to": actual})
    return repaired


def repair_draft_active_profiles() -> list[dict]:
    from app.db.repo_profiles import get_profile, set_active_profile, upsert_profile
    from app.db.repo_tuning_configs import sync_live_configuration_record
    from app.profiles.resolver import invalidate_cache

    repaired: list[dict] = []
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT profile_type, profile_name FROM active_profiles")).fetchall()
    for profile_type, profile_name in rows:
        if not is_draft_profile_name(profile_name):
            continue
        draft_profile = get_profile(profile_type, profile_name)
        if not draft_profile:
            continue
        promoted_name = f"promoted-repair-{profile_name.removeprefix('draft-')}"
        config = dict(draft_profile["config_json"] or {})
        config["approval_status"] = "coherence_repair_promoted"
        config["promoted_from_draft"] = profile_name
        upsert_profile(profile_type, promoted_name, config, is_default=False)
        set_active_profile(profile_type, promoted_name)
        _audit(
            "coherence.repair.draft_active_profile",
            f"{profile_type}:{profile_name}",
            {"active_profile": profile_name},
            {"active_profile": promoted_name, "promoted_from_draft": profile_name},
        )
        logger.info("Repaired draft-active profile %s/%s -> %s", profile_type, profile_name, promoted_name)
        repaired.append({"profile_type": profile_type, "from": profile_name, "to": promoted_name})
    if repaired:
        invalidate_cache()
        sync_live_configuration_record()
    return repaired


def run_repair() -> dict:
    report = {
        "embedding_registry": repair_embedding_registry_dimensions(),
        "draft_active_profiles": repair_draft_active_profiles(),
    }
    logger.info("Coherence repair complete: %s", report)
    return report


if __name__ == "__main__":
    print(run_repair())
