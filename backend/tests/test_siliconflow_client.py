import json

import httpx
import pytest

from app.services.siliconflow import (
    SiliconFlowEmbeddingClient,
    SiliconFlowRerankClient,
)


@pytest.mark.asyncio
async def test_embedding_client_validates_dimension_and_sends_expected_request():
    captured_request: httpx.Request | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "index": 0,
                        "embedding": [float(i) for i in range(1024)],
                    }
                ]
            },
        )

    async with httpx.AsyncClient(
        base_url="https://api.siliconflow.cn/v1",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        client = SiliconFlowEmbeddingClient(
            client=http_client,
            api_key="test-key",
            model="BAAI/bge-m3",
            dimension=1024,
        )

        embeddings = await client.embed(["PV overvoltage"])

    assert embeddings == [[float(i) for i in range(1024)]]
    assert captured_request is not None
    assert captured_request.method == "POST"
    assert captured_request.url.path == "/v1/embeddings"
    assert captured_request.headers["Authorization"] == "Bearer test-key"
    assert captured_request.read()
    assert json.loads(captured_request.content) == {
        "model": "BAAI/bge-m3",
        "input": ["PV overvoltage"],
        "encoding_format": "float",
    }


@pytest.mark.asyncio
async def test_embedding_client_sorts_response_data_by_index():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [2.0, 3.0]},
                    {"index": 0, "embedding": [0.0, 1.0]},
                ]
            },
        )

    async with httpx.AsyncClient(
        base_url="https://api.siliconflow.cn/v1",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        client = SiliconFlowEmbeddingClient(
            client=http_client,
            api_key="test-key",
            model="BAAI/bge-m3",
            dimension=2,
        )

        embeddings = await client.embed(["first", "second"])

    assert embeddings == [[0.0, 1.0], [2.0, 3.0]]


@pytest.mark.asyncio
async def test_embedding_client_raises_value_error_on_dimension_mismatch():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [1.0, 2.0, 3.0]}]},
        )

    async with httpx.AsyncClient(
        base_url="https://api.siliconflow.cn/v1",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        client = SiliconFlowEmbeddingClient(
            client=http_client,
            api_key="test-key",
            model="BAAI/bge-m3",
            dimension=2,
        )

        with pytest.raises(ValueError, match="Expected embedding dimension 2"):
            await client.embed(["bad vector"])


@pytest.mark.asyncio
async def test_rerank_client_parses_scores_and_document_text_and_sends_payload():
    captured_request: httpx.Request | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "index": 2,
                        "relevance_score": 0.98,
                        "document": {"text": "best document"},
                    },
                    {"index": 0, "relevance_score": 0.42},
                ]
            },
        )

    async with httpx.AsyncClient(
        base_url="https://api.siliconflow.cn/v1",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        client = SiliconFlowRerankClient(
            client=http_client,
            api_key="test-key",
            model="BAAI/bge-reranker-v2-m3",
        )

        results = await client.rerank(
            query="PV alarm",
            documents=["first", "second", "third"],
            top_n=2,
        )

    assert [result.index for result in results] == [2, 0]
    assert [result.score for result in results] == [0.98, 0.42]
    assert [result.text for result in results] == ["best document", None]
    assert captured_request is not None
    assert captured_request.method == "POST"
    assert captured_request.url.path == "/v1/rerank"
    assert captured_request.headers["Authorization"] == "Bearer test-key"
    assert captured_request.read()
    assert json.loads(captured_request.content) == {
        "model": "BAAI/bge-reranker-v2-m3",
        "query": "PV alarm",
        "documents": ["first", "second", "third"],
        "top_n": 2,
        "return_documents": True,
    }


@pytest.mark.asyncio
async def test_http_4xx_raises_http_status_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, request=request, json={"message": "unauthorized"})

    async with httpx.AsyncClient(
        base_url="https://api.siliconflow.cn/v1",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        client = SiliconFlowEmbeddingClient(
            client=http_client,
            api_key="bad-key",
            model="BAAI/bge-m3",
            dimension=1024,
        )

        with pytest.raises(httpx.HTTPStatusError):
            await client.embed(["unauthorized"])
