from __future__ import annotations

from typing import Any, Protocol

from app.prompts.qa_prompts import build_session_summary_messages
from app.services.conversation_context import build_conversation_context
from app.services.json_model_output import load_json_object


class ChatClient(Protocol):
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
    ) -> str:
        ...


SUMMARY_FIELDS = {
    "summary",
    "current_topic",
    "known_context",
    "already_checked",
    "open_questions",
    "user_constraints",
}


def should_refresh_summary(
    record_count: int,
    session_metadata: dict[str, Any] | None,
    summary_after_turns: int,
    summary_refresh_turns: int,
) -> bool:
    if record_count < summary_after_turns:
        return False
    metadata = session_metadata if isinstance(session_metadata, dict) else {}
    last_count = int(metadata.get("conversation_summary_turn_count") or 0)
    if last_count == 0:
        return True
    return record_count - last_count >= summary_refresh_turns


async def update_session_summary_if_needed(
    qa_session: object,
    records: list[object],
    chat_client: ChatClient,
    summary_after_turns: int,
    summary_refresh_turns: int,
    history_turns: int,
    answer_excerpt_chars: int,
) -> bool:
    metadata = _metadata(qa_session)
    record_count = len(records)
    if not should_refresh_summary(
        record_count=record_count,
        session_metadata=metadata,
        summary_after_turns=summary_after_turns,
        summary_refresh_turns=summary_refresh_turns,
    ):
        return False

    context = build_conversation_context(
        records=records,
        session_metadata=metadata,
        history_turns=history_turns,
        answer_excerpt_chars=answer_excerpt_chars,
        max_chars=12000,
    )
    content = await chat_client.chat(
        messages=build_session_summary_messages(
            previous_summary=metadata.get("conversation_summary"),
            turns=context.recent_turns,
        ),
        temperature=0.1,
    )
    summary = _sanitize_summary(load_json_object(content))
    metadata["conversation_summary"] = summary
    metadata["conversation_summary_turn_count"] = record_count
    setattr(qa_session, "session_metadata", metadata)
    return True


def _metadata(qa_session: object) -> dict[str, Any]:
    metadata = getattr(qa_session, "session_metadata", None)
    if isinstance(metadata, dict):
        return dict(metadata)
    return {}


def _sanitize_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: payload.get(key) for key in SUMMARY_FIELDS}
