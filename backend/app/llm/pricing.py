"""Token and cost estimation for generation calls (AR11).

The original plan promised "latency/cost traces"; the audit found latency
delivered and cost entirely absent — no token counting, no per-request cost,
no per-profile rollups. This module supplies the cost half: a configurable
price table and a documented token estimator used when a provider does not
report usage.

Estimation method (documented, deliberately simple): when a provider returns no
usage, token counts are approximated as ceil(len(text) / CHARS_PER_TOKEN) with
CHARS_PER_TOKEN = 4 — the common English heuristic. Estimated usage is always
flagged `estimated: true` so rollups never present a guess as a measurement.
"""
import json
import math
from typing import Optional

from app.core.config import settings

CHARS_PER_TOKEN = 4

# USD per 1K tokens, (input, output). Override/extend via LLM_PRICE_TABLE_JSON.
# Local models are free; cloud entries are illustrative defaults operators tune.
_DEFAULT_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.0025, 0.01),
    "claude-haiku-4-5-20251001": (0.001, 0.005),
    "claude-opus-4-8": (0.015, 0.075),
}


def estimate_tokens(text: str) -> int:
    return int(math.ceil(len(str(text or "")) / CHARS_PER_TOKEN))


def _runtime_setting(key: str):
    try:  # never let DB access break pricing
        from app.db.repo_runtime_settings import get_setting

        return get_setting(key)
    except Exception:
        return None


def _environment_price_table() -> dict[str, tuple[float, float]]:
    table: dict[str, tuple[float, float]] = {}
    raw = str(getattr(settings, "LLM_PRICE_TABLE_JSON", "") or "").strip()
    if raw:
        try:
            for model, prices in json.loads(raw).items():
                table[str(model)] = (float(prices[0]), float(prices[1]))
        except Exception:
            return {}
    return table


def effective_price_table() -> dict[str, list[float]]:
    """Precedence (lowest→highest): defaults → env LLM_PRICE_TABLE_JSON → runtime override."""
    table = dict(_DEFAULT_PRICES)
    table.update(_environment_price_table())
    runtime = _runtime_setting("llm_price_table")
    if isinstance(runtime, dict):
        for model, prices in runtime.items():
            try:
                table[str(model)] = (float(prices[0]), float(prices[1]))
            except Exception:
                pass
    return {model: [prices[0], prices[1]] for model, prices in table.items()}


def price_table_source() -> str:
    if isinstance(_runtime_setting("llm_price_table"), dict):
        return "runtime"
    if _environment_price_table():
        return "environment"
    return "default"


def cost_alert_source() -> str:
    if _runtime_setting("llm_cost_alert_usd") is not None:
        return "runtime"
    if float(getattr(settings, "LLM_COST_ALERT_USD", 0.0) or 0.0):
        return "environment"
    return "default"


def cost_alert_usd() -> float:
    """Per-request budget threshold; runtime override wins over env (0 disables)."""
    runtime = _runtime_setting("llm_cost_alert_usd")
    if runtime is not None:
        try:
            return float(runtime)
        except Exception:
            pass
    return float(getattr(settings, "LLM_COST_ALERT_USD", 0.0) or 0.0)


def price_for(model: str) -> tuple[float, float]:
    """(input_per_1k, output_per_1k) USD; (0,0) for unknown/local models."""
    prices = effective_price_table().get(str(model or ""), [0.0, 0.0])
    return float(prices[0]), float(prices[1])


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    input_rate, output_rate = price_for(model)
    return round((prompt_tokens / 1000.0) * input_rate + (completion_tokens / 1000.0) * output_rate, 6)


def usage_from_texts(model: str, *, prompt_text: str, completion_text: str) -> dict:
    prompt_tokens = estimate_tokens(prompt_text)
    completion_tokens = estimate_tokens(completion_text)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "estimated": True,
        "model": model,
        "cost_usd": cost_usd(model, prompt_tokens, completion_tokens),
    }


def usage_from_counts(model: str, *, prompt_tokens: int, completion_tokens: int, estimated: bool = False) -> dict:
    return {
        "prompt_tokens": int(prompt_tokens),
        "completion_tokens": int(completion_tokens),
        "total_tokens": int(prompt_tokens) + int(completion_tokens),
        "estimated": estimated,
        "model": model,
        "cost_usd": cost_usd(model, int(prompt_tokens), int(completion_tokens)),
    }
