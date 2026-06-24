from __future__ import annotations

import json
from typing import Any


def build_intent_messages(question: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你只做意图识别，是光伏运维知识库问答系统的查询理解模块。"
                "只输出 JSON，不要回答用户问题。"
                "必须保留原意、设备名称、故障码、型号、英文缩写和技术术语。"
                "intent 只能是 knowledge_base_qa、general_explanation、out_of_scope、"
                "realtime_external、invalid_input。"
                "例如：今天上海天气怎么样？属于 realtime_external；"
                "什么是无功功率？通常属于 general_explanation。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请识别用户问题意图并改写检索 query，输出字段："
                "intent, confidence, should_use_knowledge_base, normalized_question, "
                f"search_query, reason。\n用户问题：{question}"
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


def build_general_answer_messages(question: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你是通用问答助手。本次回答不引用项目知识库。"
                "回答要简洁、准确，不要声称来自项目知识库。"
            ),
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
