import pytest

from app.services.retrieval import (
    RankedCandidate,
    reciprocal_rank_fusion,
)


def test_combines_vector_and_keyword_rankings_with_shared_candidate_first():
    vector_results = [
        RankedCandidate(segment_id="shared", rank=1, score=0.91, source="vector"),
        RankedCandidate(segment_id="vector-only", rank=2, score=0.83, source="vector"),
    ]
    keyword_results = [
        RankedCandidate(segment_id="keyword-only", rank=1, score=12.0, source="keyword"),
        RankedCandidate(segment_id="shared", rank=2, score=8.0, source="keyword"),
    ]

    fused = reciprocal_rank_fusion(
        vector_results=vector_results,
        keyword_results=keyword_results,
        k=60,
        limit=10,
    )

    assert [candidate.segment_id for candidate in fused] == [
        "shared",
        "keyword-only",
        "vector-only",
    ]


def test_preserves_vector_score_and_keyword_score():
    vector_results = [
        RankedCandidate(segment_id="shared", rank=3, score=0.72, source="vector"),
        RankedCandidate(segment_id="vector-only", rank=1, score=0.96, source="vector"),
    ]
    keyword_results = [
        RankedCandidate(segment_id="shared", rank=1, score=14.5, source="keyword"),
        RankedCandidate(segment_id="keyword-only", rank=2, score=9.0, source="keyword"),
    ]

    fused = reciprocal_rank_fusion(vector_results, keyword_results, k=60, limit=10)
    by_segment_id = {candidate.segment_id: candidate for candidate in fused}

    assert by_segment_id["shared"].vector_score == 0.72
    assert by_segment_id["shared"].keyword_score == 14.5
    assert by_segment_id["vector-only"].vector_score == 0.96
    assert by_segment_id["vector-only"].keyword_score is None
    assert by_segment_id["keyword-only"].vector_score is None
    assert by_segment_id["keyword-only"].keyword_score == 9.0


def test_respects_limit():
    vector_results = [
        RankedCandidate(segment_id="a", rank=1, score=0.9, source="vector"),
        RankedCandidate(segment_id="b", rank=2, score=0.8, source="vector"),
        RankedCandidate(segment_id="c", rank=3, score=0.7, source="vector"),
    ]

    fused = reciprocal_rank_fusion(vector_results, [], k=60, limit=2)

    assert [candidate.segment_id for candidate in fused] == ["a", "b"]


def test_handles_empty_lists():
    assert reciprocal_rank_fusion([], [], k=60, limit=10) == []


def test_tie_behavior_is_deterministic_by_best_rank_then_first_encounter():
    vector_results = [
        RankedCandidate(segment_id="b", rank=1, score=0.9, source="vector"),
        RankedCandidate(segment_id="a", rank=1, score=0.8, source="vector"),
    ]
    keyword_results = [
        RankedCandidate(segment_id="c", rank=1, score=10.0, source="keyword"),
    ]

    first = reciprocal_rank_fusion(vector_results, keyword_results, k=60, limit=10)
    second = reciprocal_rank_fusion(vector_results, keyword_results, k=60, limit=10)

    assert [candidate.segment_id for candidate in first] == ["b", "a", "c"]
    assert [candidate.segment_id for candidate in second] == ["b", "a", "c"]


def test_same_source_duplicates_use_lowest_positive_rank_and_associated_score():
    vector_results = [
        RankedCandidate(segment_id="x", rank=10, score=0.1, source="vector"),
        RankedCandidate(segment_id="x", rank=1, score=0.9, source="vector"),
    ]

    fused = reciprocal_rank_fusion(vector_results, [], k=60, limit=10)

    assert len(fused) == 1
    assert fused[0].segment_id == "x"
    assert fused[0].vector_score == 0.9
    assert fused[0].rrf_score == pytest.approx(1 / 61)


def test_invalid_k_raises_value_error():
    with pytest.raises(ValueError, match="k must be greater than 0"):
        reciprocal_rank_fusion([], [], k=0, limit=10)


def test_invalid_rank_raises_value_error():
    vector_results = [
        RankedCandidate(segment_id="x", rank=0, score=0.9, source="vector"),
    ]

    with pytest.raises(ValueError, match="rank must be greater than 0"):
        reciprocal_rank_fusion(vector_results, [], k=60, limit=10)
