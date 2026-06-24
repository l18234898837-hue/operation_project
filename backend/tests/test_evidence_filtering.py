from types import SimpleNamespace

from app.services.evidence_filtering import (
    filter_evidence_for_answer,
    filter_references_for_response,
)


def test_filter_evidence_for_answer_keeps_only_items_above_threshold():
    evidence = [
        SimpleNamespace(rerank_score=0.8),
        SimpleNamespace(rerank_score=0.1),
        SimpleNamespace(rerank_score=None),
        SimpleNamespace(rerank_score=0.5),
    ]

    result = filter_evidence_for_answer(evidence, min_rerank_score=0.2, max_items=5)

    assert [item.rerank_score for item in result] == [0.8, 0.5]


def test_filter_evidence_for_answer_respects_max_items():
    evidence = [
        SimpleNamespace(rerank_score=0.8),
        SimpleNamespace(rerank_score=0.7),
        SimpleNamespace(rerank_score=0.6),
    ]

    result = filter_evidence_for_answer(evidence, min_rerank_score=0.2, max_items=2)

    assert [item.rerank_score for item in result] == [0.8, 0.7]


def test_filter_references_for_response_applies_reference_threshold_and_limit():
    evidence = [
        SimpleNamespace(rerank_score=0.9),
        SimpleNamespace(rerank_score=0.7),
        SimpleNamespace(rerank_score=0.2),
        SimpleNamespace(rerank_score=0.4),
    ]

    result = filter_references_for_response(
        evidence,
        min_rerank_score=0.3,
        max_items=3,
    )

    assert [item.rerank_score for item in result] == [0.9, 0.7, 0.4]
