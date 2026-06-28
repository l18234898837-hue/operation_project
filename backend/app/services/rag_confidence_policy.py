from __future__ import annotations

LOW_CONFIDENCE_SUPPLEMENT_SCORE = 0.3
STRONG_RAG_SCORE = 0.6


def effective_low_confidence_threshold(configured_threshold: float) -> float:
    return max(configured_threshold, LOW_CONFIDENCE_SUPPLEMENT_SCORE)


def effective_strong_rag_threshold(configured_threshold: float) -> float:
    return max(configured_threshold, STRONG_RAG_SCORE)
