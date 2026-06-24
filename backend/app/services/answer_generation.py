from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from app.prompts.qa_prompts import build_general_answer_messages, build_rag_answer_messages


class ChatClient(Protocol):
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
    ) -> str:
        ...


class StreamingChatClient(ChatClient, Protocol):
    def chat_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
    ) -> AsyncIterator[str]:
        ...


async def generate_rag_answer(
    chat_client: ChatClient,
    question: str,
    evidence: list[object],
    cautious: bool,
) -> str:
    return await chat_client.chat(
        messages=build_rag_answer_messages(
            question=question,
            evidence=evidence,
            cautious=cautious,
        ),
        temperature=0.1,
    )


async def stream_rag_answer(
    chat_client: StreamingChatClient,
    question: str,
    evidence: list[object],
    cautious: bool,
) -> AsyncIterator[str]:
    async for chunk in chat_client.chat_stream(
        messages=build_rag_answer_messages(
            question=question,
            evidence=evidence,
            cautious=cautious,
        ),
        temperature=0.1,
    ):
        yield chunk


async def generate_general_answer(
    chat_client: ChatClient,
    question: str,
) -> str:
    return await chat_client.chat(
        messages=build_general_answer_messages(question),
        temperature=0.1,
    )
