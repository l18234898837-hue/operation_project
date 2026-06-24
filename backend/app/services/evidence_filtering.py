from __future__ import annotations


def filter_evidence_for_answer(
    evidence: list[object],
    min_rerank_score: float,
    max_items: int,
) -> list[object]:
    return _filter_by_rerank_score(evidence, min_rerank_score, max_items)


def filter_references_for_response(
    evidence: list[object],
    min_rerank_score: float,
    max_items: int,
) -> list[object]:
    return _filter_by_rerank_score(evidence, min_rerank_score, max_items)


def _filter_by_rerank_score(
    evidence: list[object],
    min_rerank_score: float,
    max_items: int,
) -> list[object]:
    filtered: list[object] = []
    for item in evidence:
        score = getattr(item, "rerank_score", None)
        if score is None:
            continue
        if float(score) >= min_rerank_score:
            filtered.append(item)
        if len(filtered) >= max_items:
            break
    return filtered
