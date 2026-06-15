"""Console-editable governed runtime settings (AR17).

A small, allowlisted key/value store that lets an operator tune a few
operational settings from the admin console instead of editing the environment
and restarting. Read paths consult these overrides first, then fall back to the
environment (`settings.*`). Only the allowlisted keys are accepted, each with
its own validation, so this never becomes an arbitrary config backdoor.
"""
import math
from typing import Any, Optional

from sqlalchemy import text

from app.auth.context import AuthenticatedUser
from app.db.db import engine

ALLOWED_KEYS = {"llm_cost_alert_usd", "llm_price_table", "tuning_eval_enforcement", "admin_modules_enabled"}


def _validate(key: str, value: Any) -> Any:
    if key == "llm_cost_alert_usd":
        v = float(value)
        if not math.isfinite(v) or v < 0:
            raise ValueError("llm_cost_alert_usd must be a finite number >= 0")
        return v
    if key == "llm_price_table":
        if not isinstance(value, dict):
            raise ValueError("llm_price_table must be an object of model -> [input, output]")
        table: dict[str, list[float]] = {}
        for model, prices in value.items():
            model_name = str(model).strip()
            if not model_name:
                raise ValueError("llm_price_table model names must not be empty")
            if not isinstance(prices, (list, tuple)) or len(prices) != 2:
                raise ValueError(f"price for '{model}' must be [input_per_1k, output_per_1k]")
            normalized = [float(prices[0]), float(prices[1])]
            if any(not math.isfinite(price) or price < 0 for price in normalized):
                raise ValueError(f"price for '{model_name}' must contain finite non-negative values")
            table[model_name] = normalized
        return table
    if key == "tuning_eval_enforcement":
        v = str(value or "").strip().lower()
        if v not in {"require", "warn", ""}:
            raise ValueError("tuning_eval_enforcement must be 'require', 'warn', or ''")
        return v
    if key == "admin_modules_enabled":
        if not isinstance(value, list):
            raise ValueError("admin_modules_enabled must be a list of module names")
        return [str(item).strip().lower() for item in value if str(item).strip()]
    raise ValueError(f"Setting '{key}' is not runtime-editable")


def get_setting(key: str) -> Optional[Any]:
    """Return the runtime override for a key, or None when unset. Never raises on
    a missing table so callers can fall back to env safely."""
    if key not in ALLOWED_KEYS:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT value_json FROM runtime_settings WHERE key = :k"), {"k": key}).first()
        return row[0] if row else None
    except Exception:
        return None


def set_setting(key: str, value: Any, *, actor: Optional[AuthenticatedUser] = None) -> dict[str, Any]:
    if key not in ALLOWED_KEYS:
        raise ValueError(f"Setting '{key}' is not runtime-editable")
    validated = _validate(key, value)
    import json

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO runtime_settings (key, value_json, updated_by, updated_at)
                VALUES (:k, CAST(:v AS jsonb), :by, now())
                ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json,
                    updated_by = EXCLUDED.updated_by, updated_at = now()
                """
            ),
            {"k": key, "v": json.dumps(validated), "by": actor.email if actor else None},
        )
    return {"key": key, "value": validated}


def delete_setting(key: str) -> bool:
    if key not in ALLOWED_KEYS:
        raise ValueError(f"Setting '{key}' is not runtime-editable")
    with engine.begin() as conn:
        result = conn.execute(text("DELETE FROM runtime_settings WHERE key = :k"), {"k": key})
    return bool(result.rowcount)


def all_settings() -> dict[str, Any]:
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT key, value_json FROM runtime_settings")).fetchall()
        return {row[0]: row[1] for row in rows if row[0] in ALLOWED_KEYS}
    except Exception:
        return {}
