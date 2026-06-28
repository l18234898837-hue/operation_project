from types import SimpleNamespace

from app.services.evidence_filtering import (
    compress_evidence_for_generation,
    filter_evidence_for_answer,
    filter_references_for_response,
    select_evidence_compression_policy,
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


def test_select_evidence_compression_policy_uses_top2_for_high_confidence():
    evidence = [
        SimpleNamespace(rerank_score=0.92),
        SimpleNamespace(rerank_score=0.81),
        SimpleNamespace(rerank_score=0.5),
    ]

    policy = select_evidence_compression_policy(evidence)

    assert policy.max_items == 2
    assert policy.max_chars_per_item == 700
    assert policy.reason == "high_confidence_top2"


def test_high_confidence_single_dominant_evidence_limits_generation_noise():
    evidence = [
        SimpleNamespace(rerank_score=0.91),
        SimpleNamespace(rerank_score=0.44),
        SimpleNamespace(rerank_score=0.43),
        SimpleNamespace(rerank_score=0.31),
    ]

    policy = select_evidence_compression_policy(evidence)

    assert policy.max_items == 2
    assert policy.reason == "dominant_high_confidence_top2"


def test_select_evidence_compression_policy_uses_top3_for_medium_confidence():
    evidence = [
        SimpleNamespace(rerank_score=0.72),
        SimpleNamespace(rerank_score=0.4),
        SimpleNamespace(rerank_score=0.35),
    ]

    policy = select_evidence_compression_policy(evidence)

    assert policy.max_items == 3
    assert policy.max_chars_per_item == 700
    assert policy.reason == "medium_confidence_top3"


def test_select_evidence_compression_policy_uses_top4_for_low_confidence():
    evidence = [
        SimpleNamespace(rerank_score=0.52),
        SimpleNamespace(rerank_score=0.49),
    ]

    policy = select_evidence_compression_policy(evidence)

    assert policy.max_items == 4
    assert policy.max_chars_per_item == 500
    assert policy.reason == "low_confidence_top4"


def test_compress_evidence_for_generation_truncates_clean_text_only():
    evidence = [
        SimpleNamespace(
            rerank_score=0.9,
            heading_path="逆变器 > PV 过压",
            clean_text="a" * 20,
        )
    ]

    result = compress_evidence_for_generation(evidence, max_chars_per_item=8)

    assert result[0].clean_text == "aaaaaaaa..."
    assert result[0].heading_path == "逆变器 > PV 过压"
    assert evidence[0].clean_text == "a" * 20
