from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import re
from typing import Any, Protocol

from app.prompts.qa_prompts import build_intent_messages
from app.services.keyword_index import normalize_query
from app.services.routing_terms import (
    CHITCHAT_EXACT_TERMS,
    CHITCHAT_PATTERNS,
    DOMAIN_TERMS,
    EFFICIENCY_TERMS,
    ENVIRONMENT_TERMS,
    FAULT_ACTION_TERMS,
    FAULT_CODE_PATTERNS,
    FOLLOW_UP_TERMS,
    GENERATION_IMPACT_TERMS,
    IMPROVEMENT_ACTION_TERMS,
    LOCATION_TERMS,
    ALWAYS_REALTIME_EXTERNAL_TERMS,
    QUESTION_PREFIX_PATTERN,
    REALTIME_DATE_TERMS,
    REALTIME_TERMS,
    STRONG_DOMAIN_TERMS,
    WEATHER_TERMS,
)


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
    chitchat = "chitchat"
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
_CHITCHAT_EXACT_TERM_SET = {term.lower() for term in CHITCHAT_EXACT_TERMS}


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

    if _is_chitchat(normalized):
        return QueryUnderstandingResult(
            intent=Intent.chitchat,
            confidence=1.0,
            should_use_knowledge_base=False,
            normalized_question=normalized,
            search_query="",
            refusal_reason=None,
            reason="hard_rule_chitchat",
        )

    if _is_realtime_external(normalized):
        return QueryUnderstandingResult(
            intent=Intent.realtime_external,
            confidence=1.0,
            should_use_knowledge_base=False,
            normalized_question=normalized,
            search_query="",
            refusal_reason=None,
            reason="hard_rule_realtime_external",
        )

    if _should_route_to_knowledge_base(normalized):
        return QueryUnderstandingResult(
            intent=Intent.knowledge_base_qa,
            confidence=1.0,
            should_use_knowledge_base=True,
            normalized_question=normalized,
            search_query=_build_hard_rule_search_query(normalized),
            refusal_reason=None,
            reason="hard_rule_domain_fault_action",
        )

    if _is_realtime_external(normalized):
        return QueryUnderstandingResult(
            intent=Intent.realtime_external,
            confidence=1.0,
            should_use_knowledge_base=False,
            normalized_question=normalized,
            search_query="",
            refusal_reason=None,
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


def _parse_model_result(content: str, fallback_question: str) -> QueryUnderstandingResult:
    payload = _load_json_from_content(content)
    intent = _coerce_intent(payload.get("intent"))
    normalized_question = normalize_query(fallback_question)
    confidence = _coerce_confidence(payload.get("confidence"))
    should_use_knowledge_base = intent == Intent.knowledge_base_qa
    search_query = normalized_question if should_use_knowledge_base else ""
    refusal_reason = intent.value if intent in _REFUSAL_INTENTS else None

    return QueryUnderstandingResult(
        intent=intent,
        confidence=confidence,
        should_use_knowledge_base=should_use_knowledge_base,
        normalized_question=normalized_question,
        search_query=search_query,
        refusal_reason=refusal_reason,
        reason="llm_intent_classification",
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


def _build_hard_rule_search_query(question: str) -> str:
    inverter_efficiency_query = _build_inverter_efficiency_query(question)
    if inverter_efficiency_query is not None:
        return inverter_efficiency_query
    return question


def _build_inverter_efficiency_query(question: str) -> str | None:
    if "逆变器" not in question:
        return None
    if not _contains_any(question, EFFICIENCY_TERMS):
        return None
    if not _contains_any(question, IMPROVEMENT_ACTION_TERMS):
        return None

    stripped = re.sub(QUESTION_PREFIX_PATTERN, "", question).strip(" ，。！？?；;：:")
    if stripped.startswith("逆变器"):
        return normalize_query(stripped)
    return "逆变器效率提升"


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


def _matches_any_pattern(question: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, question, re.IGNORECASE) for pattern in patterns)


def _is_chitchat(question: str) -> bool:
    if _contains_any(question, DOMAIN_TERMS):
        return False
    question_lower = question.lower()
    if question_lower in _CHITCHAT_EXACT_TERM_SET:
        return True
    return _matches_any_pattern(question, CHITCHAT_PATTERNS)


def _is_realtime_external(question: str) -> bool:
    if _contains_any(question, ALWAYS_REALTIME_EXTERNAL_TERMS):
        return True
    if (
        _contains_any(question, WEATHER_TERMS)
        and (
            _contains_any(question, REALTIME_DATE_TERMS)
            or _contains_any(question, LOCATION_TERMS)
        )
    ):
        return True
    return _contains_any(question, REALTIME_TERMS) and not _contains_any(question, DOMAIN_TERMS)


def _should_route_to_knowledge_base(question: str) -> bool:
    if _contains_any(question, FOLLOW_UP_TERMS):
        return False
    if _matches_any_pattern(question, FAULT_CODE_PATTERNS):
        return True
    if _contains_any(question, STRONG_DOMAIN_TERMS):
        return True
    if _has_domain_fault_action(question):
        return True
    return _contains_any(question, ENVIRONMENT_TERMS) and _contains_any(
        question,
        GENERATION_IMPACT_TERMS,
    )


def _has_domain_fault_action(question: str) -> bool:
    return _contains_any(question, DOMAIN_TERMS) and _contains_any(question, FAULT_ACTION_TERMS)


_REFUSAL_INTENTS = {
    Intent.invalid_input,
    Intent.out_of_scope,
}
