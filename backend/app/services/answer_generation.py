from __future__ import annotations

from typing import Protocol


class ChatClient(Protocol):
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
    ) -> str:
        ...


async def generate_rag_answer(
    chat_client: ChatClient,
    question: str,
    evidence: list[object],
    cautious: bool,
) -> str:
    system_prompt = (
        "你是光伏运维知识库问答助手。只能基于给定证据回答。"
        "如果证据不足，必须说明当前知识库依据不足。"
        "不要编造厂家参数、故障码、设备型号或标准阈值。"
        "回答面向光伏运维人员，优先给出可能原因、排查步骤、处理建议和安全注意事项。"
    )
    if cautious:
        system_prompt += (
            "当前检索置信度中等，回答必须使用谨慎语气，"
            "并说明“根据当前知识库中相关片段”。"
        )

    return await chat_client.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _build_rag_user_prompt(question, evidence)},
        ],
        temperature=0.1,
    )


async def generate_general_answer(
    chat_client: ChatClient,
    question: str,
) -> str:
    return await chat_client.chat(
        messages=[
            {
                "role": "system",
                "content": (
                    "你是通用问答助手。本次回答不引用项目知识库。"
                    "回答要简洁、准确，不要声称来自项目知识库。"
                ),
            },
            {"role": "user", "content": question},
        ],
        temperature=0.1,
    )


def _build_rag_user_prompt(question: str, evidence: list[object]) -> str:
    parts = [f"用户问题：{question}", "", "证据片段："]
    for index, item in enumerate(evidence, start=1):
        heading_path = getattr(item, "heading_path", "")
        clean_text = getattr(item, "clean_text", "")
        rerank_score = getattr(item, "rerank_score", None)
        parts.append(
            f"证据 {index}\n"
            f"标题路径：{heading_path}\n"
            f"rerank_score：{rerank_score}\n"
            f"内容：{clean_text[:1200]}"
        )
    parts.append("")
    parts.append("请基于以上证据回答用户问题。")
    return "\n\n".join(parts)
