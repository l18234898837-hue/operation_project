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
from app.services.conversation_rewrite import StandaloneQuestionResult
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

    def get(self, model_type, item_id):
        for item in self.added:
            if isinstance(item, model_type) and getattr(item, "id", None) == item_id:
                return item
        return None

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
        self.low_confidence_rag_calls = []
        self.general_calls = []

    async def generate_rag(self, question, evidence, cautious):
        self.rag_calls.append(
            {"question": question, "evidence": evidence, "cautious": cautious}
        )
        return "RAG answer"

    async def generate_low_confidence_rag(self, question, evidence, top_score):
        self.low_confidence_rag_calls.append(
            {"question": question, "evidence": evidence, "top_score": top_score}
        )
        return "Low confidence RAG answer with model supplemental advice"

    async def generate_general(self, question, mode="general"):
        self.general_calls.append({"question": question, "mode": mode})
        return "General answer"


class FakeRetriever:
    def __init__(self, evidence):
        self.evidence = evidence
        self.calls = []

    async def retrieve(self, query):
        self.calls.append(query)
        return self.evidence


class FakeContextRewriter:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def rewrite(self, question, context):
        self.calls.append({"question": question, "context": context})
        return self.result


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


def make_evidence_scores(*scores):
    evidence = []
    for index, score in enumerate(scores, start=1):
        evidence.append(
            SimpleNamespace(
                segment_id=f"segment-{index}",
                document_id=f"document-{index}",
                heading_path="03_线缆接头与绝缘故障 > 5. 端子与接头问题",
                clean_text="接头松动、氧化或接触不良可能导致温度升高。",
                vector_score=0.6,
                keyword_score=0.5,
                rrf_score=0.03,
                rerank_score=score,
            )
        )
    return evidence


def make_communication_mismatch_evidence(score=0.67):
    return [
        SimpleNamespace(
            segment_id="segment-communication-mismatch",
            document_id="document-communication-mismatch",
            heading_path="01_逆变器故障与维护 > 3. 常见故障与处理 > 3.2 电网过压或欠压",
            clean_text="电网电压过高或过低会导致逆变器保护停机，应检查并网点电压和电网波动情况。",
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


def make_existing_record(question="上一轮问题", answer="上一轮回答"):
    record = QaRecord(
        session_id=uuid.uuid4(),
        question=question,
        normalized_question=question,
        answer=answer,
        answer_type=AnswerType.rag,
    )
    record.id = uuid.uuid4()
    return record


def get_added(session, model_type):
    return [item for item in session.added if isinstance(item, model_type)]


@pytest.mark.asyncio
async def test_answer_question_persists_rag_answer_reference_and_decision_metadata():
    session = FakeSession()
    dependencies = make_dependencies(make_understanding(), make_evidence(score=0.8))

    response = await answer_question(
        session=session,
        question="项目知识库里有哪些运维内容？",
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
    assert response.decision["threshold"] == 0.3
    assert response.decision["configured_low_confidence_threshold"] == 0.2
    assert response.decision["effective_low_confidence_threshold"] == 0.3
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
            question="项目知识库里有哪些运维内容？",
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
    assert finish["answer"] == "RAG answer"
    assert "answer_preview" not in finish


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
    assert dependencies.answer_client.general_calls == [
        {"question": "什么是无功功率？", "mode": "general"}
    ]
    assert records and records[0].answer_type == AnswerType.general_llm
    assert not get_added(session, QaUnanswered)


@pytest.mark.asyncio
async def test_answer_question_keeps_rewriter_disabled_metadata_with_history():
    session = FakeSession()
    existing_session = QaSession()
    existing_session.id = uuid.uuid4()
    existing_record = make_existing_record(
        question="逆变器绝缘阻抗低怎么排查？",
        answer="可以检查直流线缆绝缘。",
    )
    existing_record.session_id = existing_session.id
    session.added.extend([existing_session, existing_record])
    dependencies = make_dependencies(make_understanding(), make_evidence(score=0.8))

    response = await answer_question(
        session=session,
        question="项目知识库里有哪些运维内容？",
        session_id=existing_session.id,
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    assert response.answer_type == "rag"
    assert response.decision["rewrite_reason"] == "rewriter_disabled"
    assert response.decision["used_history"] is False
    assert dependencies.understanding_client.calls == ["项目知识库里有哪些运维内容？"]


@pytest.mark.asyncio
async def test_answer_question_uses_rewriter_when_history_question_has_follow_up_signal():
    session = FakeSession()
    existing_session = QaSession()
    existing_session.id = uuid.uuid4()
    existing_record = make_existing_record(
        question="逆变器绝缘阻抗低怎么排查？",
        answer="可以检查直流线缆绝缘。",
    )
    existing_record.session_id = existing_session.id
    session.added.extend([existing_session, existing_record])
    rewriter = FakeContextRewriter(
        StandaloneQuestionResult(
            standalone_question="逆变器下雨天绝缘阻抗低怎么排查？",
            is_follow_up=True,
            used_history=True,
            reason="test_follow_up_rewrite",
        )
    )
    dependencies = make_dependencies(make_understanding(), make_evidence(score=0.8))
    dependencies = QaDependencies(
        understanding_client=dependencies.understanding_client,
        retriever=dependencies.retriever,
        answer_client=dependencies.answer_client,
        context_rewriter=rewriter,
    )

    response = await answer_question(
        session=session,
        question="那下雨天才出现呢？",
        session_id=existing_session.id,
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    assert response.answer_type == "rag"
    assert response.decision["rewrite_reason"] == "test_follow_up_rewrite"
    assert response.decision["used_history"] is True
    assert rewriter.calls and rewriter.calls[0]["question"] == "那下雨天才出现呢？"
    assert dependencies.understanding_client.calls == []
    assert dependencies.retriever.calls == ["逆变器下雨天绝缘阻抗低怎么排查？"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("intent", "reason"),
    [
        (Intent.invalid_input, "invalid_input"),
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
        question="请帮我判断这个请求",
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
async def test_answer_question_pre_routes_chitchat_to_short_general_answer():
    session = FakeSession()
    dependencies = make_dependencies(make_understanding(), [])

    response = await answer_question(
        session=session,
        question="你好",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    records = get_added(session, QaRecord)
    trace_steps = get_added(session, QaTraceStep)
    assert response.answer_type == "general_llm"
    assert response.intent == "chitchat"
    assert response.decision["route"] == "chitchat"
    assert response.decision["answer_mode"] == "chitchat"
    assert response.decision["used_knowledge_base"] is False
    assert response.decision["rewrite_reason"] == "pre_route_chitchat"
    assert "load_history_ms" not in response.decision["timings_ms"]
    assert "rewrite_question_ms" not in response.decision["timings_ms"]
    assert "understand_intent_ms" not in response.decision["timings_ms"]
    assert dependencies.understanding_client.calls == []
    assert dependencies.retriever.calls == []
    assert dependencies.answer_client.general_calls == [
        {"question": "你好", "mode": "chitchat"}
    ]
    assert records and records[0].answer_type == AnswerType.general_llm
    assert {step.step_name for step in trace_steps} >= {"pre_route", "answer_generation"}
    assert not get_added(session, QaUnanswered)


@pytest.mark.asyncio
async def test_answer_question_pre_routes_domain_question_to_rag_without_intent_llm():
    session = FakeSession()
    dependencies = make_dependencies(
        make_understanding(),
        [
            SimpleNamespace(
                segment_id="segment-generation-1",
                document_id="document-generation-1",
                heading_path="06_发电量异常与效率损失 > 2.1 低辐照导致发电量下降",
                clean_text="低辐照会导致组串出力下降，进而造成逆变器发电量偏低。",
                vector_score=0.6,
                keyword_score=0.5,
                rrf_score=0.03,
                rerank_score=0.8,
            )
        ],
    )

    response = await answer_question(
        session=session,
        question="低辐照下发电量下降原因",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    assert response.answer_type == "rag"
    assert response.intent == "knowledge_base_qa"
    assert response.decision["route"] == "rag"
    assert response.decision["intent_reason"] == "hard_rule_domain_fault_action"
    assert response.decision["rewrite_reason"] == "rewriter_disabled"
    assert response.decision["search_query"] == "低辐照下发电量下降原因"
    assert "load_history_ms" in response.decision["timings_ms"]
    assert "rewrite_question_ms" in response.decision["timings_ms"]
    assert "understand_intent_ms" in response.decision["timings_ms"]
    assert dependencies.understanding_client.calls == []
    assert dependencies.retriever.calls == ["低辐照下发电量下降原因"]


@pytest.mark.asyncio
async def test_answer_question_pre_routes_realtime_external_to_boundary_answer():
    session = FakeSession()
    dependencies = make_dependencies(make_understanding(), [])

    response = await answer_question(
        session=session,
        question="今天上海天气怎么样？",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    assert response.answer_type == "general_llm"
    assert response.intent == "realtime_external"
    assert response.decision["route"] == "realtime_external"
    assert response.decision["answer_mode"] == "realtime_external"
    assert response.decision["used_knowledge_base"] is False
    assert response.decision["refusal_reason"] is None
    assert dependencies.understanding_client.calls == []
    assert dependencies.retriever.calls == []
    assert dependencies.answer_client.general_calls == [
        {"question": "今天上海天气怎么样？", "mode": "realtime_external"}
    ]
    assert not get_added(session, QaUnanswered)


@pytest.mark.asyncio
async def test_answer_question_rewrites_followup_before_hard_rule_routing():
    session = FakeSession()
    qa_session_id = uuid.uuid4()
    existing_session = QaSession(id=qa_session_id)
    session.add(existing_session)
    previous = make_existing_record(
        question="逆变器报“绝缘阻抗低”，一般应该怎么排查？",
        answer="重点检查直流线缆破皮、接头进水和绝缘电阻。",
    )
    previous.session_id = qa_session_id
    session.add(previous)
    rewrite_result = StandaloneQuestionResult(
        standalone_question="逆变器绝缘阻抗低告警下，组串电压正常但告警仍在，下一步如何处理？",
        is_follow_up=True,
        used_history=True,
        reason="补全告警上下文",
    )
    dependencies = QaDependencies(
        understanding_client=FakeUnderstandingClient(make_understanding()),
        retriever=FakeRetriever(make_evidence(score=0.8)),
        answer_client=FakeAnswerClient(),
        context_rewriter=FakeContextRewriter(rewrite_result),
    )

    response = await answer_question(
        session=session,
        session_id=qa_session_id,
        question="如果组串电压看起来正常，但告警还在，下一步怎么办？",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    assert response.answer_type == "rag"
    assert dependencies.retriever.calls == [
        "逆变器绝缘阻抗低告警下，组串电压正常但告警仍在，下一步如何处理？"
    ]
    assert response.decision["used_history"] is True


@pytest.mark.asyncio
async def test_summary_style_followup_uses_rewritten_context_not_raw_query():
    session = FakeSession()
    qa_session_id = uuid.uuid4()
    existing_session = QaSession(id=qa_session_id)
    session.add(existing_session)
    previous = make_existing_record(
        question="这个告警会影响发电量吗？",
        answer="会，绝缘阻抗低会导致逆变器停机并造成发电量损失。",
    )
    previous.session_id = qa_session_id
    session.add(previous)
    rewrite_result = StandaloneQuestionResult(
        standalone_question="请把逆变器绝缘阻抗低告警的处理方法整理成运维人员能看懂的现场处理建议。",
        is_follow_up=True,
        used_history=True,
        reason="用户要求整理前文为现场建议",
    )
    dependencies = QaDependencies(
        understanding_client=FakeUnderstandingClient(make_understanding()),
        retriever=FakeRetriever(make_evidence(score=0.8)),
        answer_client=FakeAnswerClient(),
        context_rewriter=FakeContextRewriter(rewrite_result),
    )

    response = await answer_question(
        session=session,
        session_id=qa_session_id,
        question="能不能给我一个运维人员能看懂的处理建议？",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    assert response.answer_type == "rag"
    assert dependencies.retriever.calls == [
        "请把逆变器绝缘阻抗低告警的处理方法整理成运维人员能看懂的现场处理建议。"
    ]


@pytest.mark.asyncio
async def test_observed_insulation_resistance_followup_sequence_keeps_context():
    session = FakeSession()
    qa_session_id = uuid.uuid4()
    existing_session = QaSession(id=qa_session_id)
    session.add(existing_session)
    first_record = make_existing_record(
        question="逆变器报“绝缘阻抗低”，一般应该怎么排查？",
        answer="重点检查直流线缆破皮、接头进水、绝缘电阻和安全隔离。",
    )
    first_record.session_id = qa_session_id
    session.add(first_record)

    dependencies = QaDependencies(
        understanding_client=FakeUnderstandingClient(make_understanding()),
        retriever=FakeRetriever(make_evidence(score=0.8)),
        answer_client=FakeAnswerClient(),
        context_rewriter=FakeContextRewriter(
            StandaloneQuestionResult(
                standalone_question="逆变器绝缘阻抗低告警下，组串电压正常但告警仍在，下一步如何处理？",
                is_follow_up=True,
                used_history=True,
                reason="补全告警上下文",
            )
        ),
    )

    response = await answer_question(
        session=session,
        session_id=qa_session_id,
        question="如果组串电压看起来正常，但告警还在，下一步怎么办？",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    assert response.answer_type == "rag"
    assert response.decision["used_history"] is True
    assert "绝缘阻抗低" in response.decision["standalone_question"]


@pytest.mark.asyncio
async def test_answer_question_uses_low_confidence_supplemental_rag_for_domain_question():
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
    assert response.answer_type == "rag"
    assert response.answer == "Low confidence RAG answer with model supplemental advice"
    assert len(response.references) == 1
    assert response.references[0].visible is True
    assert response.references[0].rerank_score == 0.01
    assert response.references[0].usage_note == "仅作相关片段参考"
    assert response.decision["route"] == "rag_low_confidence_supplement"
    assert response.decision["used_knowledge_base"] is True
    assert response.decision["refusal_reason"] is None
    assert response.decision["answer_mode"] == "low_confidence_supplement"
    assert response.decision["top1_rerank_score"] == 0.01
    assert response.decision["threshold"] == 0.3
    assert response.decision["configured_low_confidence_threshold"] == 0.2
    assert response.decision["effective_low_confidence_threshold"] == 0.3
    assert get_added(session, QaReference)
    assert records and records[0].answer_type == AnswerType.rag
    assert unanswered == []
    assert dependencies.answer_client.rag_calls == []
    assert dependencies.answer_client.low_confidence_rag_calls == [
        {
            "question": "逆变器绝缘阻抗低怎么排查？",
            "evidence": dependencies.retriever.evidence,
            "top_score": 0.01,
        }
    ]
    assert session.commits == 1


@pytest.mark.asyncio
async def test_answer_question_uses_supplement_when_high_score_evidence_does_not_cover_topic():
    session = FakeSession()
    dependencies = make_dependencies(
        make_understanding(
            normalized_question="逆变器在监控平台上显示通讯中断，现场应该怎么排查？",
            search_query="逆变器 监控平台 通讯中断 排查",
        ),
        make_communication_mismatch_evidence(score=0.67),
    )

    response = await answer_question(
        session=session,
        question="逆变器在监控平台上显示通讯中断，现场应该怎么排查？",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    assert response.answer_type == "rag"
    assert response.decision["route"] == "rag_low_confidence_supplement"
    assert response.decision["answer_mode"] == "low_confidence_supplement"
    assert response.decision["evidence_alignment"]["directly_supported"] is False
    assert response.decision["evidence_alignment"]["reason"] == "missing_topic_terms"
    assert dependencies.answer_client.rag_calls == []
    assert dependencies.answer_client.low_confidence_rag_calls
    assert response.references[0].usage_note == "仅作相关片段参考"


@pytest.mark.asyncio
async def test_answer_question_uses_supplement_when_filtered_evidence_is_empty():
    session = FakeSession()
    dependencies = make_dependencies(
        make_understanding(
            normalized_question="MC4接头温度偏高怎么处理？",
            search_query="MC4接头温度偏高怎么处理？",
        ),
        make_evidence_scores(0.28, 0.12),
    )

    response = await answer_question(
        session=session,
        question="如果红外测温发现某个 MC4 接头明显高于旁边接头，该怎么处理？",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
        qa_evidence_min_score=0.3,
    )

    assert response.answer_type == "rag"
    assert response.decision["route"] == "rag_low_confidence_supplement"
    assert response.decision["refusal_reason"] is None
    assert "阈值" not in response.answer
    assert dependencies.answer_client.low_confidence_rag_calls == [
        {
            "question": "如果红外测温发现某个 MC4 接头明显高于旁边接头，该怎么处理？",
            "evidence": dependencies.retriever.evidence,
            "top_score": 0.28,
        }
    ]


@pytest.mark.asyncio
async def test_answer_question_uses_policy_low_confidence_threshold_over_legacy_value():
    session = FakeSession()
    dependencies = make_dependencies(
        make_understanding(
            normalized_question="直流接头温度偏高通常是什么原因？",
            search_query="直流接头温度偏高通常是什么原因？",
        ),
        make_evidence_scores(0.28, 0.22),
    )

    response = await answer_question(
        session=session,
        question="巡检发现直流接头温度偏高，通常是什么原因？",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
        qa_evidence_min_score=0.2,
    )

    assert response.answer_type == "rag"
    assert response.decision["route"] == "rag_low_confidence_supplement"
    assert response.decision["effective_low_confidence_threshold"] == 0.3
    assert response.decision["configured_low_confidence_threshold"] == 0.2
    assert dependencies.answer_client.rag_calls == []
    assert dependencies.answer_client.low_confidence_rag_calls
