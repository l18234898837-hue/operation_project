from types import SimpleNamespace

import pytest

from app.services.session_summary import (
    should_refresh_summary,
    update_session_summary_if_needed,
)


class FakeChatClient:
    async def chat(self, messages, temperature=0.1):
        return """
        {
          "summary": "用户正在排查逆变器绝缘阻抗低",
          "current_topic": "绝缘阻抗低",
          "known_context": ["雨天出现"],
          "already_checked": [],
          "open_questions": [],
          "user_constraints": []
        }
        """


def test_should_refresh_summary_after_threshold_and_refresh_interval():
    assert should_refresh_summary(
        record_count=9,
        session_metadata=None,
        summary_after_turns=10,
        summary_refresh_turns=5,
    ) is False
    assert should_refresh_summary(
        record_count=10,
        session_metadata=None,
        summary_after_turns=10,
        summary_refresh_turns=5,
    ) is True
    assert should_refresh_summary(
        record_count=14,
        session_metadata={"conversation_summary_turn_count": 10},
        summary_after_turns=10,
        summary_refresh_turns=5,
    ) is False
    assert should_refresh_summary(
        record_count=15,
        session_metadata={"conversation_summary_turn_count": 10},
        summary_after_turns=10,
        summary_refresh_turns=5,
    ) is True


@pytest.mark.asyncio
async def test_update_session_summary_if_needed_writes_structured_metadata():
    qa_session = SimpleNamespace(session_metadata=None)
    records = [
        SimpleNamespace(question=f"问题{i}", answer=f"回答{i}", references=[])
        for i in range(10)
    ]

    updated = await update_session_summary_if_needed(
        qa_session=qa_session,
        records=records,
        chat_client=FakeChatClient(),
        summary_after_turns=10,
        summary_refresh_turns=5,
        history_turns=10,
        answer_excerpt_chars=500,
    )

    assert updated is True
    assert qa_session.session_metadata["conversation_summary_turn_count"] == 10
    assert qa_session.session_metadata["conversation_summary"]["current_topic"] == "绝缘阻抗低"
