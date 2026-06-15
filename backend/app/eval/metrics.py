"""Graded retrieval evaluation metrics (AR3).

The audit found pass criteria were keyword/heading containment only — no
graded relevance, no recall@k / MRR / nDCG, no faithfulness scoring. These
functions operate on a ranked list of chunk ids and a graded relevance map
({chunk_id: grade}, grades 0-3; grade >= min_grade counts as relevant).
"""
import math
from typing import Any, Iterable, Optional, Sequence


def _relevant_ids(relevant_grades: dict[int, int], min_grade: int = 1) -> set[int]:
    return {chunk_id for chunk_id, grade in relevant_grades.items() if int(grade) >= min_grade}


def recall_at_k(ranked_ids: Sequence[int], relevant_grades: dict[int, int], k: int, *, min_grade: int = 1) -> Optional[float]:
    relevant = _relevant_ids(relevant_grades, min_grade)
    if not relevant:
        return None
    hits = sum(1 for chunk_id in list(ranked_ids)[:k] if chunk_id in relevant)
    return hits / len(relevant)


def reciprocal_rank(ranked_ids: Sequence[int], relevant_grades: dict[int, int], *, min_grade: int = 1) -> Optional[float]:
    relevant = _relevant_ids(relevant_grades, min_grade)
    if not relevant:
        return None
    for rank, chunk_id in enumerate(ranked_ids, start=1):
        if chunk_id in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranked_ids: Sequence[int], relevant_grades: dict[int, int], k: int) -> Optional[float]:
    if not _relevant_ids(relevant_grades, 1):
        return None

    def gain(grade: int) -> float:
        return (2 ** int(grade)) - 1

    dcg = 0.0
    for rank, chunk_id in enumerate(list(ranked_ids)[:k], start=1):
        grade = int(relevant_grades.get(chunk_id, 0))
        if grade > 0:
            dcg += gain(grade) / math.log2(rank + 1)
    ideal_grades = sorted((int(g) for g in relevant_grades.values() if int(g) > 0), reverse=True)[:k]
    idcg = sum(gain(grade) / math.log2(rank + 1) for rank, grade in enumerate(ideal_grades, start=1))
    if idcg == 0:
        return None
    return dcg / idcg


def citation_faithfulness(
    *,
    cited_chunk_ids: Iterable[int],
    relevant_grades: dict[int, int],
    answered_not_found: bool,
    min_grade: int = 1,
) -> Optional[float]:
    """Fraction of citations that point at labeled-relevant evidence.

    A truthful "not found" on a case with no labeled relevant evidence scores
    1.0; a "not found" despite labeled evidence scores 0.0. Cases with an
    answer but zero citations score 0.0 (the citation contract failed).
    """
    relevant = _relevant_ids(relevant_grades, min_grade)
    cited = list(cited_chunk_ids)
    if answered_not_found:
        return 1.0 if not relevant else 0.0
    if not relevant:
        return None
    if not cited:
        return 0.0
    return sum(1 for chunk_id in cited if chunk_id in relevant) / len(cited)


def evaluate_ranking(ranked_ids: Sequence[int], relevant_grades: dict[int, int], *, ks: Sequence[int] = (5, 10)) -> dict[str, Any]:
    result: dict[str, Any] = {"mrr": reciprocal_rank(ranked_ids, relevant_grades)}
    for k in ks:
        result[f"recall_at_{k}"] = recall_at_k(ranked_ids, relevant_grades, k)
        result[f"ndcg_at_{k}"] = ndcg_at_k(ranked_ids, relevant_grades, k)
    return result


def aggregate_metric(values: Iterable[Optional[float]]) -> Optional[float]:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present) / len(present)


def aggregate_case_metrics(case_metrics: Sequence[dict[str, Any]]) -> dict[str, Optional[float]]:
    if not case_metrics:
        return {}
    keys = sorted({key for metrics in case_metrics for key in metrics if isinstance(metrics.get(key), (int, float)) or metrics.get(key) is None})
    return {key: aggregate_metric(metrics.get(key) for metrics in case_metrics) for key in keys}


def intra_list_diversity(similarities: Sequence[float]) -> Optional[float]:
    values = [min(1.0, max(-1.0, float(value))) for value in similarities]
    if not values:
        return None
    return sum(1.0 - value for value in values) / len(values)
