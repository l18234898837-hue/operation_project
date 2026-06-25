import pytest

from app.services.query_understanding import (
    Intent,
    QueryUnderstandingResult,
    apply_intent_hard_rules,
    post_validate_understanding,
    understand_query,
)
from app.services.routing_terms import DOMAIN_TERMS, FAULT_ACTION_TERMS, REALTIME_TERMS


def test_empty_question_is_invalid_input():
    result = apply_intent_hard_rules("   !!!   ")

    assert result is not None
    assert result.intent == Intent.invalid_input
    assert result.should_use_knowledge_base is False
    assert result.refusal_reason == "invalid_input"


def test_routing_terms_are_maintained_separately():
    assert "逆变器" in DOMAIN_TERMS
    assert "报警" in FAULT_ACTION_TERMS
    assert "天气" in REALTIME_TERMS


def test_realtime_external_question_is_detected_before_llm():
    result = apply_intent_hard_rules("今天上海天气怎么样？")

    assert result is not None
    assert result.intent == Intent.realtime_external
    assert result.should_use_knowledge_base is False
    assert result.refusal_reason == "realtime_external"


def test_domain_fault_question_forces_knowledge_base():
    result = apply_intent_hard_rules("逆变器漏电流报警怎么处理？")

    assert result is not None
    assert result.intent == Intent.knowledge_base_qa
    assert result.should_use_knowledge_base is True
    assert result.normalized_question == "逆变器漏电流报警怎么处理？"
    assert "逆变器漏电流报警怎么处理" in result.search_query


def test_domain_fault_question_overrides_realtime_term():
    result = apply_intent_hard_rules("今天逆变器漏电流报警怎么处理？")

    assert result is not None
    assert result.intent == Intent.knowledge_base_qa
    assert result.should_use_knowledge_base is True
    assert result.normalized_question == "今天逆变器漏电流报警怎么处理？"
    assert result.search_query == "今天逆变器漏电流报警怎么处理？"
    assert result.refusal_reason is None


def test_post_validation_overrides_general_llm_for_domain_fault_question():
    model_result = QueryUnderstandingResult(
        intent=Intent.general_explanation,
        confidence=0.9,
        should_use_knowledge_base=False,
        normalized_question="逆变器漏电流报警是什么？",
        search_query="",
        refusal_reason=None,
        reason="model thought this was general",
    )

    result = post_validate_understanding(
        original_question="逆变器漏电流报警怎么处理？",
        model_result=model_result,
    )

    assert result.intent == Intent.knowledge_base_qa
    assert result.should_use_knowledge_base is True
    assert result.search_query == "逆变器漏电流报警是什么？"


def test_post_validation_uses_normalized_question_when_kb_search_query_is_empty():
    model_result = QueryUnderstandingResult(
        intent=Intent.knowledge_base_qa,
        confidence=0.77,
        should_use_knowledge_base=True,
        normalized_question="箱变过温报警处理步骤",
        search_query="",
        refusal_reason=None,
        reason="llm_intent_classification",
    )

    result = post_validate_understanding(
        original_question="箱变过温报警怎么办？",
        model_result=model_result,
    )

    assert result.intent == Intent.knowledge_base_qa
    assert result.should_use_knowledge_base is True
    assert result.normalized_question == "箱变过温报警处理步骤"
    assert result.search_query == "箱变过温报警处理步骤"


@pytest.mark.asyncio
async def test_understand_query_uses_llm_for_general_explanation():
    class FakeChatClient:
        captured_messages = None

        async def chat(self, messages, temperature=0.1):
            self.captured_messages = messages
            return """
            {
              "intent": "general_explanation",
              "confidence": 0.82,
              "should_use_knowledge_base": false,
              "normalized_question": "什么是无功功率？",
              "search_query": "",
              "reason": "通用概念解释"
            }
            """

    chat_client = FakeChatClient()
    result = await understand_query(
        question="啥是无功功率？",
        chat_client=chat_client,
        max_question_chars=500,
    )

    assert result.intent == Intent.general_explanation
    assert result.should_use_knowledge_base is False
    assert result.normalized_question == "什么是无功功率？"
    assert "你只做意图识别" in chat_client.captured_messages[0]["content"]


@pytest.mark.asyncio
async def test_understand_query_parses_fenced_json_and_rewrites_search_query():
    class FakeChatClient:
        async def chat(self, messages, temperature=0.1):
            return """
            ```json
            {
              "intent": "knowledge_base_qa",
              "confidence": 0.88,
              "should_use_knowledge_base": true,
              "normalized_question": "组件 PID 衰减如何排查？",
              "search_query": "组件 PID 衰减 排查 处理",
              "reason": "设备故障处理"
            }
            ```
            """

    result = await understand_query(
        question="光伏运维资料中有没有 PID 相关内容？",
        chat_client=FakeChatClient(),
        max_question_chars=500,
    )

    assert result.intent == Intent.knowledge_base_qa
    assert result.should_use_knowledge_base is True
    assert result.search_query == "组件 PID 衰减 排查 处理"


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["not json", "[1, 2, 3]"])
async def test_understand_query_falls_back_to_knowledge_base_when_llm_returns_invalid_content(content):
    class InvalidContentChatClient:
        async def chat(self, messages, temperature=0.1):
            return content

    result = await understand_query(
        question="项目知识库里有哪些运维内容？",
        chat_client=InvalidContentChatClient(),
        max_question_chars=500,
    )

    assert result.intent == Intent.knowledge_base_qa
    assert result.should_use_knowledge_base is True
    assert result.normalized_question == "项目知识库里有哪些运维内容？"
    assert result.search_query == "项目知识库里有哪些运维内容？"
    assert result.reason == "fallback_after_llm_failure"


@pytest.mark.asyncio
async def test_understand_query_falls_back_to_knowledge_base_when_llm_fails():
    class FailingChatClient:
        async def chat(self, messages, temperature=0.1):
            raise RuntimeError("network unavailable")

    result = await understand_query(
        question="项目知识库里有哪些运维内容？",
        chat_client=FailingChatClient(),
        max_question_chars=500,
    )

    assert result.intent == Intent.knowledge_base_qa
    assert result.should_use_knowledge_base is True
    assert result.normalized_question == "项目知识库里有哪些运维内容？"
    assert result.search_query == "项目知识库里有哪些运维内容？"
    assert result.reason == "fallback_after_llm_failure"
