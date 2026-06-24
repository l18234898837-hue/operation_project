import pytest

from app.services.conversation_context import ConversationContext
from app.services.conversation_rewrite import rewrite_standalone_question


class FakeChatClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = []

    async def chat(self, messages, temperature=0.1):
        self.calls.append({"messages": messages, "temperature": temperature})
        return self.response


@pytest.mark.asyncio
async def test_rewrite_standalone_question_parses_json_result():
    context = ConversationContext(
        session_summary={"summary": "用户在排查逆变器绝缘阻抗低"},
        recent_turns=[{"question": "逆变器绝缘阻抗低怎么排查？"}],
        used_history=True,
    )
    client = FakeChatClient(
        """
        {"is_follow_up": true, "used_history": true,
         "standalone_question": "逆变器下雨天才出现绝缘阻抗低怎么排查？",
         "reason": "补全指代"}
        """
    )

    result = await rewrite_standalone_question("那下雨天才出现呢？", context, client)

    assert result.standalone_question == "逆变器下雨天才出现绝缘阻抗低怎么排查？"
    assert result.is_follow_up is True
    assert result.used_history is True


@pytest.mark.asyncio
async def test_rewrite_standalone_question_falls_back_to_original_on_error():
    context = ConversationContext(
        session_summary={"summary": "历史"},
        recent_turns=[{"question": "上一轮"}],
        used_history=True,
    )
    client = FakeChatClient("not json")

    result = await rewrite_standalone_question("当前问题", context, client)

    assert result.standalone_question == "当前问题"
    assert result.reason == "rewrite_fallback_after_llm_failure"
