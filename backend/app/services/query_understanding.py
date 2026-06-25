from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import re
from typing import Any, Protocol

from app.prompts.qa_prompts import build_intent_messages
from app.services.keyword_index import normalize_query
from app.services.routing_terms import DOMAIN_TERMS, FAULT_ACTION_TERMS, REALTIME_TERMS


class ChatClient(Protocol):
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
    ) -> str:
        ...


class Intent(str, Enum):
    knowledge_base_qa = "knowledge_base_qa"
    general_explanation = "general_explanation"
    out_of_scope = "out_of_scope"
    realtime_external = "realtime_external"
    invalid_input = "invalid_input"


@dataclass(frozen=True)
class QueryUnderstandingResult:
    intent: Intent
    confidence: float
    should_use_knowledge_base: bool
    normalized_question: str
    search_query: str
    refusal_reason: str | None
    reason: str


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(?P<body>.*?)```", re.IGNORECASE | re.DOTALL)
_MEANINGFUL_TEXT_RE = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]")


def apply_intent_hard_rules(
    question: str,
    max_question_chars: int = 500,
) -> QueryUnderstandingResult | None:
    normalized = normalize_query(question)
    if _is_invalid_question(normalized, max_question_chars):
        return QueryUnderstandingResult(
            intent=Intent.invalid_input,
            confidence=1.0,
            should_use_knowledge_base=False,
            normalized_question=normalized,
            search_query="",
            refusal_reason="invalid_input",
            reason="hard_rule_invalid_input",
        )

    if _has_domain_fault_action(normalized):
        return QueryUnderstandingResult(
            intent=Intent.knowledge_base_qa,
            confidence=1.0,
            should_use_knowledge_base=True,
            normalized_question=normalized,
            search_query=normalized,
            refusal_reason=None,
            reason="hard_rule_domain_fault_action",
        )

    if _contains_any(normalized, REALTIME_TERMS):
        return QueryUnderstandingResult(
            intent=Intent.realtime_external,
            confidence=1.0,
            should_use_knowledge_base=False,
            normalized_question=normalized,
            search_query="",
            refusal_reason="realtime_external",
            reason="hard_rule_realtime_external",
        )

    return None


async def understand_query(
    question: str,
    chat_client: ChatClient,
    max_question_chars: int = 500,
) -> QueryUnderstandingResult:
    hard_rule_result = apply_intent_hard_rules(
        question,
        max_question_chars=max_question_chars,
    )
    if hard_rule_result is not None:
        return hard_rule_result

    normalized = normalize_query(question)
    try:
        content = await chat_client.chat(
            messages=build_intent_messages(normalized),
            temperature=0.1,
        )
        model_result = _parse_model_result(content, fallback_question=normalized)
    except Exception:
        model_result = _fallback_to_knowledge_base(
            normalized,
            reason="fallback_after_llm_failure",
        )

    return post_validate_understanding(
        original_question=normalized,
        model_result=model_result,
    )


def post_validate_understanding(
    original_question: str,
    model_result: QueryUnderstandingResult,
) -> QueryUnderstandingResult:
    normalized_original = normalize_query(original_question)
    if (
        model_result.intent == Intent.general_explanation
        and _has_domain_fault_action(normalized_original)
    ):
        normalized_question = model_result.normalized_question or normalized_original
        return QueryUnderstandingResult(
            intent=Intent.knowledge_base_qa,
            confidence=model_result.confidence,
            should_use_knowledge_base=True,
            normalized_question=normalized_question,
            search_query=model_result.search_query or normalized_question,
            refusal_reason=None,
            reason="post_validation_domain_fault_action",
        )

    if model_result.intent == Intent.knowledge_base_qa and not model_result.search_query:
        normalized_question = model_result.normalized_question or normalized_original
        return QueryUnderstandingResult(
            intent=model_result.intent,
            confidence=model_result.confidence,
            should_use_knowledge_base=True,
            normalized_question=normalized_question,
            search_query=normalized_question,
            refusal_reason=None,
            reason=model_result.reason,
        )

    if model_result.intent == Intent.knowledge_base_qa and not model_result.should_use_knowledge_base:
        return QueryUnderstandingResult(
            intent=model_result.intent,
            confidence=model_result.confidence,
            should_use_knowledge_base=True,
            normalized_question=model_result.normalized_question or normalized_original,
            search_query=model_result.search_query or model_result.normalized_question or normalized_original,
            refusal_reason=None,
            reason=model_result.reason,
        )

    return model_result


def _build_intent_messages(question: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你只做意图识别，是光伏运维知识库问答系统的查询理解模块。"
                "只输出 JSON，不要回答用户问题。"
                "必须保留原意、设备名称、故障码、型号、英文缩写和技术术语。"
                "intent 只能是 knowledge_base_qa、general_explanation、out_of_scope、"
                "realtime_external、invalid_input。"
                "例如：今天上海天气怎么样？属于 realtime_external；"
                "什么是无功功率？通常属于 general_explanation。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请识别用户问题意图并改写检索 query，输出字段："
                "intent, confidence, should_use_knowledge_base, normalized_question, "
                f"search_query, reason。\n用户问题：{question}"
            ),
        },
    ]


def _parse_model_result(content: str, fallback_question: str) -> QueryUnderstandingResult:
    payload = _load_json_from_content(content)
    intent = _coerce_intent(payload.get("intent"))
    normalized_question = normalize_query(str(payload.get("normalized_question") or fallback_question))
    search_query = normalize_query(str(payload.get("search_query") or ""))
    confidence = _coerce_confidence(payload.get("confidence"))
    should_use_knowledge_base = payload.get("should_use_knowledge_base")
    if not isinstance(should_use_knowledge_base, bool):
        should_use_knowledge_base = intent == Intent.knowledge_base_qa
    refusal_reason = payload.get("refusal_reason")
    if not isinstance(refusal_reason, str):
        refusal_reason = intent.value if intent in _REFUSAL_INTENTS else None
    reason = payload.get("reason")

    return QueryUnderstandingResult(
        intent=intent,
        confidence=confidence,
        should_use_knowledge_base=should_use_knowledge_base,
        normalized_question=normalized_question,
        search_query=search_query,
        refusal_reason=refusal_reason,
        reason=str(reason or "llm_intent_classification"),
    )


def _load_json_from_content(content: str) -> dict[str, Any]:
    text = content.strip()
    fence_match = _JSON_FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group("body").strip()

    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("intent model output must be a JSON object")
    return data


def _fallback_to_knowledge_base(question: str, reason: str) -> QueryUnderstandingResult:
    return QueryUnderstandingResult(
        intent=Intent.knowledge_base_qa,
        confidence=0.0,
        should_use_knowledge_base=True,
        normalized_question=question,
        search_query=question,
        refusal_reason=None,
        reason=reason,
    )


def _coerce_intent(value: object) -> Intent:
    try:
        return Intent(str(value))
    except ValueError:
        return Intent.knowledge_base_qa


def _coerce_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))


def _is_invalid_question(question: str, max_question_chars: int) -> bool:
    if not question:
        return True
    if len(question) > max_question_chars:
        return True
    if _MEANINGFUL_TEXT_RE.search(question) is None:
        return True
    return len(question) < 2


def _contains_any(question: str, terms: tuple[str, ...]) -> bool:
    question_lower = question.lower()
    return any(term.lower() in question_lower for term in terms)


def _has_domain_fault_action(question: str) -> bool:
    return _contains_any(question, DOMAIN_TERMS) and _contains_any(question, FAULT_ACTION_TERMS)


_REFUSAL_INTENTS = {
    Intent.invalid_input,
    Intent.realtime_external,
    Intent.out_of_scope,
}
