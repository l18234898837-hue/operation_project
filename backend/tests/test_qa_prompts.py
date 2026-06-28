from app.prompts.qa_prompts import (
    build_general_answer_messages,
    build_intent_messages,
    build_low_confidence_rag_answer_messages,
    build_rag_answer_messages,
    build_session_summary_messages,
    build_standalone_question_messages,
)


def test_intent_prompt_requires_json_and_no_answering():
    messages = build_intent_messages("什么是无功功率？")
    joined = "\n".join(message["content"] for message in messages)

    assert "只输出一个 JSON 对象" in joined
    assert "不要 Markdown" in joined
    assert "不要代码块" in joined
    assert "不要回答用户问题" in joined
    assert "字段只能包含 intent 和 confidence" in joined
    assert "search_query" not in joined
    assert "reason" not in joined
    assert "什么是无功功率？" in joined


def test_rag_answer_prompt_forbids_ungrounded_answer():
    evidence = [
        {
            "heading_path": "03_线缆接头与绝缘故障 > 4. 绝缘阻抗问题",
            "clean_text": "绝缘阻抗低可能由直流线缆破皮接地导致。",
            "rerank_score": 0.86,
        }
    ]

    messages = build_rag_answer_messages(
        question="逆变器绝缘阻抗低怎么排查？",
        evidence=evidence,
        cautious=False,
    )
    joined = "\n".join(message["content"] for message in messages)

    assert "只能基于给定证据回答" in joined
    assert "不要编造" in joined
    assert "不得给出具体数值" in joined
    assert "厂家手册、现场规程或电站安全规范" in joined
    assert "绝缘阻抗低可能由直流线缆破皮接地导致" in joined


def test_rag_answer_prompt_prefers_concise_operational_structure():
    messages = build_rag_answer_messages(
        question="逆变器绝缘阻抗低怎么排查？",
        evidence=[
            {
                "heading_path": "03_线缆接头与绝缘故障 > 4. 绝缘阻抗问题",
                "clean_text": "绝缘阻抗低可能由直流线缆破皮接地导致。",
                "rerank_score": 0.86,
            }
        ],
        cautious=False,
    )
    joined = "\n".join(message["content"] for message in messages)

    assert "默认控制在 6-10 条要点" in joined
    assert "优先输出现场可执行步骤" in joined
    assert "不要写成长报告" in joined


def test_low_confidence_prompt_limits_ungrounded_numbers_and_followup_length():
    messages = build_low_confidence_rag_answer_messages(
        question="处理前需要注意哪些安全事项？",
        evidence=[
            {
                "heading_path": "08_安全风险与应急处理 > 2. 火灾风险 > 2.1 直流拉弧",
                "clean_text": "端子松动、接触不良可能引发直流拉弧。",
                "rerank_score": 0.02,
            }
        ],
        top_score=0.02,
    )
    joined = "\n".join(message["content"] for message in messages)

    assert "不得给出具体数值" in joined
    assert "厂家手册、现场规程或电站安全规范" in joined
    assert "能参考到的资料" in joined
    assert "结合现场经验的处理建议" in joined
    assert "模型补充建议" not in joined
    assert "追问型问题" in joined
    assert "4-6 条" in joined
    assert "不要写成长报告" in joined


def test_low_confidence_prompt_keeps_comparison_answers_short():
    messages = build_low_confidence_rag_answer_messages(
        question="把逆变器本体故障和通讯链路故障分开列一下。",
        evidence=[
            {
                "heading_path": "01_逆变器故障与维护 > 3.2 电网过压或欠压",
                "clean_text": "电网过压或欠压会导致逆变器保护停机。",
                "rerank_score": 0.08,
            }
        ],
        top_score=0.08,
    )
    joined = "\n".join(message["content"] for message in messages)

    assert "对比" in joined
    assert "简短对照表" in joined
    assert "600-900 字" in joined
    assert "不要重复展开背景" in joined


def test_general_answer_prompt_marks_no_knowledge_base_use():
    messages = build_general_answer_messages("什么是无功功率？")
    joined = "\n".join(message["content"] for message in messages)

    assert "不引用项目知识库" in joined
    assert "什么是无功功率？" in joined


def test_standalone_question_prompt_uses_summary_history_and_current_question():
    messages = build_standalone_question_messages(
        session_summary={"summary": "用户正在排查逆变器绝缘阻抗低问题。"},
        recent_turns=[
            {
                "question": "逆变器绝缘阻抗低怎么排查？",
                "answer_excerpt": "重点检查直流线缆破皮和接头进水。",
                "top_heading": "03_线缆接头与绝缘故障 > 4. 绝缘阻抗问题",
            }
        ],
        current_question="那下雨天才出现呢？",
    )
    joined = "\n".join(message["content"] for message in messages)

    assert "standalone_question" in joined
    assert "只改写问题，不回答问题" in joined
    assert "那下雨天才出现呢？" in joined
    assert "逆变器绝缘阻抗低" in joined
    assert "整理、总结、给出处理建议" in joined
    assert "运维人员能看懂" in joined


def test_session_summary_prompt_requires_structured_json():
    messages = build_session_summary_messages(
        previous_summary={"summary": "用户正在排查逆变器故障。"},
        turns=[
            {
                "question": "那下雨天才出现呢？",
                "answer_excerpt": "雨天可能导致接头进水，绝缘下降。",
            }
        ],
    )
    joined = "\n".join(message["content"] for message in messages)

    assert "只输出 JSON" in joined
    assert "current_topic" in joined
    assert "already_checked" in joined
