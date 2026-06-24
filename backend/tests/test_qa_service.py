from types import SimpleNamespace
import json
import logging
import uuid

import pytest

from app.models.rag import (
    AnswerType,
    QaRecord,
    QaReference,
    QaSession,
    QaTraceStep,
    QaUnanswered,
)
from app.services.query_understanding import Intent, QueryUnderstandingResult
from app.services.qa_service import QaDependencies, answer_question


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
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def understand(self, question):
        self.calls.append(question)
        return self.result


class FakeAnswerClient:
    def __init__(self):
        self.rag_calls = []
        self.general_calls = []

    async def generate_rag(self, question, evidence, cautious):
        self.rag_calls.append(
            {"question": question, "evidence": evidence, "cautious": cautious}
        )
        return "RAG answer"

    async def generate_general(self, question):
        self.general_calls.append(question)
        return "General answer"


class FakeRetriever:
    def __init__(self, evidence):
        self.evidence = evidence
        self.calls = []

    async def retrieve(self, query):
        self.calls.append(query)
        return self.evidence


def make_understanding(intent=Intent.knowledge_base_qa, **overrides):
    values = {
        "intent": intent,
        "confidence": 1.0,
        "should_use_knowledge_base": intent == Intent.knowledge_base_qa,
        "normalized_question": "逆变器绝缘阻抗低如何排查？",
        "search_query": "逆变器 绝缘阻抗低 排查",
        "refusal_reason": None,
        "reason": "test route",
    }
    values.update(overrides)
    return QueryUnderstandingResult(**values)


def make_evidence(score=0.8):
    return [
        SimpleNamespace(
            segment_id="segment-1",
            document_id="document-1",
            heading_path="03_线缆接头与绝缘故障 > 4. 绝缘阻抗问题",
            clean_text="绝缘阻抗问题可以理解为直流线破皮并接地。",
            vector_score=0.6,
            keyword_score=0.5,
            rrf_score=0.03,
            rerank_score=score,
        )
    ]


def make_dependencies(understanding, evidence):
    return QaDependencies(
        understanding_client=FakeUnderstandingClient(understanding),
        retriever=FakeRetriever(evidence),
        answer_client=FakeAnswerClient(),
    )


def get_added(session, model_type):
    return [item for item in session.added if isinstance(item, model_type)]


@pytest.mark.asyncio
async def test_answer_question_persists_rag_answer_reference_and_decision_metadata():
    session = FakeSession()
    dependencies = make_dependencies(make_understanding(), make_evidence(score=0.8))

    response = await answer_question(
        session=session,
        question="逆变器绝缘阻抗低怎么排查？",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    records = get_added(session, QaRecord)
    assert response.answer_type == "rag"
    assert response.references[0].rerank_score == 0.8
    assert response.decision["intent"] == "knowledge_base_qa"
    assert response.decision["normalized_question"] == "逆变器绝缘阻抗低如何排查？"
    assert response.decision["search_query"] == "逆变器 绝缘阻抗低 排查"
    assert response.decision["route"] == "rag"
    assert response.decision["used_knowledge_base"] is True
    assert response.decision["refusal_reason"] is None
    assert response.decision["top1_rerank_score"] == 0.8
    assert response.decision["threshold"] == 0.2
    assert response.decision["timings_ms"]["total_ms"] >= 0
    assert "retrieve_evidence_ms" in response.decision["timings_ms"]
    assert dependencies.retriever.calls == ["逆变器 绝缘阻抗低 排查"]
    assert dependencies.answer_client.rag_calls[0]["cautious"] is False
    assert any(isinstance(item, QaSession) for item in session.added)
    assert records and records[0].answer_type == AnswerType.rag
    assert records[0].session_id is not None
    assert any(isinstance(item, QaReference) for item in session.added)
    assert session.commits == 1


@pytest.mark.asyncio
async def test_answer_question_persists_trace_steps_for_rag_route():
    session = FakeSession()
    dependencies = make_dependencies(make_understanding(), make_evidence(score=0.8))

    await answer_question(
        session=session,
        question="How should I troubleshoot low inverter insulation resistance?",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    trace_steps = get_added(session, QaTraceStep)

    assert {step.step_name for step in trace_steps} >= {
        "load_history",
        "rewrite_question",
        "understand_intent",
        "retrieve_evidence",
        "answer_generation",
        "summary_update",
        "db_commit",
    }
    assert all(step.qa_record_id is not None for step in trace_steps)
    assert all(step.trace_id for step in trace_steps)


@pytest.mark.asyncio
async def test_answer_question_writes_structured_debug_logs_when_enabled(caplog):
    session = FakeSession()
    dependencies = make_dependencies(make_understanding(), make_evidence(score=0.8))

    with caplog.at_level(logging.INFO, logger="app.services.qa_service"):
        response = await answer_question(
            session=session,
            question="逆变器绝缘阻抗低怎么排查？",
            dependencies=dependencies,
            min_rerank_score=0.2,
            strong_rerank_score=0.6,
            reference_top_k=5,
            qa_debug_log_enabled=True,
            qa_debug_question_preview_chars=10,
        )

    payloads = [
        json.loads(record.message.removeprefix("qa_debug "))
        for record in caplog.records
        if record.message.startswith("qa_debug ")
    ]

    assert response.answer_type == "rag"
    assert {payload["event"] for payload in payloads} >= {
        "qa.request.start",
        "qa.intent.understood",
        "qa.evidence.retrieved",
        "qa.evidence.filtered",
        "qa.request.finish",
    }
    finish = next(payload for payload in payloads if payload["event"] == "qa.request.finish")
    assert finish["route"] == "rag"
    assert finish["answer_type"] == "rag"
    assert finish["references_count"] == 1


@pytest.mark.asyncio
async def test_answer_question_returns_general_llm_with_empty_references():
    session = FakeSession()
    understanding = make_understanding(
        intent=Intent.general_explanation,
        confidence=0.82,
        should_use_knowledge_base=False,
        normalized_question="什么是无功功率？",
        search_query="",
        reason="general concept",
    )
    dependencies = make_dependencies(understanding, [])

    response = await answer_question(
        session=session,
        question="什么是无功功率？",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    records = get_added(session, QaRecord)
    assert response.answer_type == "general_llm"
    assert response.references == []
    assert response.decision["route"] == "general_llm"
    assert response.decision["used_knowledge_base"] is False
    assert response.decision["refusal_reason"] is None
    assert dependencies.retriever.calls == []
    assert dependencies.answer_client.general_calls == ["什么是无功功率？"]
    assert records and records[0].answer_type == AnswerType.general_llm
    assert not get_added(session, QaUnanswered)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("intent", "reason"),
    [
        (Intent.invalid_input, "invalid_input"),
        (Intent.realtime_external, "realtime_external"),
        (Intent.out_of_scope, "out_of_scope"),
    ],
)
async def test_answer_question_refuses_non_answerable_routes_and_records_unanswered(
    intent, reason
):
    session = FakeSession()
    understanding = make_understanding(
        intent=intent,
        confidence=1.0,
        should_use_knowledge_base=False,
        normalized_question="",
        search_query="",
        refusal_reason=reason,
        reason=f"hard rule {reason}",
    )
    dependencies = make_dependencies(understanding, [])

    response = await answer_question(
        session=session,
        question="今天股价是多少？",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    records = get_added(session, QaRecord)
    unanswered = get_added(session, QaUnanswered)
    assert response.answer_type == "refused"
    assert response.references == []
    assert response.decision["route"] == "refused"
    assert response.decision["used_knowledge_base"] is False
    assert response.decision["refusal_reason"] == reason
    assert dependencies.retriever.calls == []
    assert records and records[0].answer_type == AnswerType.refused
    assert unanswered and unanswered[0].reason == reason
    assert session.commits == 1


@pytest.mark.asyncio
async def test_answer_question_refuses_low_confidence_rag_and_records_unanswered():
    session = FakeSession()
    dependencies = make_dependencies(make_understanding(), make_evidence(score=0.01))

    response = await answer_question(
        session=session,
        question="逆变器绝缘阻抗低怎么排查？",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    records = get_added(session, QaRecord)
    unanswered = get_added(session, QaUnanswered)
    assert response.answer_type == "refused"
    assert response.references == []
    assert response.decision["route"] == "refused"
    assert response.decision["used_knowledge_base"] is True
    assert response.decision["refusal_reason"] == "low_confidence"
    assert response.decision["top1_rerank_score"] == 0.01
    assert response.decision["threshold"] == 0.2
    assert not get_added(session, QaReference)
    assert records and records[0].answer_type == AnswerType.refused
    assert unanswered and unanswered[0].record_id == records[0].id
    assert dependencies.answer_client.rag_calls == []
    assert session.commits == 1
