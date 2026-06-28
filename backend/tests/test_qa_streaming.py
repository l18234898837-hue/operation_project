from types import SimpleNamespace
import asyncio
import json
import logging
import uuid

import pytest

from app.models.rag import QaSession
from app.schemas.qa import QaAskResponse
from app.services.qa_service import QaDependencies
from app.services.qa_streaming import (
    format_sse_event,
    stream_qa_events,
    stream_response_events,
)
from app.services.query_understanding import Intent, QueryUnderstandingResult


class FakeSession:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.flushes = 0
        self.rollbacks = 0

    def add(self, item):
        self.added.append(item)

    def flush(self):
        self.flushes += 1
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = uuid.uuid4()

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FakeUnderstandingClient:
    async def understand(self, question):
        return QueryUnderstandingResult(
            intent=Intent.knowledge_base_qa,
            confidence=1.0,
            should_use_knowledge_base=True,
            normalized_question=question,
            search_query=question,
            refusal_reason=None,
            reason="test",
        )


class FakeRetriever:
    async def retrieve(self, query):
        return [
            SimpleNamespace(
                segment_id=str(uuid.uuid4()),
                document_id="document-1",
                heading_path="03_线缆接头与绝缘故障 > 4. 绝缘阻抗问题",
                clean_text="绝缘阻抗低可能与直流线缆破皮有关。",
                vector_score=0.6,
                keyword_score=0.5,
                rrf_score=0.03,
                rerank_score=0.9,
            )
        ]


class LowConfidenceRetriever:
    async def retrieve(self, query):
        return [
            SimpleNamespace(
                segment_id=str(uuid.uuid4()),
                document_id="document-1",
                heading_path="03_线缆接头与绝缘故障 > 5. 端子与接头问题",
                clean_text="接头松动、氧化或接触不良可能导致温度升高。",
                vector_score=0.6,
                keyword_score=0.5,
                rrf_score=0.03,
                rerank_score=0.01,
            )
        ]


class FakeStreamingAnswerClient:
    async def stream_rag(self, question, evidence, cautious):
        yield "第一段"
        yield "第二段"

    async def generate_rag(self, question, evidence, cautious):
        return "第一段第二段"

    async def generate_general(self, question, mode="general"):
        return "通用回答"


class LowConfidenceStreamingAnswerClient(FakeStreamingAnswerClient):
    async def stream_low_confidence_rag(self, question, evidence, top_score):
        yield "能参考到的资料"
        yield "结合现场经验的处理建议"

    async def generate_low_confidence_rag(self, question, evidence, top_score):
        return "能参考到的资料结合现场经验的处理建议"


class SlowStreamingAnswerClient(FakeStreamingAnswerClient):
    async def stream_rag(self, question, evidence, cautious):
        await asyncio.sleep(2.2)
        yield "慢速回答"


def test_format_sse_event_outputs_valid_sse_frame():
    frame = format_sse_event(
        event="status",
        data={"message": "正在检索知识库"},
    )

    assert frame.startswith("event: status\n")
    assert "data: " in frame
    assert frame.endswith("\n\n")
    payload = json.loads(frame.split("data: ", 1)[1])
    assert payload["message"] == "正在检索知识库"


@pytest.mark.asyncio
async def test_stream_response_events_yields_answer_delta_before_done():
    response = QaAskResponse(
        session_id=uuid.uuid4(),
        trace_id="trace-1",
        answer_type="rag",
        intent="knowledge_base_qa",
        answer="测试答案",
        confidence=0.8,
        references=[],
        decision={"route": "rag"},
    )

    events = [event async for event in stream_response_events(response)]

    answer_index = next(
        index for index, event in enumerate(events) if "event: answer_delta" in event
    )
    done_index = next(
        index for index, event in enumerate(events) if "event: done" in event
    )

    assert answer_index < done_index


@pytest.mark.asyncio
async def test_stream_qa_events_yields_streamed_answer_delta_before_done():
    session = FakeSession()
    dependencies = QaDependencies(
        understanding_client=FakeUnderstandingClient(),
        retriever=FakeRetriever(),
        answer_client=FakeStreamingAnswerClient(),
    )

    events = [
        event
        async for event in stream_qa_events(
            session=session,
            question="逆变器绝缘阻抗低怎么排查？",
            dependencies=dependencies,
            min_rerank_score=0.2,
            strong_rerank_score=0.6,
            reference_top_k=5,
        )
    ]

    answer_events = [event for event in events if "event: answer_delta" in event]
    status_events = [event for event in events if "event: status" in event]
    done_index = next(
        index for index, event in enumerate(events) if "event: done" in event
    )

    assert status_events
    assert any("正在查找光伏运维知识库" in event for event in status_events)
    assert any("已找到" in event for event in status_events)
    assert len(answer_events) == 2
    assert "第一段" in answer_events[0]
    assert "第二段" in answer_events[1]
    assert events.index(status_events[0]) < events.index(answer_events[0])
    assert events.index(answer_events[0]) < done_index
    assert any(isinstance(item, QaSession) for item in session.added)


@pytest.mark.asyncio
async def test_stream_qa_events_streams_low_confidence_supplement_answer():
    session = FakeSession()
    dependencies = QaDependencies(
        understanding_client=FakeUnderstandingClient(),
        retriever=LowConfidenceRetriever(),
        answer_client=LowConfidenceStreamingAnswerClient(),
    )

    events = [
        event
        async for event in stream_qa_events(
            session=session,
            question="处理前需要注意哪些安全事项？",
            dependencies=dependencies,
            min_rerank_score=0.2,
            strong_rerank_score=0.6,
            reference_top_k=5,
        )
    ]

    answer_events = [event for event in events if "event: answer_delta" in event]
    done_index = next(
        index for index, event in enumerate(events) if "event: done" in event
    )

    assert len(answer_events) == 2
    assert "能参考到的资料" in answer_events[0]
    assert "结合现场经验的处理建议" in answer_events[1]
    assert events.index(answer_events[0]) < done_index


@pytest.mark.asyncio
async def test_stream_qa_events_logs_full_answer_on_sse_finish(caplog):
    session = FakeSession()
    dependencies = QaDependencies(
        understanding_client=FakeUnderstandingClient(),
        retriever=FakeRetriever(),
        answer_client=FakeStreamingAnswerClient(),
    )

    with caplog.at_level(logging.INFO, logger="app.services.qa_streaming"):
        [
            event
            async for event in stream_qa_events(
                session=session,
                question="逆变器绝缘阻抗低怎么排查？",
                dependencies=dependencies,
                min_rerank_score=0.2,
                strong_rerank_score=0.6,
                reference_top_k=5,
                qa_debug_log_enabled=True,
            )
        ]

    payloads = [
        json.loads(record.message.removeprefix("qa_debug "))
        for record in caplog.records
        if record.message.startswith("qa_debug ")
    ]
    finish = next(payload for payload in payloads if payload["event"] == "qa.sse.finish")

    assert finish["answer"] == "第一段第二段"
    assert "answer_preview" not in finish


@pytest.mark.asyncio
async def test_stream_qa_events_emits_heartbeat_while_waiting_for_answer():
    session = FakeSession()
    dependencies = QaDependencies(
        understanding_client=FakeUnderstandingClient(),
        retriever=FakeRetriever(),
        answer_client=SlowStreamingAnswerClient(),
    )

    events = [
        event
        async for event in stream_qa_events(
            session=session,
            question="逆变器绝缘阻抗低怎么排查？",
            dependencies=dependencies,
            min_rerank_score=0.2,
            strong_rerank_score=0.6,
            reference_top_k=5,
        )
    ]

    heartbeat_events = [
        event
        for event in events
        if "event: status" in event and '"heartbeat": true' in event
    ]
    answer_index = next(
        index for index, event in enumerate(events) if "event: answer_delta" in event
    )

    assert heartbeat_events
    assert "正在分析问题中的设备、故障和场景信息" in heartbeat_events[0]
    assert events.index(heartbeat_events[0]) < answer_index
