from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, replace
from typing import Iterator


@dataclass(frozen=True)
class RetrievalScoring:
    anchor_cooccurrence_cap: float = 0.18
    anchor_cooccurrence_term: float = 0.03
    anchor_cooccurrence_pair: float = 0.02
    anchor_explicit_cap: float = 0.24
    anchor_explicit_term: float = 0.035
    anchor_explicit_pair: float = 0.025
    soft_keyword_anchor_term: float = 0.05
    graph_existing_weight: float = 0.20
    graph_supplemental_weight: float = 0.20
    temporal_signal_score: float = 1.0
    temporal_weight: float = 0.10
    neighbor_base: float = 0.03
    neighbor_anchor_term: float = 0.025
    anchor_window_base: float = 0.12
    anchor_window_term: float = 0.04
    anchor_window_overlap_cap: float = 0.08
    anchor_window_overlap_term: float = 0.01
    anchor_window_cap: float = 0.31
    anchor_window_neighbor_weight: float = 0.70
    anchor_window_offset_bonus: float = 0.08
    anchor_window_neighbor_bonus: float = 0.08
    anchor_window_neighbor_cap: float = 0.24


ADOPTED_RETRIEVAL_SCORING = RetrievalScoring()
_scoring_override: ContextVar[RetrievalScoring | None] = ContextVar("retrieval_scoring_override", default=None)


def get_retrieval_scoring() -> RetrievalScoring:
    return _scoring_override.get() or ADOPTED_RETRIEVAL_SCORING


def scoring_snapshot() -> dict[str, float]:
    return asdict(get_retrieval_scoring())


@contextmanager
def retrieval_scoring_overrides(**changes: float) -> Iterator[RetrievalScoring]:
    scoring = replace(get_retrieval_scoring(), **changes)
    token = _scoring_override.set(scoring)
    try:
        yield scoring
    finally:
        _scoring_override.reset(token)
