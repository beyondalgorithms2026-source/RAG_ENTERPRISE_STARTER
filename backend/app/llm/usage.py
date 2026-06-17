"""Request-scoped generation-usage accumulator (AR11).

A single answer can make several generation calls (primary + JSON repair +
second pass). Each call appends its usage here so the answering layer can record
one aggregated cost/token figure per request and attach it to the trace, rather
than losing per-call usage. ContextVar-scoped (like AR8 profile overrides), so
concurrent requests never mix usage.
"""
from contextvars import ContextVar
from typing import Optional

_usage_ctx: ContextVar[Optional[list]] = ContextVar("generation_usage", default=None)


def reset_usage() -> None:
    _usage_ctx.set([])


def add_usage(usage: dict) -> None:
    bucket = _usage_ctx.get()
    if bucket is None:
        bucket = []
        _usage_ctx.set(bucket)
    bucket.append(usage)


def current_usage() -> dict:
    """Aggregate all generation calls in the current context."""
    bucket = _usage_ctx.get() or []
    prompt = sum(int(u.get("prompt_tokens") or 0) for u in bucket)
    completion = sum(int(u.get("completion_tokens") or 0) for u in bucket)
    cost = round(sum(float(u.get("cost_usd") or 0.0) for u in bucket), 6)
    estimated = any(bool(u.get("estimated")) for u in bucket)
    model = bucket[-1].get("model") if bucket else None
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
        "cost_usd": cost,
        "estimated": estimated,
        "call_count": len(bucket),
        "model": model,
    }
