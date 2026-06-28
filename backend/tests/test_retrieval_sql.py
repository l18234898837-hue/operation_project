from types import SimpleNamespace

import pytest

from app.services.retrieval import (
    build_keyword_search_sql,
    build_vector_search_sql,
    retrieve_evidence,
)


def test_vector_search_sql_uses_cosine_distance():
    sql = build_vector_search_sql(limit=20)

    assert "embedding <=> :query_embedding" in sql
    assert "LIMIT :limit" in sql


def test_keyword_search_sql_uses_keyword_text():
    sql = build_keyword_search_sql(limit=20)

    assert "keyword_text" in sql
    assert "websearch_to_tsquery" not in sql
    assert "to_tsquery('simple', :query_text)" in sql
    assert "LIMIT :limit" in sql


@pytest.mark.asyncio
async def test_retrieve_evidence_binds_query_embedding_as_pgvector():
    session = FakeSession(vector_rows=[], keyword_rows=[], segments=[])

    await retrieve_evidence(
        session=session,
        query="inverter fault",
        embedding_client=FakeEmbeddingClient(),
        rerank_client=None,
        vector_top_k=10,
        keyword_top_k=10,
        rrf_top_k=10,
        final_top_k=5,
        rrf_k=60,
    )

    vector_statement = session.execute_calls[0]["sql"]
    assert vector_statement._bindparams["query_embedding"].type.dim == 1024


@pytest.mark.asyncio
async def test_retrieve_evidence_tokenizes_chinese_keyword_query_param():
    session = FakeSession(vector_rows=[], keyword_rows=[], segments=[])

    await retrieve_evidence(
        session=session,
        query="SVG 无功补偿异常怎么处理？",
        embedding_client=FakeEmbeddingClient(),
        rerank_client=None,
        vector_top_k=10,
        keyword_top_k=10,
        rrf_top_k=10,
        final_top_k=5,
        rrf_k=60,
    )

    keyword_params = session.execute_calls[1]["params"]
    assert keyword_params["query_text"] == "SVG | 无功 | 补偿 | 异常 | 怎么 | 处理"


@pytest.mark.asyncio
async def test_retrieve_evidence_skips_keyword_search_when_query_has_no_terms():
    session = FakeSession(vector_rows=[], keyword_rows=[], segments=[])

    await retrieve_evidence(
        session=session,
        query="!!!",
        embedding_client=FakeEmbeddingClient(),
        rerank_client=None,
        vector_top_k=10,
        keyword_top_k=10,
        rrf_top_k=10,
        final_top_k=5,
        rrf_k=60,
    )

    assert len(session.execute_calls) == 1


@pytest.mark.asyncio
async def test_retrieve_evidence_returns_empty_without_rerank_when_no_rows():
    session = FakeSession(vector_rows=[], keyword_rows=[], segments=[])
    embedding_client = FakeEmbeddingClient()
    rerank_client = FakeRerankClient([])

    evidence = await retrieve_evidence(
        session=session,
        query="  inverter   fault  ",
        embedding_client=embedding_client,
        rerank_client=rerank_client,
        vector_top_k=10,
        keyword_top_k=10,
        rrf_top_k=10,
        final_top_k=5,
        rrf_k=60,
    )

    assert evidence == []
    assert embedding_client.calls == [["inverter fault"]]
    assert rerank_client.calls == []


@pytest.mark.asyncio
async def test_retrieve_evidence_returns_empty_without_rerank_when_segments_missing():
    rerank_client = FakeRerankClient([])

    evidence = await retrieve_evidence(
        session=FakeSession(
            vector_rows=[SimpleNamespace(segment_id="missing", score=0.9, rank=1)],
            keyword_rows=[],
            segments=[],
        ),
        query="inverter fault",
        embedding_client=FakeEmbeddingClient(),
        rerank_client=rerank_client,
        vector_top_k=10,
        keyword_top_k=10,
        rrf_top_k=10,
        final_top_k=5,
        rrf_k=60,
    )

    assert evidence == []
    assert rerank_client.calls == []


@pytest.mark.asyncio
async def test_retrieve_evidence_preserves_fused_order_and_maps_scores_without_rerank():
    segment_a = make_segment("a", "doc-1", "Root > A", "indexed A", "clean A")
    segment_b = make_segment("b", "doc-2", "Root > B", "indexed B", "clean B")
    segment_c = make_segment("c", "doc-3", "Root > C", "indexed C", "clean C")
    session = FakeSession(
        vector_rows=[
            SimpleNamespace(segment_id="a", score=0.9, rank=1),
            SimpleNamespace(segment_id="b", score=0.8, rank=2),
        ],
        keyword_rows=[
            SimpleNamespace(segment_id="c", score=12.0, rank=1),
            SimpleNamespace(segment_id="a", score=8.0, rank=2),
        ],
        segments=[segment_b, segment_c, segment_a],
    )

    evidence = await retrieve_evidence(
        session=session,
        query="  inverter   fault  ",
        embedding_client=FakeEmbeddingClient(),
        rerank_client=None,
        vector_top_k=2,
        keyword_top_k=2,
        rrf_top_k=3,
        final_top_k=3,
        rrf_k=60,
    )

    assert [chunk.segment_id for chunk in evidence] == ["a", "c", "b"]
    assert [chunk.document_id for chunk in evidence] == ["doc-1", "doc-3", "doc-2"]
    assert evidence[0].vector_score == 0.9
    assert evidence[0].keyword_score == 8.0
    assert evidence[0].rerank_score is None
    assert evidence[1].vector_score is None
    assert evidence[1].keyword_score == 12.0
    assert evidence[2].vector_score == 0.8
    assert evidence[2].keyword_score is None


@pytest.mark.asyncio
async def test_retrieve_evidence_applies_rerank_order_and_scores():
    segment_a = make_segment("a", "doc-1", "Root > A", "indexed A", "clean A")
    segment_b = make_segment("b", "doc-2", "Root > B", "indexed B", "clean B")
    segment_c = make_segment("c", "doc-3", "Root > C", "indexed C", "clean C")
    rerank_client = FakeRerankClient(
        [
            SimpleNamespace(index=1, score=0.98),
            SimpleNamespace(index=0, score=0.74),
        ]
    )

    evidence = await retrieve_evidence(
        session=FakeSession(
            vector_rows=[
                SimpleNamespace(segment_id="a", score=0.9, rank=1),
                SimpleNamespace(segment_id="b", score=0.8, rank=2),
            ],
            keyword_rows=[
                SimpleNamespace(segment_id="c", score=12.0, rank=1),
                SimpleNamespace(segment_id="a", score=8.0, rank=2),
            ],
            segments=[segment_a, segment_b, segment_c],
        ),
        query="  inverter   fault  ",
        embedding_client=FakeEmbeddingClient(),
        rerank_client=rerank_client,
        vector_top_k=2,
        keyword_top_k=2,
        rrf_top_k=3,
        final_top_k=2,
        rrf_k=60,
    )

    assert [chunk.segment_id for chunk in evidence] == ["c", "a"]
    assert [chunk.rerank_score for chunk in evidence] == [0.98, 0.74]
    assert rerank_client.calls == [
        {
            "query": "inverter fault",
            "documents": ["indexed A", "indexed C", "indexed B"],
            "top_n": 2,
        }
    ]


@pytest.mark.asyncio
async def test_retrieve_evidence_records_stage_diagnostics():
    segment_a = make_segment("a", "doc-1", "Root > A", "indexed A", "clean A")
    diagnostics = {}

    evidence = await retrieve_evidence(
        session=FakeSession(
            vector_rows=[SimpleNamespace(segment_id="a", score=0.9, rank=1)],
            keyword_rows=[SimpleNamespace(segment_id="a", score=8.0, rank=1)],
            segments=[segment_a],
        ),
        query="inverter fault",
        embedding_client=FakeEmbeddingClient(),
        rerank_client=FakeRerankClient([SimpleNamespace(index=0, score=0.91)]),
        vector_top_k=2,
        keyword_top_k=2,
        rrf_top_k=3,
        final_top_k=2,
        rrf_k=60,
        diagnostics=diagnostics,
    )

    assert [chunk.segment_id for chunk in evidence] == ["a"]
    assert diagnostics["vector_rows_count"] == 1
    assert diagnostics["keyword_rows_count"] == 1
    assert diagnostics["fused_count"] == 1
    assert diagnostics["loaded_segments_count"] == 1
    assert diagnostics["rerank_enabled"] is True
    assert diagnostics["rerank_documents_count"] == 1
    assert diagnostics["rerank_results_count"] == 1
    assert diagnostics["result_count"] == 1
    for key in {
        "query_prepare_ms",
        "embedding_ms",
        "vector_search_ms",
        "keyword_search_ms",
        "rrf_ms",
        "load_segments_ms",
        "rerank_ms",
        "build_evidence_ms",
        "total_internal_ms",
    }:
        assert key in diagnostics
        assert diagnostics[key] >= 0


def test_query_script_imports_safely_without_executing_main():
    import backend.scripts.query_knowledge_base as query_script

    assert hasattr(query_script, "main")


class FakeEmbeddingClient:
    def __init__(self):
        self.calls = []

    async def embed(self, texts):
        self.calls.append(texts)
        return [[0.1, 0.2, 0.3]]


class FakeRerankClient:
    def __init__(self, results):
        self.results = results
        self.calls = []

    async def rerank(self, query, documents, top_n):
        self.calls.append({"query": query, "documents": documents, "top_n": top_n})
        return self.results


class FakeSession:
    def __init__(self, vector_rows, keyword_rows, segments):
        self._execute_results = [
            FakeExecuteResult(vector_rows),
            FakeExecuteResult(keyword_rows),
        ]
        self._segments = segments
        self.execute_calls = []

    def execute(self, sql, params):
        self.execute_calls.append({"sql": sql, "params": params})
        return self._execute_results.pop(0)

    def query(self, model):
        return FakeQuery(self._segments)


class FakeExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeQuery:
    def __init__(self, segments):
        self._segments = segments

    def filter(self, expression):
        return self

    def all(self):
        return self._segments


def make_segment(segment_id, document_id, heading_path, indexed_text, clean_text):
    return SimpleNamespace(
        id=segment_id,
        document_id=document_id,
        heading_path=heading_path,
        indexed_text=indexed_text,
        clean_text=clean_text,
    )
