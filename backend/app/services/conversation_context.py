from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConversationContext:
    session_summary: dict[str, Any] | None
    recent_turns: list[dict[str, Any]]
    used_history: bool

    def is_empty(self) -> bool:
        return not self.session_summary and not self.recent_turns


def build_conversation_context(
    records: list[object],
    session_metadata: dict[str, Any] | None,
    history_turns: int,
    answer_excerpt_chars: int,
    max_chars: int,
) -> ConversationContext:
    summary = _summary_from_metadata(session_metadata)
    recent_records = records[-history_turns:] if history_turns > 0 else []
    turns = [_record_to_turn(record, answer_excerpt_chars) for record in recent_records]
    context = ConversationContext(
        session_summary=summary,
        recent_turns=turns,
        used_history=bool(summary or turns),
    )
    return _trim_context(context, max_chars)


def _summary_from_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(metadata, dict):
        return None
    summary = metadata.get("conversation_summary")
    return summary if isinstance(summary, dict) else None


def _record_to_turn(record: object, answer_excerpt_chars: int) -> dict[str, Any]:
    return {
        "question": getattr(record, "question", "") or "",
        "normalized_question": getattr(record, "normalized_question", "") or "",
        "answer_type": _answer_type_value(getattr(record, "answer_type", "")),
        "answer_excerpt": (getattr(record, "answer", "") or "")[:answer_excerpt_chars],
        "top_heading": _top_heading(record),
    }


def _answer_type_value(value: object) -> str:
    return str(getattr(value, "value", value) or "")


def _top_heading(record: object) -> str:
    references = list(getattr(record, "references", []) or [])
    references.sort(key=lambda item: getattr(item, "rank", 999999) or 999999)
    if not references:
        return ""
    metadata = getattr(references[0], "ref_metadata", None)
    if isinstance(metadata, dict):
        return str(metadata.get("heading_path") or "")
    return ""


def _trim_context(context: ConversationContext, max_chars: int) -> ConversationContext:
    if max_chars <= 0:
        return ConversationContext(
            session_summary=context.session_summary,
            recent_turns=[],
            used_history=bool(context.session_summary),
        )

    turns = list(context.recent_turns)
    while _rough_chars(context.session_summary, turns) > max_chars and turns:
        turns.pop(0)
    return ConversationContext(
        session_summary=context.session_summary,
        recent_turns=turns,
        used_history=bool(context.session_summary or turns),
    )


def _rough_chars(summary: dict[str, Any] | None, turns: list[dict[str, Any]]) -> int:
    return len(str(summary or "")) + len(str(turns))
