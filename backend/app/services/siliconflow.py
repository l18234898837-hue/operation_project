from collections.abc import AsyncIterator
from dataclasses import dataclass
import json

import httpx


@dataclass(frozen=True)
class RerankResult:
    index: int
    score: float
    text: str | None


class SiliconFlowEmbeddingClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        model: str,
        dimension: int,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._model = model
        self._dimension = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.post(
            "/embeddings",
            headers=self._headers(),
            json={
                "model": self._model,
                "input": texts,
                "encoding_format": "float",
            },
        )
        response.raise_for_status()

        vectors: list[list[float]] = []
        for item in sorted(response.json()["data"], key=lambda value: value["index"]):
            embedding = item["embedding"]
            if len(embedding) != self._dimension:
                raise ValueError(
                    f"Expected embedding dimension {self._dimension}, got {len(embedding)}"
                )
            vectors.append(embedding)

        return vectors

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}


class SiliconFlowRerankClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        model: str,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._model = model

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> list[RerankResult]:
        response = await self._client.post(
            "/rerank",
            headers=self._headers(),
            json={
                "model": self._model,
                "query": query,
                "documents": documents,
                "top_n": top_n,
                "return_documents": True,
            },
        )
        response.raise_for_status()

        return [
            RerankResult(
                index=item["index"],
                score=item["relevance_score"],
                text=item.get("document", {}).get("text"),
            )
            for item in response.json()["results"]
        ]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}


class SiliconFlowChatClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        model: str,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._model = model

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
    ) -> str:
        response = await self._client.post(
            "/chat/completions",
            headers=self._headers(),
            json={
                "model": self._model,
                "messages": messages,
                "temperature": temperature,
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
    ) -> AsyncIterator[str]:
        async with self._client.stream(
            "POST",
            "/chat/completions",
            headers=self._headers(),
            json={
                "model": self._model,
                "messages": messages,
                "temperature": temperature,
                "stream": True,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line.removeprefix("data:").strip()
                if payload == "[DONE]":
                    break
                data = json.loads(payload)
                delta = data["choices"][0].get("delta") or {}
                content = delta.get("content")
                if content:
                    yield content

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}
