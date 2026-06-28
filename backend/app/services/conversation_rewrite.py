from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.prompts.qa_prompts import build_standalone_question_messages
from app.services.conversation_context import ConversationContext
from app.services.json_model_output import load_json_object
from app.services.keyword_index import normalize_query
from app.services.routing_terms import (
    DOMAIN_TERMS,
    REWRITE_FOLLOW_UP_TERMS,
    SELF_CONTAINED_ACTION_TERMS,
)


class ChatClient(Protocol):
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
    ) -> str:
        ...


@dataclass(frozen=True)
class StandaloneQuestionResult:
    standalone_question: str
    is_follow_up: bool
    used_history: bool
    reason: str


async def rewrite_standalone_question(
    question: str,
    context: ConversationContext,
    chat_client: ChatClient,
) -> StandaloneQuestionResult:
    normalized_question = normalize_query(question)
    if context.is_empty():
        return StandaloneQuestionResult(
            standalone_question=normalized_question,
            is_follow_up=False,
            used_history=False,
            reason="no_history",
        )
    try:
        content = await chat_client.chat(
            messages=build_standalone_question_messages(
                session_summary=context.session_summary,
                recent_turns=context.recent_turns,
                current_question=normalized_question,
            ),
            temperature=0.1,
        )
        payload = load_json_object(content)
        standalone_question = normalize_query(
            str(payload.get("standalone_question") or normalized_question)
        )
        return StandaloneQuestionResult(
            standalone_question=standalone_question or normalized_question,
            is_follow_up=bool(payload.get("is_follow_up", False)),
            used_history=bool(payload.get("used_history", False)),
            reason=str(payload.get("reason") or "llm_rewrite"),
        )
    except Exception:
        return StandaloneQuestionResult(
            standalone_question=normalized_question,
            is_follow_up=False,
            used_history=False,
            reason="rewrite_fallback_after_llm_failure",
        )


def _needs_history_rewrite(question: str) -> bool:
    question_lower = question.lower()
    return any(term.lower() in question_lower for term in REWRITE_FOLLOW_UP_TERMS)


def _contains_any(question: str, terms: tuple[str, ...]) -> bool:
    question_lower = question.lower()
    return any(term.lower() in question_lower for term in terms)


def _is_self_contained_domain_question(question: str) -> bool:
    if _needs_history_rewrite(question):
        return False
    return _contains_any(question, DOMAIN_TERMS) and _contains_any(
        question,
        SELF_CONTAINED_ACTION_TERMS,
    )
