"""Per-request corpus scope.

A caller may restrict one request to named corpora (``source_metadata_json.corpus``),
so two synthetic companies can share one database without an answer for one being
built from the other's documents. The scope only ever narrows: it is ANDed onto the
access-control clause in ``source_access_sql`` and never replaces it. With no scope
set, the generated SQL is unchanged.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from app.core.config import settings

_active_corpora: ContextVar[tuple[str, ...] | None] = ContextVar(
    "active_corpus_scope", default=None
)


def allowed_corpora() -> set[str]:
    return {name.strip() for name in (settings.ALLOWED_CORPORA or "").split(",") if name.strip()}


def normalize_corpora(values: Iterable[str] | None) -> tuple[str, ...] | None:
    """Validate and canonicalise requested corpus names; ``None`` means unscoped."""
    if values is None:
        return None
    names = sorted({str(value).strip() for value in values})
    if not names or any(not name for name in names):
        raise ValueError("corpus must be a non-empty list of corpus names")
    allowed = allowed_corpora()
    if allowed:
        unknown = [name for name in names if name not in allowed]
        if unknown:
            raise ValueError(f"unknown corpus: {', '.join(unknown)}")
    return tuple(names)


def active_corpora() -> tuple[str, ...] | None:
    return _active_corpora.get()


@contextmanager
def corpus_scope(corpora: Iterable[str] | None) -> Iterator[tuple[str, ...] | None]:
    token = _active_corpora.set(normalize_corpora(corpora))
    try:
        yield _active_corpora.get()
    finally:
        _active_corpora.reset(token)


def corpus_scope_sql(
    *, params: dict[str, Any], source_alias: str = "s", prefix: str = "access"
) -> str:
    corpora = active_corpora()
    if corpora is None:
        return ""
    param = f"{prefix}_corpus_scope"
    params[param] = list(corpora)
    return f"COALESCE({source_alias}.source_metadata_json ->> 'corpus', '') = ANY(:{param})"


def cache_corpus_scope() -> dict[str, Any] | None:
    corpora = active_corpora()
    return {"corpora": list(corpora)} if corpora is not None else None
