from types import SimpleNamespace

import pytest

from app.services.answer_generation import generate_general_answer, generate_rag_answer


class FakeChatClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = []

    async def chat(self, messages, temperature=0.1):
        self.calls.append({"messages": messages, "temperature": temperature})
        return self.response


@pytest.mark.asyncio
async def test_generate_rag_answer_includes_evidence_and_forbids_ungrounded_answer():
    evidence = [
        SimpleNamespace(
            heading_path="03_线缆接头与绝缘故障 > 4. 绝缘阻抗问题",
            clean_text="绝缘阻抗偏低可能与直流线缆破皮、接头进水或组串绝缘异常有关。",
            rerank_score=0.85,
        )
    ]
    client = FakeChatClient("应先检查直流线缆、接头进水和组串绝缘电阻。")

    answer = await generate_rag_answer(
        chat_client=client,
        question="逆变器绝缘阻抗低怎么排查？",
        evidence=evidence,
        cautious=False,
    )

    assert "直流线缆" in answer
    assert client.calls[0]["temperature"] == 0.1
    system_prompt = client.calls[0]["messages"][0]["content"]
    user_prompt = client.calls[0]["messages"][1]["content"]
    assert "只能基于给定证据回答" in system_prompt
    assert "证据 1" in user_prompt
    assert "03_线缆接头与绝缘故障" in user_prompt
    assert "绝缘阻抗偏低可能与直流线缆破皮" in user_prompt


@pytest.mark.asyncio
async def test_generate_rag_answer_adds_cautious_instruction_when_requested():
    evidence = [
        SimpleNamespace(
            heading_path="02_逆变器告警 > 漏电流告警",
            clean_text="漏电流告警可先排查组件绝缘、线缆破损和接地情况。",
            rerank_score=0.31,
        )
    ]
    client = FakeChatClient("根据当前知识库中相关片段，可能需要先做绝缘和接地检查。")

    await generate_rag_answer(
        chat_client=client,
        question="逆变器漏电流告警怎么处理？",
        evidence=evidence,
        cautious=True,
    )

    system_prompt = client.calls[0]["messages"][0]["content"]
    assert "谨慎语气" in system_prompt
    assert "根据当前知识库中相关片段" in system_prompt


@pytest.mark.asyncio
async def test_generate_general_answer_marks_no_knowledge_base_use():
    client = FakeChatClient("无功功率是交流系统中用于建立电磁场的功率。")

    answer = await generate_general_answer(
        chat_client=client,
        question="什么是无功功率？",
    )

    assert "无功功率" in answer
    assert client.calls[0]["temperature"] == 0.1
    system_prompt = client.calls[0]["messages"][0]["content"]
    assert "不引用项目知识库" in system_prompt
