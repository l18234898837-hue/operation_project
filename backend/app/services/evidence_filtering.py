from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace


@dataclass(frozen=True)
class EvidenceCompressionPolicy:
    max_items: int
    max_chars_per_item: int
    reason: str


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


def select_evidence_compression_policy(evidence: list[object]) -> EvidenceCompressionPolicy:
    top1 = _rerank_score_at(evidence, 0)
    top2 = _rerank_score_at(evidence, 1)

    if top1 is not None and top1 >= 0.85 and (top2 is None or top1 - top2 >= 0.25):
        return EvidenceCompressionPolicy(
            max_items=2,
            max_chars_per_item=700,
            reason="dominant_high_confidence_top2",
        )
    if top1 is not None and top2 is not None and top1 >= 0.85 and top2 >= 0.75:
        return EvidenceCompressionPolicy(
            max_items=2,
            max_chars_per_item=700,
            reason="high_confidence_top2",
        )
    if top1 is not None and top1 >= 0.60:
        return EvidenceCompressionPolicy(
            max_items=3,
            max_chars_per_item=700,
            reason="medium_confidence_top3",
        )
    return EvidenceCompressionPolicy(
        max_items=4,
        max_chars_per_item=500,
        reason="low_confidence_top4",
    )


def compress_evidence_for_generation(
    evidence: list[object],
    max_chars_per_item: int,
) -> list[object]:
    return [
        _clone_with_clean_text(
            item,
            clean_text=_truncate_text(
                str(getattr(item, "clean_text", "") or ""),
                max_chars=max_chars_per_item,
            ),
        )
        for item in evidence
    ]


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


def _rerank_score_at(evidence: list[object], index: int) -> float | None:
    if index >= len(evidence):
        return None
    score = getattr(evidence[index], "rerank_score", None)
    return float(score) if score is not None else None


def _truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return f"{text[:max_chars].rstrip()}..."


def _clone_with_clean_text(item: object, clean_text: str) -> object:
    values = dict(getattr(item, "__dict__", {}) or {})
    values["clean_text"] = clean_text
    return SimpleNamespace(**values)
