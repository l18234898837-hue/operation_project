from app.services.rag_confidence_policy import (
    LOW_CONFIDENCE_SUPPLEMENT_SCORE,
    STRONG_RAG_SCORE,
    effective_low_confidence_threshold,
    effective_strong_rag_threshold,
)


def test_rag_confidence_policy_defaults():
    assert LOW_CONFIDENCE_SUPPLEMENT_SCORE == 0.3
    assert STRONG_RAG_SCORE == 0.6


def test_rag_confidence_policy_keeps_conservative_effective_thresholds():
    assert effective_low_confidence_threshold(0.2) == 0.3
    assert effective_low_confidence_threshold(0.45) == 0.45
    assert effective_strong_rag_threshold(0.5) == 0.6
    assert effective_strong_rag_threshold(0.7) == 0.7
