# RAG Multi-Turn Conversation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 RAG 问答接口上实现第一版多轮会话：返回并复用 `session_id`，用 `session_summary + 最近 10 轮压缩历史 + 当前问题` 生成 `standalone_question`，再基于当前轮重新检索证据并回答。

**Architecture:** 历史上下文只用于“理解和改写当前问题”，不作为最终答案事实来源。当前轮答案仍只使用当前轮检索证据，当前轮引用仍只来自当前轮 `references`。10 轮以后使用 LLM 生成结构化会话摘要，并存储到 `qa_session.session_metadata`。

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy 2.0, PostgreSQL JSONB, pytest, httpx, SiliconFlow chat API, existing RAG retrieval pipeline.

---

## 固定产品规则

1. 最近历史窗口使用最近 10 轮问答。
2. 历史上下文用于 `standalone_question` 改写和意图理解，不传入 RAG 答案生成。
3. RAG 答案仍只基于当前轮 evidence。
4. 当前轮 `references` 只来自当前轮检索结果。
5. 10 轮后生成 `session_summary`，之后每新增 5 轮或上下文超过 8000 字时更新。
6. 摘要使用 LLM 压缩，但输出必须是结构化 JSON，并通过代码字段约束校验。
7. `session_summary` 存在 `qa_session.session_metadata`，第一版不新建摘要表。
8. `QaAskResponse` 必须返回 `session_id`，方便前端后续追问复用。
9. 如果改写模型失败，系统使用当前问题原文作为 `standalone_question`，不能中断问答。
10. 多轮会话不能绕过现有实时外部拒答和低置信拒答逻辑。

## 当前项目事实

- FastAPI app: `backend/app/main.py`
- API router: `backend/app/api/router.py`
- QA API: `backend/app/api/qa.py`
- QA schema: `backend/app/schemas/qa.py`
- QA service: `backend/app/services/qa_service.py`
- Query understanding: `backend/app/services/query_understanding.py`
- Answer generation: `backend/app/services/answer_generation.py`
- Real dependency builder: `backend/app/services/qa_dependencies.py`
- RAG models: `backend/app/models/rag.py`
- `qa_session.session_metadata` 已存在，可用于保存 summary。
- `qa_record` 已记录每轮问答，可用于构造最近 10 轮历史。
- 当前 `QaAskRequest` 已支持 `session_id`，但 `QaAskResponse` 还没有返回 `session_id`。

## 文件结构

创建文件：

- `backend/app/prompts/qa_prompts.py`
  集中存放 intent、RAG answer、general answer、standalone rewrite、session summary 的 prompt 构造函数。

- `backend/app/services/conversation_context.py`
  读取并压缩最近 10 轮历史，构造 `ConversationContext`。

- `backend/app/services/conversation_rewrite.py`
  调用 LLM 将 `session_summary + 最近 10 轮 + 当前问题` 改写为 `standalone_question`。

- `backend/app/services/session_summary.py`
  判断是否需要更新 summary，调用 LLM 生成结构化摘要，并写入 `qa_session.session_metadata`。

- `backend/tests/test_qa_prompts.py`
  测试 prompt 构造函数关键约束。

- `backend/tests/test_conversation_context.py`
  测试历史窗口、截断、Top1 heading 提取。

- `backend/tests/test_conversation_rewrite.py`
  测试 standalone question JSON 解析、fallback、字段约束。

- `backend/tests/test_session_summary.py`
  测试 summary 更新时机、JSON 解析、metadata 合并。

- `backend/scripts/smoke_multiturn_qa.py`
  手动 live smoke test，用真实 API 验证两轮追问。

修改文件：

- `backend/app/core/config.py`
  增加多轮会话配置项。

- `.env.example`
  增加多轮会话配置项说明。

- `backend/app/schemas/qa.py`
  `QaAskResponse` 增加 `session_id`。

- `backend/app/services/query_understanding.py`
  改为从 `app.prompts.qa_prompts` 获取 intent messages。

- `backend/app/services/answer_generation.py`
  改为从 `app.prompts.qa_prompts` 获取 RAG/general messages。

- `backend/app/services/qa_service.py`
  接入多轮上下文、standalone rewrite、summary 更新、响应返回 `session_id`。

- `backend/app/services/qa_dependencies.py`
  构造真实 conversation rewriter 和 session summarizer。

- `backend/app/api/qa.py`
  传入多轮配置参数。

- `backend/tests/test_config.py`
  覆盖新增配置。

- `backend/tests/test_qa_api.py`
  覆盖响应 `session_id` 和多轮请求 schema。

- `backend/tests/test_qa_service.py`
  覆盖 session 复用、standalone question、summary 更新。

- `docs/RAG问答接口闭环流程说明.md`
  增加多轮会话说明。

不做：

- 前端页面。
- 会话列表 UI。
- 日志后台页面。
- 新建 summary 表。
- 多用户权限系统。
- 流式输出。

---

### Task 1: 增加多轮会话配置

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_config.py` 追加：

```python
def test_settings_reads_multi_turn_conversation_configuration():
    settings = Settings(
        conversation_history_turns="10",
        conversation_summary_after_turns="10",
        conversation_summary_refresh_turns="5",
        conversation_context_max_chars="8000",
        conversation_answer_excerpt_chars="500",
    )

    assert settings.conversation_history_turns == 10
    assert settings.conversation_summary_after_turns == 10
    assert settings.conversation_summary_refresh_turns == 5
    assert settings.conversation_context_max_chars == 8000
    assert settings.conversation_answer_excerpt_chars == 500
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_config.py::test_settings_reads_multi_turn_conversation_configuration -v
```

Expected: FAIL，因为 `Settings` 还没有这些字段。

- [ ] **Step 3: 增加配置字段**

在 `backend/app/core/config.py` 的 QA 配置后加入：

```python
    conversation_history_turns: int = 10
    conversation_summary_after_turns: int = 10
    conversation_summary_refresh_turns: int = 5
    conversation_context_max_chars: int = 8000
    conversation_answer_excerpt_chars: int = 500
```

- [ ] **Step 4: 更新 `.env.example`**

在 `.env.example` QA 配置后追加：

```env
# Multi-turn conversation configuration
# 最近用于理解追问的历史轮数
CONVERSATION_HISTORY_TURNS=10
# 超过多少轮后生成会话摘要
CONVERSATION_SUMMARY_AFTER_TURNS=10
# 摘要生成后，每新增多少轮刷新一次摘要
CONVERSATION_SUMMARY_REFRESH_TURNS=5
# 传给问题改写模型的历史上下文最大字符数
CONVERSATION_CONTEXT_MAX_CHARS=8000
# 每轮历史里保留的答案摘要最大字符数
CONVERSATION_ANSWER_EXCERPT_CHARS=500
```

- [ ] **Step 5: 运行测试确认通过**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_config.py -v
```

Expected: PASS。

---

### Task 2: 将 Prompt 集中到独立模块

**Files:**
- Create: `backend/app/prompts/qa_prompts.py`
- Create: `backend/tests/test_qa_prompts.py`
- Modify: `backend/app/services/query_understanding.py`
- Modify: `backend/app/services/answer_generation.py`
- Test: `backend/tests/test_qa_prompts.py`
- Test: `backend/tests/test_query_understanding.py`
- Test: `backend/tests/test_answer_generation.py`

- [ ] **Step 1: 写 prompt 测试**

创建 `backend/tests/test_qa_prompts.py`：

```python
from app.prompts.qa_prompts import (
    build_general_answer_messages,
    build_intent_messages,
    build_rag_answer_messages,
    build_session_summary_messages,
    build_standalone_question_messages,
)


def test_intent_prompt_requires_json_and_no_answering():
    messages = build_intent_messages("什么是无功功率？")
    joined = "\n".join(message["content"] for message in messages)

    assert "只输出 JSON" in joined
    assert "不要回答用户问题" in joined
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

    assert "只能够基于给定证据回答" in joined
    assert "不要编造" in joined
    assert "绝缘阻抗低可能由直流线缆破皮接地导致" in joined


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
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_qa_prompts.py -v
```

Expected: FAIL，因为 `app.prompts.qa_prompts` 不存在。

- [ ] **Step 3: 创建 prompt 模块**

创建 `backend/app/prompts/qa_prompts.py`：

```python
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
        "你是光伏运维知识库问答助手。只能够基于给定证据回答。"
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
        clean_text = _value(item, "clean_text", "")
        rerank_score = _value(item, "rerank_score", None)
        parts.append(
            f"证据 {index}\n"
            f"标题路径：{heading_path}\n"
            f"rerank_score：{rerank_score}\n"
            f"内容：{str(clean_text)[:1200]}"
        )
    parts.append("")
    parts.append("请基于以上证据回答用户问题。")
    return "\n\n".join(parts)


def _value(item: object, key: str, default: Any) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)
```

- [ ] **Step 4: 修改 query understanding 使用 prompt 模块**

在 `backend/app/services/query_understanding.py`：

1. 增加导入：

```python
from app.prompts.qa_prompts import build_intent_messages
```

2. 将 `understand_query` 中：

```python
messages=_build_intent_messages(normalized),
```

改成：

```python
messages=build_intent_messages(normalized),
```

3. 删除本文件中的 `_build_intent_messages` 函数。

- [ ] **Step 5: 修改 answer generation 使用 prompt 模块**

在 `backend/app/services/answer_generation.py` 中改成：

```python
from __future__ import annotations

from typing import Protocol

from app.prompts.qa_prompts import (
    build_general_answer_messages,
    build_rag_answer_messages,
)


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
    return await chat_client.chat(
        messages=build_rag_answer_messages(
            question=question,
            evidence=evidence,
            cautious=cautious,
        ),
        temperature=0.1,
    )


async def generate_general_answer(
    chat_client: ChatClient,
    question: str,
) -> str:
    return await chat_client.chat(
        messages=build_general_answer_messages(question),
        temperature=0.1,
    )
```

- [ ] **Step 6: 运行相关测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_qa_prompts.py backend\tests\test_query_understanding.py backend\tests\test_answer_generation.py -v
```

Expected: PASS。

---

### Task 3: 响应中返回 session_id

**Files:**
- Modify: `backend/app/schemas/qa.py`
- Modify: `backend/app/services/qa_service.py`
- Modify: `backend/tests/test_qa_api.py`
- Modify: `backend/tests/test_qa_service.py`

- [ ] **Step 1: 写 schema 测试**

在 `backend/tests/test_qa_api.py` 增加：

```python
def test_qa_response_includes_session_id():
    response = QaAskResponse(
        session_id="11111111-1111-1111-1111-111111111111",
        trace_id="trace-1",
        answer_type="rag",
        intent="knowledge_base_qa",
        answer="测试回答",
        confidence=0.8,
        references=[],
        decision={},
    )

    assert response.session_id == "11111111-1111-1111-1111-111111111111"
```

- [ ] **Step 2: 写 service 测试**

在 `backend/tests/test_qa_service.py` 增加：

```python
@pytest.mark.asyncio
async def test_answer_question_returns_session_id_for_new_session():
    session = FakeSession()
    dependencies = make_dependencies(make_understanding(), make_evidence(score=0.8))

    response = await answer_question(
        session=session,
        question="逆变器绝缘阻抗低怎么排查？",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    qa_sessions = get_added(session, QaSession)
    assert response.session_id == str(qa_sessions[0].id)


@pytest.mark.asyncio
async def test_answer_question_reuses_supplied_session_id():
    session = FakeSession()
    session_id = uuid.uuid4()
    dependencies = make_dependencies(make_understanding(), make_evidence(score=0.8))

    response = await answer_question(
        session=session,
        question="逆变器绝缘阻抗低怎么排查？",
        session_id=session_id,
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    assert response.session_id == str(session_id)
```

如果 `FakeSession` 没有 `get` 方法，先在 `FakeSession` 中增加：

```python
    def get(self, model_type, item_id):
        for item in self.added:
            if isinstance(item, model_type) and getattr(item, "id", None) == item_id:
                return item
        return None
```

- [ ] **Step 3: 运行测试确认失败**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_qa_api.py::test_qa_response_includes_session_id backend\tests\test_qa_service.py::test_answer_question_returns_session_id_for_new_session -v
```

Expected: FAIL，因为 `QaAskResponse` 还没有 `session_id`。

- [ ] **Step 4: 修改 schema**

在 `backend/app/schemas/qa.py` 的 `QaAskResponse` 中加入：

```python
    session_id: str
```

- [ ] **Step 5: 修改 response 构造**

在 `backend/app/services/qa_service.py` 修改 `_response_from_record`：

```python
def _response_from_record(
    record: QaRecord,
    intent: str,
    references: list[QaReferenceSchema],
) -> QaAskResponse:
    return QaAskResponse(
        session_id=str(record.session_id),
        trace_id=record.trace_id or "",
        answer_type=record.answer_type.value,
        intent=intent,
        answer=record.answer or "",
        confidence=record.confidence,
        references=references,
        decision=dict(record.decision_metadata or {}),
    )
```

- [ ] **Step 6: 更新所有测试里的 QaAskResponse 构造**

在 `backend/tests/test_qa_api.py` 中所有 `QaAskResponse(...)` 增加：

```python
session_id="11111111-1111-1111-1111-111111111111",
```

- [ ] **Step 7: 运行测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_qa_api.py backend\tests\test_qa_service.py -v
```

Expected: PASS。

---

### Task 4: 构造最近 10 轮压缩历史上下文

**Files:**
- Create: `backend/app/services/conversation_context.py`
- Create: `backend/tests/test_conversation_context.py`

- [ ] **Step 1: 写测试**

创建 `backend/tests/test_conversation_context.py`：

```python
from types import SimpleNamespace
import uuid

from app.models.rag import AnswerType
from app.services.conversation_context import (
    ConversationContext,
    build_context_from_records,
    should_include_history,
)


def make_record(index: int, answer: str = "答案内容") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        question=f"第 {index} 轮问题",
        normalized_question=f"第 {index} 轮规范化问题",
        answer=answer,
        answer_type=AnswerType.rag,
        confidence=0.8,
        decision_metadata={
            "intent": "knowledge_base_qa",
            "refusal_reason": None,
        },
        references=[
            SimpleNamespace(
                rank=1,
                ref_metadata={"heading_path": f"标题路径 {index}"},
            )
        ],
    )


def test_build_context_keeps_latest_turns_only():
    records = [make_record(index) for index in range(12)]

    context = build_context_from_records(
        records=records,
        session_metadata={"conversation_summary": {"summary": "早期摘要"}},
        history_turns=10,
        answer_excerpt_chars=20,
        max_chars=8000,
    )

    assert isinstance(context, ConversationContext)
    assert context.session_summary == {"summary": "早期摘要"}
    assert len(context.recent_turns) == 10
    assert context.recent_turns[0]["question"] == "第 2 轮问题"
    assert context.recent_turns[-1]["question"] == "第 11 轮问题"
    assert context.recent_turns[-1]["top_heading"] == "标题路径 11"


def test_build_context_truncates_answer_excerpt():
    context = build_context_from_records(
        records=[make_record(1, answer="一" * 100)],
        session_metadata={},
        history_turns=10,
        answer_excerpt_chars=30,
        max_chars=8000,
    )

    assert context.recent_turns[0]["answer_excerpt"] == "一" * 30


def test_build_context_respects_max_chars():
    records = [make_record(index, answer="长答案" * 200) for index in range(10)]

    context = build_context_from_records(
        records=records,
        session_metadata={},
        history_turns=10,
        answer_excerpt_chars=500,
        max_chars=600,
    )

    assert len(str(context.recent_turns)) <= 900
    assert len(context.recent_turns) < 10


def test_should_include_history_detects_follow_up_words():
    assert should_include_history("那下雨天才出现呢？") is True
    assert should_include_history("继续说一下处理方法") is True
    assert should_include_history("逆变器绝缘阻抗低怎么排查？") is False
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_conversation_context.py -v
```

Expected: FAIL，因为模块不存在。

- [ ] **Step 3: 实现 conversation_context**

创建 `backend/app/services/conversation_context.py`：

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


FOLLOW_UP_TERMS = (
    "那",
    "这个",
    "刚才",
    "继续",
    "还有",
    "如果这样",
    "上面",
    "前面",
    "它",
    "这种情况",
)


@dataclass(frozen=True)
class ConversationContext:
    session_summary: dict[str, Any] | None
    recent_turns: list[dict[str, Any]]


def build_context_from_records(
    records: list[object],
    session_metadata: dict[str, Any] | None,
    history_turns: int,
    answer_excerpt_chars: int,
    max_chars: int,
) -> ConversationContext:
    metadata = session_metadata or {}
    summary = metadata.get("conversation_summary")
    if not isinstance(summary, dict):
        summary = None

    recent_records = list(records)[-history_turns:]
    turns = [_record_to_turn(record, answer_excerpt_chars) for record in recent_records]

    while turns and len(str(turns)) > max_chars:
        turns.pop(0)

    return ConversationContext(
        session_summary=summary,
        recent_turns=turns,
    )


def should_include_history(question: str) -> bool:
    return any(term in question for term in FOLLOW_UP_TERMS)


def _record_to_turn(record: object, answer_excerpt_chars: int) -> dict[str, Any]:
    decision = getattr(record, "decision_metadata", None) or {}
    answer = getattr(record, "answer", None) or ""
    return {
        "question": getattr(record, "question", "") or "",
        "normalized_question": getattr(record, "normalized_question", "") or "",
        "intent": decision.get("intent"),
        "answer_type": _answer_type_value(getattr(record, "answer_type", None)),
        "confidence": getattr(record, "confidence", None),
        "answer_excerpt": answer[:answer_excerpt_chars],
        "top_heading": _top_heading(record),
        "refusal_reason": decision.get("refusal_reason"),
    }


def _answer_type_value(value: object) -> str | None:
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    if isinstance(value, str):
        return value
    return None


def _top_heading(record: object) -> str | None:
    references = getattr(record, "references", None) or []
    sorted_refs = sorted(
        references,
        key=lambda item: getattr(item, "rank", 999) or 999,
    )
    if not sorted_refs:
        return None
    metadata = getattr(sorted_refs[0], "ref_metadata", None) or {}
    heading = metadata.get("heading_path")
    return heading if isinstance(heading, str) else None
```

- [ ] **Step 4: 运行测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_conversation_context.py -v
```

Expected: PASS。

---

### Task 5: 实现 standalone_question 改写服务

**Files:**
- Create: `backend/app/services/conversation_rewrite.py`
- Create: `backend/tests/test_conversation_rewrite.py`

- [ ] **Step 1: 写测试**

创建 `backend/tests/test_conversation_rewrite.py`：

```python
import pytest

from app.services.conversation_context import ConversationContext
from app.services.conversation_rewrite import (
    StandaloneQuestionResult,
    rewrite_standalone_question,
)


class FakeChatClient:
    def __init__(self, content: str | Exception):
        self.content = content
        self.calls = []

    async def chat(self, messages, temperature=0.1):
        self.calls.append({"messages": messages, "temperature": temperature})
        if isinstance(self.content, Exception):
            raise self.content
        return self.content


@pytest.mark.asyncio
async def test_rewrite_standalone_question_uses_history_context():
    context = ConversationContext(
        session_summary={"summary": "用户正在排查逆变器绝缘阻抗低问题。"},
        recent_turns=[
            {
                "question": "逆变器绝缘阻抗低怎么排查？",
                "answer_excerpt": "重点检查直流线缆破皮和接头进水。",
                "top_heading": "03_线缆接头与绝缘故障 > 4. 绝缘阻抗问题",
            }
        ],
    )
    client = FakeChatClient(
        """
        {
          "is_follow_up": true,
          "used_history": true,
          "standalone_question": "逆变器绝缘阻抗低故障如果只在下雨天出现，应如何排查？",
          "reason": "当前问题承接上一轮绝缘阻抗低故障"
        }
        """
    )

    result = await rewrite_standalone_question(
        question="那下雨天才出现呢？",
        context=context,
        chat_client=client,
    )

    assert isinstance(result, StandaloneQuestionResult)
    assert result.is_follow_up is True
    assert result.used_history is True
    assert result.standalone_question == "逆变器绝缘阻抗低故障如果只在下雨天出现，应如何排查？"


@pytest.mark.asyncio
async def test_rewrite_standalone_question_falls_back_when_model_fails():
    result = await rewrite_standalone_question(
        question="那下雨天才出现呢？",
        context=ConversationContext(session_summary=None, recent_turns=[]),
        chat_client=FakeChatClient(RuntimeError("model failed")),
    )

    assert result.is_follow_up is False
    assert result.used_history is False
    assert result.standalone_question == "那下雨天才出现呢？"
    assert result.reason == "fallback_after_rewrite_failure"


@pytest.mark.asyncio
async def test_rewrite_standalone_question_falls_back_for_invalid_json():
    result = await rewrite_standalone_question(
        question="那下雨天才出现呢？",
        context=ConversationContext(session_summary=None, recent_turns=[]),
        chat_client=FakeChatClient("not json"),
    )

    assert result.standalone_question == "那下雨天才出现呢？"
    assert result.reason == "fallback_after_rewrite_failure"
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_conversation_rewrite.py -v
```

Expected: FAIL，因为模块不存在。

- [ ] **Step 3: 实现 conversation_rewrite**

创建 `backend/app/services/conversation_rewrite.py`：

```python
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Protocol

from app.prompts.qa_prompts import build_standalone_question_messages
from app.services.conversation_context import ConversationContext
from app.services.keyword_index import normalize_query


class ChatClient(Protocol):
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
    ) -> str:
        ...


@dataclass(frozen=True)
class StandaloneQuestionResult:
    is_follow_up: bool
    used_history: bool
    standalone_question: str
    reason: str


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(?P<body>.*?)```", re.IGNORECASE | re.DOTALL)


async def rewrite_standalone_question(
    question: str,
    context: ConversationContext,
    chat_client: ChatClient,
) -> StandaloneQuestionResult:
    normalized_question = normalize_query(question)
    if not context.recent_turns and not context.session_summary:
        return StandaloneQuestionResult(
            is_follow_up=False,
            used_history=False,
            standalone_question=normalized_question,
            reason="no_history_context",
        )

    try:
        content = await chat_client.chat(
            messages=build_standalone_question_messages(
                session_summary=context.session_summary,
                recent_turns=context.recent_turns,
                current_question=normalized_question,
            ),
            temperature=0.1,
        )
        payload = _load_json(content)
        standalone_question = normalize_query(str(payload.get("standalone_question") or normalized_question))
        return StandaloneQuestionResult(
            is_follow_up=bool(payload.get("is_follow_up")),
            used_history=bool(payload.get("used_history")),
            standalone_question=standalone_question or normalized_question,
            reason=str(payload.get("reason") or "llm_standalone_rewrite"),
        )
    except Exception:
        return StandaloneQuestionResult(
            is_follow_up=False,
            used_history=False,
            standalone_question=normalized_question,
            reason="fallback_after_rewrite_failure",
        )


def _load_json(content: str) -> dict:
    text = content.strip()
    fence_match = _JSON_FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group("body").strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("standalone rewrite output must be a JSON object")
    return data
```

- [ ] **Step 4: 运行测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_conversation_rewrite.py -v
```

Expected: PASS。

---

### Task 6: 实现会话摘要更新服务

**Files:**
- Create: `backend/app/services/session_summary.py`
- Create: `backend/tests/test_session_summary.py`

- [ ] **Step 1: 写测试**

创建 `backend/tests/test_session_summary.py`：

```python
from types import SimpleNamespace
import uuid

import pytest

from app.models.rag import AnswerType
from app.services.session_summary import (
    SESSION_SUMMARY_METADATA_KEY,
    maybe_update_session_summary,
    should_refresh_summary,
)


class FakeChatClient:
    def __init__(self, content):
        self.content = content
        self.calls = []

    async def chat(self, messages, temperature=0.1):
        self.calls.append({"messages": messages, "temperature": temperature})
        return self.content


class FakeSession:
    def __init__(self):
        self.flushes = 0

    def flush(self):
        self.flushes += 1


def make_qa_session(metadata=None):
    return SimpleNamespace(id=uuid.uuid4(), session_metadata=metadata)


def make_record(index):
    return SimpleNamespace(
        question=f"第 {index} 轮问题",
        normalized_question=f"第 {index} 轮规范化问题",
        answer=f"第 {index} 轮答案",
        answer_type=AnswerType.rag,
        confidence=0.8,
        decision_metadata={"intent": "knowledge_base_qa"},
        references=[],
    )


def test_should_refresh_summary_after_threshold():
    assert should_refresh_summary(record_count=10, summarized_turn_count=0, after_turns=10, refresh_turns=5) is True
    assert should_refresh_summary(record_count=12, summarized_turn_count=10, after_turns=10, refresh_turns=5) is False
    assert should_refresh_summary(record_count=15, summarized_turn_count=10, after_turns=10, refresh_turns=5) is True


@pytest.mark.asyncio
async def test_maybe_update_session_summary_writes_metadata():
    qa_session = make_qa_session(metadata={})
    db_session = FakeSession()
    records = [make_record(index) for index in range(10)]
    client = FakeChatClient(
        """
        {
          "summary": "用户正在排查逆变器绝缘阻抗低问题。",
          "current_topic": "雨天出现绝缘阻抗低报警",
          "known_context": ["雨天更容易出现"],
          "already_checked": ["直流接头"],
          "open_questions": ["是否逐路测量绝缘电阻"],
          "user_constraints": []
        }
        """
    )

    updated = await maybe_update_session_summary(
        db_session=db_session,
        qa_session=qa_session,
        records=records,
        chat_client=client,
        after_turns=10,
        refresh_turns=5,
        answer_excerpt_chars=200,
    )

    assert updated is True
    assert qa_session.session_metadata[SESSION_SUMMARY_METADATA_KEY]["summary"] == "用户正在排查逆变器绝缘阻抗低问题。"
    assert qa_session.session_metadata["conversation_summary_turn_count"] == 10
    assert db_session.flushes == 1


@pytest.mark.asyncio
async def test_maybe_update_session_summary_skips_before_threshold():
    qa_session = make_qa_session(metadata={})
    db_session = FakeSession()
    records = [make_record(index) for index in range(3)]
    client = FakeChatClient("{}")

    updated = await maybe_update_session_summary(
        db_session=db_session,
        qa_session=qa_session,
        records=records,
        chat_client=client,
        after_turns=10,
        refresh_turns=5,
        answer_excerpt_chars=200,
    )

    assert updated is False
    assert client.calls == []
    assert db_session.flushes == 0
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_session_summary.py -v
```

Expected: FAIL，因为模块不存在。

- [ ] **Step 3: 实现 session_summary**

创建 `backend/app/services/session_summary.py`：

```python
from __future__ import annotations

import json
import re
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.prompts.qa_prompts import build_session_summary_messages
from app.services.conversation_context import build_context_from_records


SESSION_SUMMARY_METADATA_KEY = "conversation_summary"
SUMMARY_TURN_COUNT_KEY = "conversation_summary_turn_count"
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(?P<body>.*?)```", re.IGNORECASE | re.DOTALL)


class ChatClient(Protocol):
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
    ) -> str:
        ...


def should_refresh_summary(
    record_count: int,
    summarized_turn_count: int,
    after_turns: int,
    refresh_turns: int,
) -> bool:
    if record_count < after_turns:
        return False
    if summarized_turn_count <= 0:
        return True
    return record_count - summarized_turn_count >= refresh_turns


async def maybe_update_session_summary(
    db_session: Session,
    qa_session: object,
    records: list[object],
    chat_client: ChatClient,
    after_turns: int,
    refresh_turns: int,
    answer_excerpt_chars: int,
) -> bool:
    metadata = dict(getattr(qa_session, "session_metadata", None) or {})
    summarized_turn_count = int(metadata.get(SUMMARY_TURN_COUNT_KEY) or 0)
    record_count = len(records)
    if not should_refresh_summary(record_count, summarized_turn_count, after_turns, refresh_turns):
        return False

    previous_summary = metadata.get(SESSION_SUMMARY_METADATA_KEY)
    if not isinstance(previous_summary, dict):
        previous_summary = None
    context = build_context_from_records(
        records=records,
        session_metadata=metadata,
        history_turns=record_count,
        answer_excerpt_chars=answer_excerpt_chars,
        max_chars=12000,
    )
    content = await chat_client.chat(
        messages=build_session_summary_messages(
            previous_summary=previous_summary,
            turns=context.recent_turns,
        ),
        temperature=0.1,
    )
    summary = _sanitize_summary(_load_json(content))
    metadata[SESSION_SUMMARY_METADATA_KEY] = summary
    metadata[SUMMARY_TURN_COUNT_KEY] = record_count
    setattr(qa_session, "session_metadata", metadata)
    db_session.flush()
    return True


def _load_json(content: str) -> dict[str, Any]:
    text = content.strip()
    fence_match = _JSON_FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group("body").strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("session summary output must be a JSON object")
    return data


def _sanitize_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": str(payload.get("summary") or ""),
        "current_topic": str(payload.get("current_topic") or ""),
        "known_context": _string_list(payload.get("known_context")),
        "already_checked": _string_list(payload.get("already_checked")),
        "open_questions": _string_list(payload.get("open_questions")),
        "user_constraints": _string_list(payload.get("user_constraints")),
    }


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]
```

- [ ] **Step 4: 运行测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_session_summary.py -v
```

Expected: PASS。

---

### Task 7: 将多轮上下文接入 QA Service

**Files:**
- Modify: `backend/app/services/qa_service.py`
- Modify: `backend/tests/test_qa_service.py`

- [ ] **Step 1: 扩展测试 fake**

在 `backend/tests/test_qa_service.py` 中增加：

```python
from app.services.conversation_rewrite import StandaloneQuestionResult
```

增加 fake：

```python
class FakeContextRewriter:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def rewrite(self, question, context):
        self.calls.append({"question": question, "context": context})
        return self.result


class FakeSessionSummarizer:
    def __init__(self):
        self.calls = []

    async def maybe_update(self, session, qa_session, records):
        self.calls.append(
            {"session": session, "qa_session": qa_session, "records": records}
        )
        return False
```

更新 `make_dependencies`：

```python
def make_dependencies(understanding, evidence, context_rewriter=None, session_summarizer=None):
    return QaDependencies(
        understanding_client=FakeUnderstandingClient(understanding),
        retriever=FakeRetriever(evidence),
        answer_client=FakeAnswerClient(),
        context_rewriter=context_rewriter,
        session_summarizer=session_summarizer,
    )
```

更新 `FakeSession` 支持 query history：

```python
    def __init__(self):
        self.added = []
        self.commits = 0
        self.flushes = 0
        self.rollbacks = 0
        self.records_by_session_id = {}

    def get(self, model_type, item_id):
        for item in self.added:
            if isinstance(item, model_type) and getattr(item, "id", None) == item_id:
                return item
        return None

    def list_records(self, session_id):
        return self.records_by_session_id.get(session_id, [])
```

- [ ] **Step 2: 写 service 多轮测试**

在 `backend/tests/test_qa_service.py` 增加：

```python
@pytest.mark.asyncio
async def test_answer_question_rewrites_follow_up_before_understanding_and_retrieval():
    session = FakeSession()
    session_id = uuid.uuid4()
    existing_session = QaSession(id=session_id)
    previous_record = QaRecord(
        session_id=session_id,
        question="逆变器绝缘阻抗低怎么排查？",
        normalized_question="逆变器绝缘阻抗低怎么排查？",
        answer="重点检查直流线缆破皮和接头进水。",
        answer_type=AnswerType.rag,
        confidence=0.8,
        decision_metadata={"intent": "knowledge_base_qa", "refusal_reason": None},
    )
    previous_record.id = uuid.uuid4()
    session.added.append(existing_session)
    session.records_by_session_id[session_id] = [previous_record]
    rewriter = FakeContextRewriter(
        StandaloneQuestionResult(
            is_follow_up=True,
            used_history=True,
            standalone_question="逆变器绝缘阻抗低故障如果只在下雨天出现，应如何排查？",
            reason="follow_up_rainy_day",
        )
    )
    dependencies = make_dependencies(
        make_understanding(
            normalized_question="逆变器绝缘阻抗低故障如果只在下雨天出现，应如何排查？",
            search_query="逆变器 绝缘阻抗低 下雨天 排查",
        ),
        make_evidence(score=0.8),
        context_rewriter=rewriter,
        session_summarizer=FakeSessionSummarizer(),
    )

    response = await answer_question(
        session=session,
        question="那下雨天才出现呢？",
        session_id=session_id,
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
        history_turns=10,
        context_max_chars=8000,
        answer_excerpt_chars=500,
    )

    assert response.session_id == str(session_id)
    assert dependencies.understanding_client.calls == ["逆变器绝缘阻抗低故障如果只在下雨天出现，应如何排查？"]
    assert dependencies.retriever.calls == ["逆变器 绝缘阻抗低 下雨天 排查"]
    assert response.decision["standalone_question"] == "逆变器绝缘阻抗低故障如果只在下雨天出现，应如何排查？"
    assert response.decision["is_follow_up"] is True
    assert response.decision["used_history"] is True


@pytest.mark.asyncio
async def test_answer_question_does_not_pass_history_to_rag_answer_generation():
    session = FakeSession()
    rewriter = FakeContextRewriter(
        StandaloneQuestionResult(
            is_follow_up=True,
            used_history=True,
            standalone_question="逆变器绝缘阻抗低故障如果更换接头后仍报警，应继续排查哪里？",
            reason="follow_up_after_repair",
        )
    )
    dependencies = make_dependencies(
        make_understanding(
            normalized_question="逆变器绝缘阻抗低故障如果更换接头后仍报警，应继续排查哪里？",
            search_query="逆变器 绝缘阻抗低 更换接头 仍报警 排查",
        ),
        make_evidence(score=0.8),
        context_rewriter=rewriter,
    )

    await answer_question(
        session=session,
        question="那换了接头还报警呢？",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
        history_turns=10,
        context_max_chars=8000,
        answer_excerpt_chars=500,
    )

    rag_call = dependencies.answer_client.rag_calls[0]
    assert rag_call["question"] == "逆变器绝缘阻抗低故障如果更换接头后仍报警，应继续排查哪里？"
    assert "重点检查直流线缆破皮" not in rag_call["question"]
```

- [ ] **Step 3: 运行测试确认失败**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_qa_service.py::test_answer_question_rewrites_follow_up_before_understanding_and_retrieval -v
```

Expected: FAIL，因为 `QaDependencies` 和 `answer_question` 还没有多轮参数。

- [ ] **Step 4: 修改 QA service 协议和依赖**

在 `backend/app/services/qa_service.py` 增加导入：

```python
from app.services.conversation_context import build_context_from_records
from app.services.conversation_rewrite import StandaloneQuestionResult
```

增加 Protocol：

```python
class ContextRewriter(Protocol):
    async def rewrite(self, question: str, context: object) -> StandaloneQuestionResult:
        ...


class SessionSummarizer(Protocol):
    async def maybe_update(
        self,
        session: Session,
        qa_session: QaSession,
        records: list[QaRecord],
    ) -> bool:
        ...
```

修改 `QaDependencies`：

```python
@dataclass(frozen=True)
class QaDependencies:
    understanding_client: UnderstandingClient
    retriever: Retriever
    answer_client: AnswerClient
    context_rewriter: ContextRewriter | None = None
    session_summarizer: SessionSummarizer | None = None
```

修改 `answer_question` 签名：

```python
async def answer_question(
    session: Session,
    question: str,
    dependencies: QaDependencies,
    min_rerank_score: float,
    strong_rerank_score: float,
    reference_top_k: int,
    session_id: str | uuid.UUID | None = None,
    history_turns: int = 10,
    context_max_chars: int = 8000,
    answer_excerpt_chars: int = 500,
) -> QaAskResponse:
```

- [ ] **Step 5: 增加历史记录读取 helper**

在 `backend/app/services/qa_service.py` 增加：

```python
def _list_session_records(session: Session, qa_session: QaSession) -> list[QaRecord]:
    custom = getattr(session, "list_records", None)
    if callable(custom):
        return list(custom(qa_session.id))

    return (
        session.query(QaRecord)
        .filter(QaRecord.session_id == qa_session.id)
        .order_by(QaRecord.created_at.asc())
        .all()
    )
```

- [ ] **Step 6: 在理解问题前执行 rewrite**

在 `answer_question` 中，`qa_session = _get_or_create_session(...)` 后加入：

```python
    previous_records = _list_session_records(session, qa_session)
    rewrite_result = StandaloneQuestionResult(
        is_follow_up=False,
        used_history=False,
        standalone_question=question,
        reason="no_context_rewriter",
    )
    if dependencies.context_rewriter is not None:
        context = build_context_from_records(
            records=previous_records,
            session_metadata=qa_session.session_metadata,
            history_turns=history_turns,
            answer_excerpt_chars=answer_excerpt_chars,
            max_chars=context_max_chars,
        )
        rewrite_result = await dependencies.context_rewriter.rewrite(question, context)

    question_for_understanding = rewrite_result.standalone_question
    understanding = await dependencies.understanding_client.understand(question_for_understanding)
```

删除原来的：

```python
    understanding = await dependencies.understanding_client.understand(question)
```

- [ ] **Step 7: 将 rewrite 信息写入 decision_metadata**

所有 `_add_record(...)` 调用的 `decision_extra` 中增加：

```python
                "original_question": question,
                "standalone_question": rewrite_result.standalone_question,
                "is_follow_up": rewrite_result.is_follow_up,
                "used_history": rewrite_result.used_history,
                "rewrite_reason": rewrite_result.reason,
```

RAG answer 调用改为：

```python
    answer = await dependencies.answer_client.generate_rag(
        question=understanding.normalized_question,
        evidence=evidence_for_answer,
        cautious=cautious,
    )
```

保留当前逻辑，不传 history。

- [ ] **Step 8: 在 commit 前尝试更新 summary**

在每个路径 `session.commit()` 前调用：

```python
        _maybe_update_summary(
            session=session,
            qa_session=qa_session,
            dependencies=dependencies,
            previous_records=previous_records,
            record=record,
        )
```

并增加 helper：

```python
async def _maybe_update_summary(
    session: Session,
    qa_session: QaSession,
    dependencies: QaDependencies,
    previous_records: list[QaRecord],
    record: QaRecord,
) -> None:
    if dependencies.session_summarizer is None:
        return
    await dependencies.session_summarizer.maybe_update(
        session=session,
        qa_session=qa_session,
        records=[*previous_records, record],
    )
```

注意：该 helper 必须定义为 async，调用处必须 `await _maybe_update_summary(...)`。

- [ ] **Step 9: 运行 QA service 测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_qa_service.py -v
```

Expected: PASS。

---

### Task 8: 构造真实多轮依赖

**Files:**
- Modify: `backend/app/services/qa_dependencies.py`
- Modify: `backend/app/api/qa.py`
- Test: `backend/tests/test_qa_api.py`

- [ ] **Step 1: 实现真实 wrapper**

在 `backend/app/services/qa_dependencies.py` 增加：

```python
from app.services.conversation_context import ConversationContext
from app.services.conversation_rewrite import (
    StandaloneQuestionResult,
    rewrite_standalone_question,
)
from app.services.session_summary import maybe_update_session_summary
```

增加类：

```python
class RealContextRewriter:
    def __init__(self, chat_client: SiliconFlowChatClient) -> None:
        self._chat_client = chat_client

    async def rewrite(
        self,
        question: str,
        context: ConversationContext,
    ) -> StandaloneQuestionResult:
        return await rewrite_standalone_question(
            question=question,
            context=context,
            chat_client=self._chat_client,
        )


class RealSessionSummarizer:
    def __init__(
        self,
        chat_client: SiliconFlowChatClient,
        after_turns: int,
        refresh_turns: int,
        answer_excerpt_chars: int,
    ) -> None:
        self._chat_client = chat_client
        self._after_turns = after_turns
        self._refresh_turns = refresh_turns
        self._answer_excerpt_chars = answer_excerpt_chars

    async def maybe_update(self, session, qa_session, records) -> bool:
        return await maybe_update_session_summary(
            db_session=session,
            qa_session=qa_session,
            records=records,
            chat_client=self._chat_client,
            after_turns=self._after_turns,
            refresh_turns=self._refresh_turns,
            answer_excerpt_chars=self._answer_excerpt_chars,
        )
```

修改 `build_qa_dependencies(...)` 增加参数：

```python
    context_chat_client: SiliconFlowChatClient,
```

并在 `QaDependencies(...)` 中增加：

```python
        context_rewriter=RealContextRewriter(context_chat_client),
        session_summarizer=RealSessionSummarizer(
            chat_client=context_chat_client,
            after_turns=settings.conversation_summary_after_turns,
            refresh_turns=settings.conversation_summary_refresh_turns,
            answer_excerpt_chars=settings.conversation_answer_excerpt_chars,
        ),
```

- [ ] **Step 2: 修改 API 传入 context chat client**

在 `backend/app/api/qa.py` 的 `get_qa_answerer()` 中，创建：

```python
            context_chat_client = SiliconFlowChatClient(
                client=llm_http,
                api_key=settings.llm_api_key,
                model=settings.qa_intent_model,
            )
```

调用 `build_qa_dependencies(...)` 时增加：

```python
                        context_chat_client=context_chat_client,
```

调用 `answer_question(...)` 时增加：

```python
                    history_turns=settings.conversation_history_turns,
                    context_max_chars=settings.conversation_context_max_chars,
                    answer_excerpt_chars=settings.conversation_answer_excerpt_chars,
```

- [ ] **Step 3: 更新 endpoint fake response 测试**

在 `backend/tests/test_qa_api.py` 的 endpoint fake response 中加入：

```python
session_id="11111111-1111-1111-1111-111111111111",
```

- [ ] **Step 4: 运行 API 测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_qa_api.py -v
```

Expected: PASS。

---

### Task 9: 增加多轮 smoke 脚本

**Files:**
- Create: `backend/scripts/smoke_multiturn_qa.py`
- Modify: `backend/tests/test_qa_api.py`

- [ ] **Step 1: 写导入安全测试**

在 `backend/tests/test_qa_api.py` 增加：

```python
def test_smoke_multiturn_script_imports_safely_without_executing_main():
    import backend.scripts.smoke_multiturn_qa as smoke_script

    assert hasattr(smoke_script, "main")
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_qa_api.py::test_smoke_multiturn_script_imports_safely_without_executing_main -v
```

Expected: FAIL，因为脚本不存在。

- [ ] **Step 3: 创建 smoke 脚本**

创建 `backend/scripts/smoke_multiturn_qa.py`：

```python
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.scripts_import import run_smoke


async def main() -> None:
    await run_smoke()


if __name__ == "__main__":
    asyncio.run(main())
```

同时创建 `backend/app/scripts_import.py`：

```python
from __future__ import annotations

from app.core.config import settings
from app.scripts_runtime import ask_once


async def run_smoke() -> None:
    first = await ask_once("逆变器绝缘阻抗低怎么排查？", session_id=None)
    print("first answer_type =", first.answer_type)
    print("first session_id =", first.session_id)
    print("first references =", len(first.references))

    second = await ask_once("那下雨天才出现呢？", session_id=first.session_id)
    print("second answer_type =", second.answer_type)
    print("second session_id =", second.session_id)
    print("second standalone_question =", second.decision.get("standalone_question"))
    print("second used_history =", second.decision.get("used_history"))

    if first.session_id != second.session_id:
        raise SystemExit("second turn did not reuse session_id")
    if not second.decision.get("standalone_question"):
        raise SystemExit("second turn did not produce standalone_question")
```

创建 `backend/app/scripts_runtime.py`：

```python
from __future__ import annotations

import httpx

from app.core.config import settings
from app.db.session import SessionLocal
from app.schemas.qa import QaAskResponse
from app.services.qa_dependencies import build_qa_dependencies
from app.services.qa_service import answer_question
from app.services.siliconflow import (
    SiliconFlowChatClient,
    SiliconFlowEmbeddingClient,
    SiliconFlowRerankClient,
)


async def ask_once(question: str, session_id: str | None) -> QaAskResponse:
    timeout = httpx.Timeout(settings.model_api_timeout_seconds)
    async with (
        httpx.AsyncClient(base_url=settings.llm_base_url, timeout=timeout) as llm_http,
        httpx.AsyncClient(base_url=settings.embedding_base_url, timeout=timeout) as embedding_http,
        httpx.AsyncClient(base_url=settings.rerank_base_url, timeout=timeout) as rerank_http,
    ):
        intent_chat_client = SiliconFlowChatClient(llm_http, settings.llm_api_key, settings.qa_intent_model)
        answer_chat_client = SiliconFlowChatClient(llm_http, settings.llm_api_key, settings.qa_chat_model)
        context_chat_client = SiliconFlowChatClient(llm_http, settings.llm_api_key, settings.qa_intent_model)
        embedding_client = SiliconFlowEmbeddingClient(
            client=embedding_http,
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )
        rerank_client = (
            SiliconFlowRerankClient(
                client=rerank_http,
                api_key=settings.rerank_api_key,
                model=settings.rerank_model,
            )
            if settings.rerank_enabled
            else None
        )

        with SessionLocal() as session:
            return await answer_question(
                session=session,
                question=question,
                session_id=session_id,
                dependencies=build_qa_dependencies(
                    session=session,
                    intent_chat_client=intent_chat_client,
                    answer_chat_client=answer_chat_client,
                    context_chat_client=context_chat_client,
                    embedding_client=embedding_client,
                    rerank_client=rerank_client,
                ),
                min_rerank_score=settings.qa_rerank_min_score,
                strong_rerank_score=settings.qa_rerank_strong_score,
                reference_top_k=settings.qa_reference_top_k,
                history_turns=settings.conversation_history_turns,
                context_max_chars=settings.conversation_context_max_chars,
                answer_excerpt_chars=settings.conversation_answer_excerpt_chars,
            )
```

- [ ] **Step 4: 运行导入测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_qa_api.py::test_smoke_multiturn_script_imports_safely_without_executing_main -v
```

Expected: PASS。

- [ ] **Step 5: 手动 live smoke test**

在 `backend` 目录执行：

```powershell
python.exe -X utf8 scripts\smoke_multiturn_qa.py
```

Expected:

- 第一轮 `answer_type = rag`
- 第二轮复用同一个 `session_id`
- 第二轮 `decision.standalone_question` 非空
- 第二轮 `decision.used_history` 通常为 `true`

---

### Task 10: 文档和最终验证

**Files:**
- Modify: `docs/RAG问答接口闭环流程说明.md`
- Create: `docs/multi-turn-qa-verification.md`

- [ ] **Step 1: 创建验证文档**

创建 `docs/multi-turn-qa-verification.md`：

```markdown
# 多轮 RAG 问答验证记录

## 目标

验证多轮会话第一版闭环：

1. 第一轮不传 `session_id`，后端创建 session。
2. 响应返回 `session_id`。
3. 第二轮传入同一个 `session_id`。
4. 系统使用会话摘要和最近 10 轮压缩历史生成 `standalone_question`。
5. 当前轮重新检索知识库。
6. 当前轮答案只基于当前轮证据。

## 验证命令

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests -v
```

```powershell
cd D:\桌面\文件\operation_project\backend
python.exe -X utf8 scripts\smoke_multiturn_qa.py
```

## 期望结果

- 单元测试全部通过。
- 第一轮返回 `answer_type = rag`。
- 第一轮返回非空 `session_id`。
- 第二轮返回相同 `session_id`。
- 第二轮 `decision.standalone_question` 非空。
- 第二轮 `decision.used_history` 为 `true` 或在模型判断当前问题完整时为 `false`。
- RAG 答案仍然返回当前轮 `references`。

## 注意事项

- 历史上下文只用于改写问题。
- 历史上下文不作为答案事实来源。
- `references` 只来自当前轮检索。
- 如果模型 API 超时，可调大 `.env` 中的 `MODEL_API_TIMEOUT_SECONDS`。
```

- [ ] **Step 2: 更新流程说明文档**

在 `docs/RAG问答接口闭环流程说明.md` 增加章节：

```markdown
## 多轮会话上下文规则

多轮会话采用以下原则：

```text
session_summary + 最近 10 轮压缩历史 + 当前问题
        ↓
生成 standalone_question
        ↓
当前轮重新检索知识库
        ↓
只基于当前轮证据回答
```

历史上下文只负责理解用户追问，不作为最终答案事实来源。
```

- [ ] **Step 3: 运行全量测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests -v
```

Expected: PASS。

- [ ] **Step 4: 手动验证**

```powershell
cd D:\桌面\文件\operation_project\backend
python.exe -X utf8 scripts\smoke_multiturn_qa.py
```

Expected: PASS，输出两轮 session 信息。

---

## 补充小计划

用户确认需要一并纳入的 5 个小计划：

1. Prompt 独立出来。
2. 证据过滤规则。
3. 统一异常处理策略。
4. 小型后端自测脚本。
5. 整理 `.env.example` 和本地 `.env`。

其中：

- Prompt 独立出来已经由 **Task 2: 将 Prompt 集中到独立模块** 覆盖。
- 多轮自测脚本已经由 **Task 9: 增加多轮 smoke 脚本** 覆盖。
- 下面补充单轮 smoke、证据过滤、异常处理和 `.env` 整理任务。

---

### Task 11: 增加证据过滤规则

**Files:**
- Create: `backend/app/services/evidence_filtering.py`
- Create: `backend/tests/test_evidence_filtering.py`
- Modify: `backend/app/services/qa_service.py`
- Test: `backend/tests/test_evidence_filtering.py`
- Test: `backend/tests/test_qa_service.py`

- [ ] **Step 1: 写证据过滤测试**

创建 `backend/tests/test_evidence_filtering.py`：

```python
from types import SimpleNamespace

from app.services.evidence_filtering import filter_evidence_for_answer


def make_evidence(score):
    return SimpleNamespace(rerank_score=score, clean_text=f"score={score}")


def test_filter_evidence_for_answer_keeps_scores_at_or_above_threshold():
    evidence = [make_evidence(0.86), make_evidence(0.2), make_evidence(0.19), make_evidence(None)]

    filtered = filter_evidence_for_answer(evidence, min_rerank_score=0.2, max_items=5)

    assert [item.rerank_score for item in filtered] == [0.86, 0.2]


def test_filter_evidence_for_answer_respects_max_items():
    evidence = [make_evidence(0.9), make_evidence(0.8), make_evidence(0.7)]

    filtered = filter_evidence_for_answer(evidence, min_rerank_score=0.2, max_items=2)

    assert [item.rerank_score for item in filtered] == [0.9, 0.8]


def test_filter_evidence_for_answer_returns_empty_when_all_scores_are_weak():
    evidence = [make_evidence(0.1), make_evidence(None)]

    filtered = filter_evidence_for_answer(evidence, min_rerank_score=0.2, max_items=5)

    assert filtered == []
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_evidence_filtering.py -v
```

Expected: FAIL，因为模块不存在。

- [ ] **Step 3: 实现证据过滤模块**

创建 `backend/app/services/evidence_filtering.py`：

```python
from __future__ import annotations


def filter_evidence_for_answer(
    evidence: list[object],
    min_rerank_score: float,
    max_items: int,
) -> list[object]:
    if max_items <= 0:
        return []

    filtered: list[object] = []
    for item in evidence:
        score = getattr(item, "rerank_score", None)
        if score is None:
            continue
        if float(score) < min_rerank_score:
            continue
        filtered.append(item)
        if len(filtered) >= max_items:
            break

    return filtered
```

- [ ] **Step 4: 在 QA service 中使用过滤后的证据生成答案**

在 `backend/app/services/qa_service.py` 导入：

```python
from app.services.evidence_filtering import filter_evidence_for_answer
```

将 RAG 路线中的：

```python
    evidence_for_answer = evidence[:reference_top_k]
```

改为：

```python
    evidence_for_response = evidence[:reference_top_k]
    evidence_for_answer = filter_evidence_for_answer(
        evidence=evidence_for_response,
        min_rerank_score=min_rerank_score,
        max_items=reference_top_k,
    )
    if not evidence_for_answer:
        answer = "当前知识库没有找到足够相关的依据，暂时无法可靠回答该问题。"
        record = _add_record(
            session=session,
            qa_session=qa_session,
            trace_id=trace_id,
            question=question,
            understanding=understanding,
            answer=answer,
            answer_type=AnswerType.refused,
            confidence=top_score,
            latency_ms=_latency_ms(start),
            decision_extra={
                "route": "refused",
                "used_knowledge_base": True,
                "refusal_reason": "no_evidence_after_filtering",
                "top1_rerank_score": top_score,
                "threshold": min_rerank_score,
                "evidence_for_answer_count": 0,
            },
        )
        _add_unanswered(
            session=session,
            qa_session=qa_session,
            record=record,
            question=question,
            understanding=understanding,
            reason="no_evidence_after_filtering",
        )
        session.commit()
        return _response_from_record(record, understanding.intent.value, [])
```

并将后续 `_add_references(...)` 仍使用 `evidence_for_response`，生成答案使用 `evidence_for_answer`：

```python
    answer = await dependencies.answer_client.generate_rag(
        question=understanding.normalized_question,
        evidence=evidence_for_answer,
        cautious=cautious,
    )
    references = _add_references(session, record, evidence_for_response)
```

在 RAG `decision_extra` 中增加：

```python
            "evidence_for_answer_count": len(evidence_for_answer),
            "reference_count": len(evidence_for_response),
```

- [ ] **Step 5: 增加 QA service 测试**

在 `backend/tests/test_qa_service.py` 增加：

```python
@pytest.mark.asyncio
async def test_answer_question_filters_weak_evidence_before_answer_generation():
    session = FakeSession()
    evidence = [
        make_evidence(score=0.8)[0],
        make_evidence(score=0.1)[0],
    ]
    dependencies = make_dependencies(make_understanding(), evidence)

    response = await answer_question(
        session=session,
        question="逆变器绝缘阻抗低怎么排查？",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    rag_call = dependencies.answer_client.rag_calls[0]
    assert len(rag_call["evidence"]) == 1
    assert rag_call["evidence"][0].rerank_score == 0.8
    assert len(response.references) == 2
    assert response.decision["evidence_for_answer_count"] == 1
```

- [ ] **Step 6: 运行测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_evidence_filtering.py backend\tests\test_qa_service.py -v
```

Expected: PASS。

---

### Task 12: 增加统一异常处理策略

**Files:**
- Create: `backend/app/services/qa_error_handling.py`
- Create: `backend/tests/test_qa_error_handling.py`
- Modify: `backend/app/services/qa_service.py`
- Test: `backend/tests/test_qa_error_handling.py`
- Test: `backend/tests/test_qa_service.py`

- [ ] **Step 1: 写异常分类测试**

创建 `backend/tests/test_qa_error_handling.py`：

```python
import httpx

from app.services.qa_error_handling import classify_qa_exception


def test_classify_timeout_exception():
    result = classify_qa_exception(httpx.ReadTimeout("timeout"))

    assert result.reason == "model_timeout"
    assert "超时" in result.user_message
    assert result.should_record_unanswered is True


def test_classify_http_status_exception():
    request = httpx.Request("POST", "https://api.example.test/v1/chat/completions")
    response = httpx.Response(429, request=request)
    exc = httpx.HTTPStatusError("too many requests", request=request, response=response)

    result = classify_qa_exception(exc)

    assert result.reason == "model_http_error"
    assert result.status_code == 429
    assert result.should_record_unanswered is True


def test_classify_unknown_exception():
    result = classify_qa_exception(ValueError("bad payload"))

    assert result.reason == "qa_internal_error"
    assert result.status_code is None
    assert result.should_record_unanswered is True
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_qa_error_handling.py -v
```

Expected: FAIL，因为模块不存在。

- [ ] **Step 3: 实现异常分类模块**

创建 `backend/app/services/qa_error_handling.py`：

```python
from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class QaExceptionDecision:
    reason: str
    user_message: str
    status_code: int | None
    should_record_unanswered: bool


def classify_qa_exception(exc: Exception) -> QaExceptionDecision:
    if isinstance(exc, httpx.TimeoutException):
        return QaExceptionDecision(
            reason="model_timeout",
            user_message="模型服务请求超时，当前无法可靠生成答案，请稍后重试。",
            status_code=None,
            should_record_unanswered=True,
        )

    if isinstance(exc, httpx.HTTPStatusError):
        return QaExceptionDecision(
            reason="model_http_error",
            user_message="模型服务暂时不可用，当前无法可靠生成答案，请稍后重试。",
            status_code=exc.response.status_code,
            should_record_unanswered=True,
        )

    return QaExceptionDecision(
        reason="qa_internal_error",
        user_message="问答服务处理异常，当前无法可靠生成答案。",
        status_code=None,
        should_record_unanswered=True,
    )
```

- [ ] **Step 4: 在 QA service 中兜底异常**

在 `backend/app/services/qa_service.py` 导入：

```python
from app.services.qa_error_handling import classify_qa_exception
```

在 `answer_question(...)` 中保留现有业务逻辑，但将模型调用和检索调用的主流程包进内部 helper。推荐实现方式：

```python
async def answer_question(...):
    start = time.perf_counter()
    trace_id = uuid.uuid4().hex
    qa_session = _get_or_create_session(session, session_id)
    try:
        return await _answer_question_inner(
            session=session,
            qa_session=qa_session,
            question=question,
            trace_id=trace_id,
            start=start,
            dependencies=dependencies,
            min_rerank_score=min_rerank_score,
            strong_rerank_score=strong_rerank_score,
            reference_top_k=reference_top_k,
            session_id=session_id,
            history_turns=history_turns,
            context_max_chars=context_max_chars,
            answer_excerpt_chars=answer_excerpt_chars,
        )
    except Exception as exc:
        session.rollback()
        decision = classify_qa_exception(exc)
        fallback_understanding = QueryUnderstandingResult(
            intent=Intent.out_of_scope,
            confidence=0.0,
            should_use_knowledge_base=False,
            normalized_question=question,
            search_query="",
            refusal_reason=decision.reason,
            reason=decision.reason,
        )
        record = _add_record(
            session=session,
            qa_session=qa_session,
            trace_id=trace_id,
            question=question,
            understanding=fallback_understanding,
            answer=decision.user_message,
            answer_type=AnswerType.refused,
            confidence=None,
            latency_ms=_latency_ms(start),
            decision_extra={
                "route": "refused",
                "used_knowledge_base": False,
                "refusal_reason": decision.reason,
                "error_status_code": decision.status_code,
            },
        )
        _add_unanswered(
            session=session,
            qa_session=qa_session,
            record=record,
            question=question,
            understanding=fallback_understanding,
            reason=decision.reason,
        )
        session.commit()
        return _response_from_record(record, fallback_understanding.intent.value, [])
```

然后把原来的 `answer_question` 主体移动到 `_answer_question_inner(...)`。

- [ ] **Step 5: 增加 QA service 异常测试**

在 `backend/tests/test_qa_service.py` 增加：

```python
class FailingAnswerClient(FakeAnswerClient):
    async def generate_rag(self, question, evidence, cautious):
        raise RuntimeError("chat failed")


@pytest.mark.asyncio
async def test_answer_question_returns_structured_refusal_when_answer_generation_fails():
    session = FakeSession()
    dependencies = QaDependencies(
        understanding_client=FakeUnderstandingClient(make_understanding()),
        retriever=FakeRetriever(make_evidence(score=0.8)),
        answer_client=FailingAnswerClient(),
    )

    response = await answer_question(
        session=session,
        question="逆变器绝缘阻抗低怎么排查？",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    assert response.answer_type == "refused"
    assert response.decision["refusal_reason"] == "qa_internal_error"
    assert response.references == []
    assert get_added(session, QaUnanswered)
    assert session.rollbacks == 1
    assert session.commits == 1
```

- [ ] **Step 6: 运行测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_qa_error_handling.py backend\tests\test_qa_service.py -v
```

Expected: PASS。

---

### Task 13: 增加单轮 QA smoke 脚本

**Files:**
- Create: `backend/scripts/smoke_qa.py`
- Modify: `backend/tests/test_qa_api.py`
- Test: `backend/tests/test_qa_api.py`

- [ ] **Step 1: 写导入安全测试**

在 `backend/tests/test_qa_api.py` 增加：

```python
def test_smoke_qa_script_imports_safely_without_executing_main():
    import backend.scripts.smoke_qa as smoke_script

    assert hasattr(smoke_script, "main")
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_qa_api.py::test_smoke_qa_script_imports_safely_without_executing_main -v
```

Expected: FAIL，因为脚本不存在。

- [ ] **Step 3: 创建 smoke 脚本**

创建 `backend/scripts/smoke_qa.py`：

```python
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.scripts_runtime import ask_once


async def main() -> None:
    cases = [
        ("rag", "逆变器绝缘阻抗低怎么排查？"),
        ("general_or_rag", "什么是无功功率？"),
        ("refused", "今天上海天气怎么样？"),
    ]

    for expected, question in cases:
        response = await ask_once(question, session_id=None)
        print("question =", question)
        print("answer_type =", response.answer_type)
        print("intent =", response.intent)
        print("references =", len(response.references))
        print("session_id =", response.session_id)
        print("---")

        if expected == "rag" and response.answer_type != "rag":
            raise SystemExit("RAG smoke case did not return rag")
        if expected == "refused" and response.answer_type != "refused":
            raise SystemExit("Realtime smoke case did not return refused")
        if expected == "general_or_rag" and response.answer_type not in {"general_llm", "rag"}:
            raise SystemExit("General smoke case returned unexpected answer_type")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: 运行导入测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_qa_api.py::test_smoke_qa_script_imports_safely_without_executing_main -v
```

Expected: PASS。

- [ ] **Step 5: 手动 live smoke test**

在 `backend` 目录执行：

```powershell
python.exe -X utf8 scripts\smoke_qa.py
```

Expected:

- RAG 问题返回 `answer_type = rag`
- 通用解释问题返回 `general_llm` 或 `rag`
- 实时外部问题返回 `answer_type = refused`

---

### Task 14: 整理 `.env.example` 和本地 `.env`

**Files:**
- Create: `backend/scripts/normalize_env_file.py`
- Modify: `.env.example`
- Optionally modify: `.env`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: 写脚本导入安全测试**

在 `backend/tests/test_config.py` 增加：

```python
def test_normalize_env_file_script_imports_safely_without_executing_main():
    import backend.scripts.normalize_env_file as normalize_script

    assert hasattr(normalize_script, "main")
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_config.py::test_normalize_env_file_script_imports_safely_without_executing_main -v
```

Expected: FAIL，因为脚本不存在。

- [ ] **Step 3: 创建 `.env` 整理脚本**

创建 `backend/scripts/normalize_env_file.py`。脚本必须满足：

1. 读取 `.env.example` 和 `.env`。
2. 按固定分组输出。
3. 保留 `.env` 中已有真实值。
4. 不在终端打印真实 API Key。
5. 文件保持 UTF-8。

核心结构如下：

```python
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ORDERED_SECTIONS = [
    ("应用基础配置", ["APP_ENV", "APP_PORT", "APP_NAME", "MODEL_API_TIMEOUT_SECONDS"]),
    ("PostgreSQL 本地数据库配置", ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]),
    ("Redis 预留配置", ["REDIS_HOST", "REDIS_PORT", "REDIS_DB"]),
    ("SiliconFlow Chat 模型配置", ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"]),
    ("SiliconFlow Embedding 模型配置", ["EMBEDDING_BASE_URL", "EMBEDDING_API_KEY", "EMBEDDING_MODEL", "EMBEDDING_DIMENSION"]),
    ("SiliconFlow Rerank 模型配置", ["RERANK_BASE_URL", "RERANK_API_KEY", "RERANK_MODEL", "RERANK_ENABLED", "RERANK_TOP_N"]),
    ("检索参数", ["RETRIEVAL_VECTOR_TOP_K", "RETRIEVAL_KEYWORD_TOP_K", "RETRIEVAL_RRF_TOP_K", "RETRIEVAL_FINAL_TOP_K", "RETRIEVAL_RRF_K"]),
    ("QA 阈值配置", ["QA_RERANK_MIN_SCORE", "QA_RERANK_STRONG_SCORE", "QA_MAX_QUESTION_CHARS", "QA_REFERENCE_TOP_K", "QA_INTENT_MODEL", "QA_CHAT_MODEL"]),
    ("多轮会话配置", ["CONVERSATION_HISTORY_TURNS", "CONVERSATION_SUMMARY_AFTER_TURNS", "CONVERSATION_SUMMARY_REFRESH_TURNS", "CONVERSATION_CONTEXT_MAX_CHARS", "CONVERSATION_ANSWER_EXCERPT_CHARS"]),
]

DEFAULTS = {
    "APP_ENV": "dev",
    "APP_PORT": "8000",
    "APP_NAME": "PV QA Assistant",
    "MODEL_API_TIMEOUT_SECONDS": "300",
    "DB_HOST": "127.0.0.1",
    "DB_PORT": "5432",
    "DB_NAME": "operation_pv",
    "DB_USER": "postgres",
    "DB_PASSWORD": "your_password",
    "REDIS_HOST": "127.0.0.1",
    "REDIS_PORT": "6379",
    "REDIS_DB": "0",
    "LLM_BASE_URL": "https://api.siliconflow.cn/v1",
    "LLM_API_KEY": "your_api_key",
    "LLM_MODEL": "deepseek-ai/DeepSeek-V4-Flash",
    "EMBEDDING_BASE_URL": "https://api.siliconflow.cn/v1",
    "EMBEDDING_API_KEY": "your_api_key",
    "EMBEDDING_MODEL": "BAAI/bge-m3",
    "EMBEDDING_DIMENSION": "1024",
    "RERANK_BASE_URL": "https://api.siliconflow.cn/v1",
    "RERANK_API_KEY": "your_api_key",
    "RERANK_MODEL": "BAAI/bge-reranker-v2-m3",
    "RERANK_ENABLED": "true",
    "RERANK_TOP_N": "5",
    "RETRIEVAL_VECTOR_TOP_K": "20",
    "RETRIEVAL_KEYWORD_TOP_K": "20",
    "RETRIEVAL_RRF_TOP_K": "20",
    "RETRIEVAL_FINAL_TOP_K": "5",
    "RETRIEVAL_RRF_K": "60",
    "QA_RERANK_MIN_SCORE": "0.2",
    "QA_RERANK_STRONG_SCORE": "0.6",
    "QA_MAX_QUESTION_CHARS": "500",
    "QA_REFERENCE_TOP_K": "5",
    "QA_INTENT_MODEL": "deepseek-ai/DeepSeek-V4-Flash",
    "QA_CHAT_MODEL": "deepseek-ai/DeepSeek-V4-Flash",
    "CONVERSATION_HISTORY_TURNS": "10",
    "CONVERSATION_SUMMARY_AFTER_TURNS": "10",
    "CONVERSATION_SUMMARY_REFRESH_TURNS": "5",
    "CONVERSATION_CONTEXT_MAX_CHARS": "8000",
    "CONVERSATION_ANSWER_EXCERPT_CHARS": "500",
}


def parse_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def render_env(values: dict[str, str]) -> str:
    parts: list[str] = []
    used: set[str] = set()
    for title, keys in ORDERED_SECTIONS:
        parts.append(f"# {title}")
        for key in keys:
            value = values.get(key, DEFAULTS.get(key, ""))
            parts.append(f"{key}={value}")
            used.add(key)
        parts.append("")

    extras = sorted(key for key in values if key not in used)
    if extras:
        parts.append("# 其他自定义配置")
        for key in extras:
            parts.append(f"{key}={values[key]}")
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"


def normalize_file(path: Path) -> None:
    values = {**DEFAULTS, **parse_env(path)}
    path.write_text(render_env(values), encoding="utf-8")


def main() -> None:
    normalize_file(PROJECT_ROOT / ".env.example")
    print("normalized .env.example")
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        normalize_file(env_path)
        print("normalized .env without printing secret values")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行导入测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_config.py::test_normalize_env_file_script_imports_safely_without_executing_main -v
```

Expected: PASS。

- [ ] **Step 5: 执行整理脚本**

执行前确认：该脚本会修改 `.env.example` 和本地 `.env`，但不会打印真实值。

```powershell
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\normalize_env_file.py
```

Expected:

- `.env.example` 被整理为中文注释分组。
- `.env` 如果存在，也被整理为同样结构，并保留原真实值。
- 终端不打印真实 API Key。

---

## Self-Review

**Spec coverage:** 本计划覆盖了用户确认的核心设计：LLM 压缩 + 代码字段约束、最近 10 轮历史、10 轮后 summary、`session_summary + 最近 10 轮 + 当前问题 -> standalone_question -> 当前轮检索 -> 只基于当前轮证据回答`。也覆盖了 `session_id` 返回、历史不进入答案生成、当前轮 references 独立、summary 存储到 `qa_session.session_metadata`、Prompt 独立、证据过滤、统一异常处理、单轮和多轮 smoke 脚本、`.env.example` 与本地 `.env` 格式整理。

**Placeholder scan:** 本计划没有使用 TBD、TODO、implement later 或“自行补充测试”。每个任务都有明确文件、测试、命令和期望结果。

**Type consistency:** `ConversationContext`、`StandaloneQuestionResult`、`QaDependencies.context_rewriter`、`QaDependencies.session_summarizer`、`QaAskResponse.session_id` 在后续任务中的名称保持一致。`conversation_summary` 和 `conversation_summary_turn_count` 统一放在 `qa_session.session_metadata`。

**Important guardrail:** 执行时不得修改真实 `.env` 中的 API Key，不得在日志或回复中打印真实 API Key。Live smoke test 会调用 SiliconFlow API，执行前必须确认用户授权。
