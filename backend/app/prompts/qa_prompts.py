from __future__ import annotations

import json
from typing import Any


def build_intent_messages(question: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你是光伏运维问答系统的意图分类器。"
                "只输出一个 JSON 对象，不要 Markdown，不要代码块，不要解释，不要回答用户问题。"
                "JSON 字段只能包含 intent 和 confidence。"
                "intent 只能是 knowledge_base_qa、general_explanation、chitchat、"
                "out_of_scope、realtime_external、invalid_input。"
                "分类规则：光伏电站、组件、逆变器、组串、箱变、发电量、故障、报警、"
                "排查、维护相关为 knowledge_base_qa；光伏或电力基础概念解释为 "
                "general_explanation；问候、感谢、寒暄为 chitchat；天气、新闻、股价、"
                "价格、汇率、当前时间等实时外部信息为 realtime_external；空内容、乱码、"
                "无法理解为 invalid_input；与光伏运维无关为 out_of_scope。"
                "示例：逆变器漏电流报警怎么处理 -> knowledge_base_qa；"
                "什么是无功功率 -> general_explanation；今天上海天气怎么样 -> "
                "realtime_external；帮我写一首诗 -> out_of_scope；你好 -> chitchat。"
            ),
        },
        {
            "role": "user",
            "content": (
                "输出格式：{\"intent\":\"knowledge_base_qa\",\"confidence\":0.9}\n"
                f"用户问题：{question}"
            ),
        },
    ]


def build_rag_answer_messages(
    question: str,
    evidence: list[object],
    cautious: bool,
) -> list[dict[str, str]]:
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

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": build_rag_user_prompt(question, evidence)},
    ]


def build_general_answer_messages(
    question: str,
    mode: str = "general",
) -> list[dict[str, str]]:
    if mode == "chitchat":
        system_prompt = (
            "你是光伏电站运维知识助手。用户正在进行简短寒暄或礼貌表达。"
            "请用专业、友好、简洁的语气自然回应，并引导用户提出光伏运维相关问题。"
            "不要声称查询了知识库，不要展开技术长文。"
        )
    elif mode == "realtime_external":
        system_prompt = (
            "你是光伏电站运维知识助手。当前系统未接入实时外部数据源，"
            "本次回答不基于项目知识库，也不能给出天气、新闻、股价、价格、汇率等实时事实结论。"
            "请先明确说明这个边界，再提供与光伏运维相关的一般性替代建议；"
            "如果问题与光伏运维无关，请简洁说明可协助的范围。"
        )
    else:
        system_prompt = (
            "你是通用问答助手。本次回答不引用项目知识库。"
            "回答要简洁、准确，不要声称来自项目知识库。"
        )

    return [
        {
            "role": "system",
            "content": system_prompt,
        },
        {"role": "user", "content": question},
    ]


def build_standalone_question_messages(
    session_summary: dict[str, Any] | None,
    recent_turns: list[dict[str, Any]],
    current_question: str,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你是多轮问答的问题改写模块。只改写问题，不回答问题。"
                "你的任务是根据会话摘要、最近历史和当前问题，生成可以独立检索的 standalone_question。"
                "历史上下文只用于理解指代词，不作为事实来源。"
                "如果当前问题已经完整，standalone_question 可以等于当前问题。"
                "只输出 JSON，字段为 is_follow_up, used_history, standalone_question, reason。"
            ),
        },
        {
            "role": "user",
            "content": (
                "会话摘要：\n"
                f"{json.dumps(session_summary or {}, ensure_ascii=False)}\n\n"
                "最近历史：\n"
                f"{json.dumps(recent_turns, ensure_ascii=False)}\n\n"
                f"当前问题：{current_question}"
            ),
        },
    ]


def build_session_summary_messages(
    previous_summary: dict[str, Any] | None,
    turns: list[dict[str, Any]],
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你是光伏运维问答系统的会话摘要模块。"
                "请把历史对话压缩成结构化 JSON，只保留对后续追问理解有用的信息。"
                "不要新增对话中没有出现的事实。"
                "只输出 JSON，字段为 summary, current_topic, known_context, "
                "already_checked, open_questions, user_constraints。"
            ),
        },
        {
            "role": "user",
            "content": (
                "已有摘要：\n"
                f"{json.dumps(previous_summary or {}, ensure_ascii=False)}\n\n"
                "新增对话：\n"
                f"{json.dumps(turns, ensure_ascii=False)}"
            ),
        },
    ]


def build_rag_user_prompt(question: str, evidence: list[object]) -> str:
    parts = [f"用户问题：{question}", "", "证据片段："]
    for index, item in enumerate(evidence, start=1):
        heading_path = _value(item, "heading_path", "")
        clean_text = str(_value(item, "clean_text", "") or "")
        rerank_score = _value(item, "rerank_score", None)
        parts.append(
            f"证据 {index}\n"
            f"标题路径：{heading_path}\n"
            f"rerank_score：{rerank_score}\n"
            f"内容：{clean_text[:1200]}"
        )
    parts.append("")
    parts.append("请基于以上证据回答用户问题。")
    return "\n\n".join(parts)


def _value(item: object, key: str, default: Any) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)
