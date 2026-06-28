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
async def test_rewrite_standalone_question_lets_llm_decide_when_history_exists():
    context = ConversationContext(
        session_summary={"summary": "用户在排查逆变器绝缘阻抗低"},
        recent_turns=[{"question": "逆变器绝缘阻抗低怎么排查？"}],
        used_history=True,
    )
    client = FakeChatClient(
        """
        {"is_follow_up": false, "used_history": false,
         "standalone_question": "项目知识库里有哪些运维内容？",
         "reason": "当前问题是独立问题，不承接历史故障"}
        """
    )

    result = await rewrite_standalone_question(
        "项目知识库里有哪些运维内容？",
        context,
        client,
    )

    assert result.standalone_question == "项目知识库里有哪些运维内容？"
    assert result.is_follow_up is False
    assert result.used_history is False
    assert result.reason == "当前问题是独立问题，不承接历史故障"
    assert client.calls


@pytest.mark.asyncio
async def test_rewrite_uses_history_for_checklist_followup_without_keyword_shortcut():
    context = ConversationContext(
        session_summary={"summary": "用户正在排查某个组串发电量明显低于同区域其他组串。"},
        recent_turns=[
            {
                "question": "这个问题和接线端子接触不良有没有关系？",
                "answer_excerpt": "有关系，接线端子接触不良会导致组串电流偏低。",
            }
        ],
        used_history=True,
    )
    client = FakeChatClient(
        """
        {"is_follow_up": true, "used_history": true,
         "standalone_question": "请整理一个用于排查组串发电量明显低于同区域其他组串的现场排查清单。",
         "reason": "用户要求整理前文问题的现场排查清单"}
        """
    )

    result = await rewrite_standalone_question(
        "最后帮我整理一个现场排查清单。",
        context,
        client,
    )

    assert result.is_follow_up is True
    assert result.used_history is True
    assert "组串发电量明显低于同区域其他组串" in result.standalone_question
    assert client.calls


@pytest.mark.asyncio
async def test_rewrite_lets_llm_decide_even_for_self_contained_domain_question_with_history():
    context = ConversationContext(
        session_summary={"summary": "用户正在排查组串发电量偏低。"},
        recent_turns=[
            {
                "question": "某个组串发电量明显低于同区域其他组串，可能是什么原因？",
                "answer_excerpt": "优先检查遮挡、积灰、接线端子和组串电流。",
            }
        ],
        used_history=True,
    )
    client = FakeChatClient(
        """
        {"is_follow_up": false, "used_history": false,
         "standalone_question": "逆变器绝缘阻抗低怎么排查？",
         "reason": "当前问题是新的独立领域问题"}
        """
    )

    result = await rewrite_standalone_question(
        "逆变器绝缘阻抗低怎么排查？",
        context,
        client,
    )

    assert result.is_follow_up is False
    assert result.used_history is False
    assert result.standalone_question == "逆变器绝缘阻抗低怎么排查？"
    assert client.calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        "如果组串电压看起来正常，但告警还在，下一步怎么办？",
        "能不能给我一个运维人员能看懂的处理建议？",
        "给我整理成现场处理建议",
        "这个问题最后怎么处理？",
    ],
)
async def test_rewrite_standalone_question_uses_history_for_operational_followups(question):
    context = ConversationContext(
        session_summary={"summary": "用户正在排查逆变器绝缘阻抗低告警。"},
        recent_turns=[
            {
                "question": "逆变器报“绝缘阻抗低”，一般应该怎么排查？",
                "answer_excerpt": "重点检查直流线缆破皮、接头进水和绝缘电阻。",
            }
        ],
        used_history=True,
    )
    client = FakeChatClient(
        """
        {"is_follow_up": true, "used_history": true,
         "standalone_question": "逆变器绝缘阻抗低告警下，组串电压正常但告警仍在，下一步如何处理？",
         "reason": "补全告警上下文"}
        """
    )

    result = await rewrite_standalone_question(question, context, client)

    assert result.is_follow_up is True
    assert result.used_history is True
    assert client.calls


@pytest.mark.asyncio
async def test_rewrite_marks_summary_advice_request_as_followup():
    context = ConversationContext(
        session_summary={"summary": "用户正在排查逆变器绝缘阻抗低告警。"},
        recent_turns=[
            {
                "question": "这个告警会影响发电量吗？",
                "answer_excerpt": "会，逆变器停机会导致发电量损失。",
            }
        ],
        used_history=True,
    )
    client = FakeChatClient(
        """
        {"is_follow_up": true, "used_history": true,
         "standalone_question": "请把逆变器绝缘阻抗低告警的处理方法整理成运维人员能看懂的现场处理建议。",
         "reason": "用户要求整理前文为现场建议"}
        """
    )

    result = await rewrite_standalone_question(
        "能不能给我一个运维人员能看懂的处理建议？",
        context,
        client,
    )

    assert result.used_history is True
    assert "绝缘阻抗低" in result.standalone_question


@pytest.mark.asyncio
async def test_rewrite_standalone_question_falls_back_to_original_on_error():
    context = ConversationContext(
        session_summary={"summary": "历史"},
        recent_turns=[{"question": "上一轮"}],
        used_history=True,
    )
    client = FakeChatClient("not json")

    result = await rewrite_standalone_question("那当前问题呢？", context, client)

    assert result.standalone_question == "那当前问题呢？"
    assert result.reason == "rewrite_fallback_after_llm_failure"
