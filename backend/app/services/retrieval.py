from dataclasses import dataclass
import re

from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.models.rag import KbDocumentSegment
from app.services.keyword_index import build_keyword_text, normalize_query
from app.services.siliconflow import SiliconFlowEmbeddingClient, SiliconFlowRerankClient


TSQUERY_TOKEN_RE = re.compile(r"^[\w\u4e00-\u9fff]+(?:-[\w\u4e00-\u9fff]+)*$")


@dataclass
class RankedCandidate:
    segment_id: str
    rank: int
    score: float
    source: str


@dataclass
class FusedCandidate:
    segment_id: str
    rrf_score: float
    vector_score: float | None
    keyword_score: float | None


@dataclass
class EvidenceChunk:
    segment_id: str
    document_id: str
    heading_path: str
    indexed_text: str
    clean_text: str
    vector_score: float | None
    keyword_score: float | None
    rrf_score: float
    rerank_score: float | None


@dataclass
class _CandidateAccumulator:
    segment_id: str
    rrf_score: float = 0.0
    vector_score: float | None = None
    keyword_score: float | None = None
    best_rank: int | None = None
    first_seen: int = 0

    def add_source_score(self, rank: int, score: float, score_key: str, k: int) -> None:
        self.rrf_score += 1 / (k + rank)
        self.best_rank = rank if self.best_rank is None else min(self.best_rank, rank)

        if score_key == "vector_score":
            self.vector_score = score
            return

        self.keyword_score = score


def reciprocal_rank_fusion(
    vector_results: list[RankedCandidate],
    keyword_results: list[RankedCandidate],
    k: int,
    limit: int,
) -> list[FusedCandidate]:
    if k <= 0:
        raise ValueError("k must be greater than 0")

    _validate_ranks(vector_results)
    _validate_ranks(keyword_results)

    if limit <= 0:
        return []

    candidates: dict[str, _CandidateAccumulator] = {}

    def add_results(results: list[RankedCandidate], score_key: str) -> None:
        for result in _best_ranked_by_segment_id(results):
            candidate = candidates.setdefault(
                result.segment_id,
                _CandidateAccumulator(
                    segment_id=result.segment_id,
                    first_seen=len(candidates),
                ),
            )
            candidate.add_source_score(result.rank, result.score, score_key, k)

    add_results(vector_results, "vector_score")
    add_results(keyword_results, "keyword_score")

    sorted_candidates = sorted(
        candidates.values(),
        key=lambda candidate: (
            -candidate.rrf_score,
            candidate.best_rank,
            candidate.first_seen,
        ),
    )

    return [
        FusedCandidate(
            segment_id=candidate.segment_id,
            rrf_score=candidate.rrf_score,
            vector_score=candidate.vector_score,
            keyword_score=candidate.keyword_score,
        )
        for candidate in sorted_candidates[:limit]
    ]


def _validate_ranks(results: list[RankedCandidate]) -> None:
    for result in results:
        if result.rank <= 0:
            raise ValueError("rank must be greater than 0")


def _best_ranked_by_segment_id(
    results: list[RankedCandidate],
) -> list[RankedCandidate]:
    best_by_segment_id: dict[str, RankedCandidate] = {}

    for result in results:
        current = best_by_segment_id.get(result.segment_id)
        if current is None or result.rank < current.rank:
            best_by_segment_id[result.segment_id] = result

    return list(best_by_segment_id.values())


def build_vector_search_sql(limit: int) -> str:
    return """
    SELECT
        id::text AS segment_id,
        (1 - (embedding <=> :query_embedding)) AS score,
        row_number() OVER (ORDER BY embedding <=> :query_embedding) AS rank
    FROM kb_document_segment
    WHERE embedding IS NOT NULL
    ORDER BY embedding <=> :query_embedding
    LIMIT :limit
    """


def build_keyword_search_sql(limit: int) -> str:
    return """
    WITH query AS (
        SELECT to_tsquery('simple', :query_text) AS tsquery
    )
    SELECT
        id::text AS segment_id,
        ts_rank_cd(to_tsvector('simple', COALESCE(keyword_text, '')), query.tsquery) AS score,
        row_number() OVER (
            ORDER BY ts_rank_cd(
                to_tsvector('simple', COALESCE(keyword_text, '')),
                query.tsquery
            ) DESC
        ) AS rank
    FROM kb_document_segment, query
    WHERE to_tsvector('simple', COALESCE(keyword_text, '')) @@ query.tsquery
    ORDER BY score DESC
    LIMIT :limit
    """


async def retrieve_evidence(
    session: Session,
    query: str,
    embedding_client: SiliconFlowEmbeddingClient,
    rerank_client: SiliconFlowRerankClient | None,
    vector_top_k: int,
    keyword_top_k: int,
    rrf_top_k: int,
    final_top_k: int,
    rrf_k: int,
) -> list[EvidenceChunk]:
    normalized_query = normalize_query(query)
    keyword_query = build_keyword_text(normalized_query) or normalized_query
    keyword_tsquery = build_keyword_tsquery(keyword_query)
    query_embedding = (await embedding_client.embed([normalized_query]))[0]
    vector_stmt = text(build_vector_search_sql(vector_top_k)).bindparams(
        bindparam("query_embedding", type_=Vector(1024)),
        bindparam("limit"),
    )

    vector_rows = session.execute(
        vector_stmt,
        {"query_embedding": query_embedding, "limit": vector_top_k},
    ).all()
    keyword_rows = []
    if keyword_tsquery:
        keyword_rows = session.execute(
            text(build_keyword_search_sql(keyword_top_k)),
            {"query_text": keyword_tsquery, "limit": keyword_top_k},
        ).all()

    fused = reciprocal_rank_fusion(
        _rows_to_ranked(vector_rows, "vector"),
        _rows_to_ranked(keyword_rows, "keyword"),
        k=rrf_k,
        limit=rrf_top_k,
    )
    if not fused:
        return []

    segment_ids = [candidate.segment_id for candidate in fused]
    segments = (
        session.query(KbDocumentSegment)
        .filter(KbDocumentSegment.id.in_(segment_ids))
        .all()
    )
    segment_by_id = {str(segment.id): segment for segment in segments}
    fused_by_id = {candidate.segment_id: candidate for candidate in fused}
    ordered_segments = [
        segment_by_id[segment_id]
        for segment_id in segment_ids
        if segment_id in segment_by_id
    ]
    if not ordered_segments:
        return []

    final_segment_ids = [str(segment.id) for segment in ordered_segments[:final_top_k]]
    rerank_scores: dict[str, float] = {}
    if rerank_client is not None:
        rerank_results = await rerank_client.rerank(
            normalized_query,
            [segment.indexed_text for segment in ordered_segments],
            top_n=final_top_k,
        )
        final_segment_ids = []
        for result in rerank_results:
            if result.index < 0 or result.index >= len(ordered_segments):
                continue
            segment_id = str(ordered_segments[result.index].id)
            final_segment_ids.append(segment_id)
            rerank_scores[segment_id] = float(result.score)

    return [
        _to_evidence_chunk(
            segment=segment_by_id[segment_id],
            fused=fused_by_id[segment_id],
            rerank_score=rerank_scores.get(segment_id),
        )
        for segment_id in final_segment_ids[:final_top_k]
        if segment_id in segment_by_id and segment_id in fused_by_id
    ]


def _rows_to_ranked(rows: list[object], source: str) -> list[RankedCandidate]:
    return [
        RankedCandidate(
            segment_id=str(_row_value(row, "segment_id")),
            rank=int(_row_value(row, "rank")),
            score=float(_row_value(row, "score") or 0.0),
            source=source,
        )
        for row in rows
    ]


def build_keyword_tsquery(keyword_query: str) -> str:
    tokens = [
        token
        for token in keyword_query.split()
        if TSQUERY_TOKEN_RE.fullmatch(token)
    ]
    return " | ".join(tokens)


def _row_value(row: object, key: str) -> object:
    mapping = getattr(row, "_mapping", None)
    if mapping is not None and key in mapping:
        return mapping[key]

    return getattr(row, key)


def _to_evidence_chunk(
    segment: KbDocumentSegment,
    fused: FusedCandidate,
    rerank_score: float | None,
) -> EvidenceChunk:
    return EvidenceChunk(
        segment_id=str(segment.id),
        document_id=str(segment.document_id),
        heading_path=segment.heading_path or "",
        indexed_text=segment.indexed_text,
        clean_text=segment.clean_text,
        vector_score=fused.vector_score,
        keyword_score=fused.keyword_score,
        rrf_score=fused.rrf_score,
        rerank_score=rerank_score,
    )
