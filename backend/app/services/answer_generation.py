from __future__ import annotations

from collections.abc import AsyncIterator
import re
import time
from typing import Protocol

from app.prompts.qa_prompts import (
    build_general_answer_messages,
    build_low_confidence_rag_answer_messages,
    build_rag_answer_messages,
)


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
    diagnostics: dict[str, object] | None = None,
) -> str:
    messages = build_rag_answer_messages(
        question=question,
        evidence=evidence,
        cautious=cautious,
    )
    _record_generation_input_diagnostics(
        diagnostics=diagnostics,
        mode="rag",
        messages=messages,
        evidence=evidence,
        cautious=cautious,
    )
    start = time.perf_counter()
    answer = await chat_client.chat(
        messages=messages,
        temperature=0.1,
    )
    _record_non_stream_output_diagnostics(diagnostics, answer, start)
    return answer


async def generate_low_confidence_rag_answer(
    chat_client: ChatClient,
    question: str,
    evidence: list[object],
    top_score: float | None,
    diagnostics: dict[str, object] | None = None,
) -> str:
    messages = build_low_confidence_rag_answer_messages(
        question=question,
        evidence=evidence,
        top_score=top_score,
    )
    _record_generation_input_diagnostics(
        diagnostics=diagnostics,
        mode="rag_low_confidence_supplement",
        messages=messages,
        evidence=evidence,
        cautious=True,
    )
    start = time.perf_counter()
    answer = await chat_client.chat(
        messages=messages,
        temperature=0.1,
    )
    _record_non_stream_output_diagnostics(diagnostics, answer, start)
    return answer


async def stream_rag_answer(
    chat_client: StreamingChatClient,
    question: str,
    evidence: list[object],
    cautious: bool,
    diagnostics: dict[str, object] | None = None,
) -> AsyncIterator[str]:
    messages = build_rag_answer_messages(
        question=question,
        evidence=evidence,
        cautious=cautious,
    )
    _record_generation_input_diagnostics(
        diagnostics=diagnostics,
        mode="rag",
        messages=messages,
        evidence=evidence,
        cautious=cautious,
    )
    tracker = _StreamDiagnosticsTracker(diagnostics)
    async for chunk in chat_client.chat_stream(
        messages=messages,
        temperature=0.1,
    ):
        tracker.record_chunk(chunk)
        yield chunk
    tracker.finish()


async def stream_low_confidence_rag_answer(
    chat_client: StreamingChatClient,
    question: str,
    evidence: list[object],
    top_score: float | None,
    diagnostics: dict[str, object] | None = None,
) -> AsyncIterator[str]:
    messages = build_low_confidence_rag_answer_messages(
        question=question,
        evidence=evidence,
        top_score=top_score,
    )
    _record_generation_input_diagnostics(
        diagnostics=diagnostics,
        mode="rag_low_confidence_supplement",
        messages=messages,
        evidence=evidence,
        cautious=True,
    )
    tracker = _StreamDiagnosticsTracker(diagnostics)
    async for chunk in chat_client.chat_stream(
        messages=messages,
        temperature=0.1,
    ):
        tracker.record_chunk(chunk)
        yield chunk
    tracker.finish()


async def generate_general_answer(
    chat_client: ChatClient,
    question: str,
    mode: str = "general",
    diagnostics: dict[str, object] | None = None,
) -> str:
    local_answer = _local_general_answer(question, mode)
    if local_answer is not None:
        _record_local_output_diagnostics(
            diagnostics=diagnostics,
            mode=mode,
            answer=local_answer,
        )
        return local_answer

    messages = build_general_answer_messages(question, mode=mode)
    _record_generation_input_diagnostics(
        diagnostics=diagnostics,
        mode=mode,
        messages=messages,
        evidence=[],
        cautious=False,
    )
    start = time.perf_counter()
    answer = await chat_client.chat(
        messages=messages,
        temperature=0.1,
    )
    _record_non_stream_output_diagnostics(diagnostics, answer, start)
    return answer


async def stream_general_answer(
    chat_client: StreamingChatClient,
    question: str,
    mode: str = "general",
    diagnostics: dict[str, object] | None = None,
) -> AsyncIterator[str]:
    local_answer = _local_general_answer(question, mode)
    if local_answer is not None:
        _record_local_output_diagnostics(
            diagnostics=diagnostics,
            mode=mode,
            answer=local_answer,
        )
        yield local_answer
        return

    messages = build_general_answer_messages(question, mode=mode)
    _record_generation_input_diagnostics(
        diagnostics=diagnostics,
        mode=mode,
        messages=messages,
        evidence=[],
        cautious=False,
    )
    tracker = _StreamDiagnosticsTracker(diagnostics)
    async for chunk in chat_client.chat_stream(
        messages=messages,
        temperature=0.1,
    ):
        tracker.record_chunk(chunk)
        yield chunk
    tracker.finish()


def _local_general_answer(question: str, mode: str) -> str | None:
    if mode != "chitchat":
        return None
    if _is_thanks_or_closing(question):
        return "不客气，有其他光伏运维相关问题可以继续问我。"
    return None


def _is_thanks_or_closing(question: str) -> bool:
    text = question.strip().lower()
    return bool(
        re.search(r"(谢谢|感谢|辛苦了|清楚|明白|有帮助|不错|挺好)", text)
        or re.fullmatch(r"(好的|好|明白了|知道了|没问题|可以了|先这样)[啊呀!！。.\s]*", text)
    )


def _record_local_output_diagnostics(
    diagnostics: dict[str, object] | None,
    mode: str,
    answer: str,
) -> None:
    if diagnostics is None:
        return
    diagnostics.clear()
    diagnostics.update(
        {
            "mode": mode,
            "streamed": True,
            "local_answer": True,
            "messages_count": 0,
            "prompt_chars": 0,
            "evidence_count": 0,
            "evidence_chars": 0,
            "cautious": False,
            "first_token_ms": 0,
            "total_ms": 0,
            "chunk_count": 1 if answer else 0,
            "output_chars": len(answer),
            "chars_per_second": None,
        }
    )


def _record_generation_input_diagnostics(
    diagnostics: dict[str, object] | None,
    mode: str,
    messages: list[dict[str, str]],
    evidence: list[object],
    cautious: bool,
) -> None:
    if diagnostics is None:
        return
    diagnostics.clear()
    diagnostics.update(
        {
            "mode": mode,
            "streamed": False,
            "messages_count": len(messages),
            "prompt_chars": sum(len(message.get("content", "")) for message in messages),
            "evidence_count": len(evidence),
            "evidence_chars": sum(len(getattr(item, "clean_text", "") or "") for item in evidence),
            "cautious": cautious,
        }
    )


def _record_non_stream_output_diagnostics(
    diagnostics: dict[str, object] | None,
    answer: str,
    start: float,
) -> None:
    total_ms = _elapsed_ms(start)
    output_chars = len(answer)
    if diagnostics is None:
        return
    diagnostics.update(
        {
            "streamed": False,
            "first_token_ms": total_ms,
            "total_ms": total_ms,
            "chunk_count": 1 if answer else 0,
            "output_chars": output_chars,
            "chars_per_second": _chars_per_second(output_chars, total_ms),
        }
    )


class _StreamDiagnosticsTracker:
    def __init__(self, diagnostics: dict[str, object] | None) -> None:
        self._diagnostics = diagnostics
        self._start = time.perf_counter()
        self._first_token_ms: int | None = None
        self._chunk_count = 0
        self._output_chars = 0
        if self._diagnostics is not None:
            self._diagnostics["streamed"] = True

    def record_chunk(self, chunk: str) -> None:
        if self._first_token_ms is None:
            self._first_token_ms = _elapsed_ms(self._start)
            if self._diagnostics is not None:
                self._diagnostics["first_token_ms"] = self._first_token_ms
        self._chunk_count += 1
        self._output_chars += len(chunk)

    def finish(self) -> None:
        total_ms = _elapsed_ms(self._start)
        if self._diagnostics is None:
            return
        self._diagnostics.update(
            {
                "streamed": True,
                "first_token_ms": self._first_token_ms,
                "total_ms": total_ms,
                "chunk_count": self._chunk_count,
                "output_chars": self._output_chars,
                "chars_per_second": _chars_per_second(self._output_chars, total_ms),
            }
        )


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _chars_per_second(chars: int, duration_ms: int) -> float | None:
    if duration_ms <= 0:
        return None
    return round(chars / (duration_ms / 1000), 2)
