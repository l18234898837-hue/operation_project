# RAG Answer Quality Follow-Up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve multi-turn RAG answer quality for photovoltaic O&M conversations by fixing follow-up detection, preserving context for continuation questions, reducing noisy evidence, and making answers shorter and more field-operable.

**Architecture:** Keep the existing QA pipeline shape: conversation context -> rewrite -> intent/routing -> retrieval -> evidence filtering -> answer generation. The changes should be narrow: expand centralized routing terms, make follow-up rewrites happen before hard routing when history exists, add a history-based consolidation path for summary-style follow-ups, tighten evidence selection, and adjust prompts for concise operational answers.

**Tech Stack:** FastAPI service layer, Python 3.12, pytest, SQLAlchemy model fakes in tests, existing RAG services under `backend/app/services`.

---

## File Structure

- Modify: `backend/app/services/routing_terms.py`
  - Centralize additional follow-up and consolidation terms.
- Modify: `backend/app/services/conversation_rewrite.py`
  - Improve deterministic follow-up detection and self-contained-question checks.
- Modify: `backend/app/services/qa_service.py`
  - Ensure context rewrite is not bypassed by hard rules when a question is likely a follow-up.
  - Add a history-summary route for “make it understandable / summarize as advice” requests.
- Modify: `backend/app/prompts/qa_prompts.py`
  - Make RAG answers shorter and more operational by default.
- Modify: `backend/app/services/evidence_filtering.py`
  - Tighten generation evidence selection for high-confidence cases to reduce unrelated evidence noise.
- Test: `backend/tests/test_conversation_rewrite.py`
- Test: `backend/tests/test_qa_service.py`
- Test: `backend/tests/test_qa_prompts.py`
- Test: `backend/tests/test_evidence_filtering.py`

---

### Task 1: Expand Follow-Up Vocabulary

**Files:**
- Modify: `backend/app/services/routing_terms.py`
- Test: `backend/tests/test_conversation_rewrite.py`

- [ ] **Step 1: Write failing tests for observed follow-up phrases**

Add these tests to `backend/tests/test_conversation_rewrite.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_conversation_rewrite.py::test_rewrite_standalone_question_uses_history_for_operational_followups -q
```

Expected: FAIL because some phrases currently return `reason="no_follow_up_signal"` and do not call the rewriter.

- [ ] **Step 3: Add centralized terms**

In `backend/app/services/routing_terms.py`, extend `REWRITE_FOLLOW_UP_TERMS` with:

```python
REWRITE_FOLLOW_UP_TERMS = (
    *FOLLOW_UP_TERMS,
    "那个",
    "那",
    "那么",
    "呢",
    "继续",
    "上一条",
    "上一轮",
    "上一个",
    "前一个",
    "告警还在",
    "下一步",
    "处理建议",
    "现场处理",
    "运维人员能看懂",
    "能看懂",
    "整理成",
    "最后怎么处理",
)
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_conversation_rewrite.py -q
```

Expected: all tests in this file pass.

---

### Task 2: Do Not Let Hard Rules Bypass History Follow-Ups

**Files:**
- Modify: `backend/app/services/qa_service.py`
- Test: `backend/tests/test_qa_service.py`

- [ ] **Step 1: Write failing service test for “告警还在”**

Add this test to `backend/tests/test_qa_service.py`:

```python
@pytest.mark.asyncio
async def test_answer_question_rewrites_followup_before_hard_rule_routing():
    session = FakeSession()
    qa_session_id = uuid.uuid4()
    existing_session = QaSession(id=qa_session_id)
    session.add(existing_session)
    previous = make_existing_record(
        question="逆变器报“绝缘阻抗低”，一般应该怎么排查？",
        answer="重点检查直流线缆破皮、接头进水和绝缘电阻。",
    )
    previous.session_id = qa_session_id
    session.add(previous)
    rewrite_result = StandaloneQuestionResult(
        standalone_question="逆变器绝缘阻抗低告警下，组串电压正常但告警仍在，下一步如何处理？",
        is_follow_up=True,
        used_history=True,
        reason="补全告警上下文",
    )
    dependencies = QaDependencies(
        understanding_client=FakeUnderstandingClient(make_understanding()),
        retriever=FakeRetriever(make_evidence(score=0.8)),
        answer_client=FakeAnswerClient(),
        context_rewriter=FakeContextRewriter(rewrite_result),
    )

    response = await answer_question(
        session=session,
        session_id=qa_session_id,
        question="如果组串电压看起来正常，但告警还在，下一步怎么办？",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    assert response.answer_type == "rag"
    assert dependencies.retriever.calls == [
        "逆变器绝缘阻抗低告警下，组串电压正常但告警仍在，下一步如何处理？"
    ]
    assert response.decision["used_history"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_qa_service.py::test_answer_question_rewrites_followup_before_hard_rule_routing -q
```

Expected: FAIL because hard-rule routing can currently skip context rewrite for some domain-looking follow-ups.

- [ ] **Step 3: Refactor `answer_question` flow**

In `backend/app/services/qa_service.py`, change `_answer_question_inner` so the initial hard-rule shortcut only handles:

```python
hard_rule_understanding = apply_intent_hard_rules(question)
if hard_rule_understanding is not None and hard_rule_understanding.intent in {
    Intent.chitchat,
    Intent.invalid_input,
    Intent.realtime_external,
}:
    ...
```

Then always build history context before final knowledge-base hard routing when the question is not an obvious chitchat/invalid/realtime case. After rewrite, run:

```python
question_for_understanding = rewrite_result.standalone_question
hard_rule_understanding = apply_intent_hard_rules(question_for_understanding)
if hard_rule_understanding is not None:
    understanding = hard_rule_understanding
else:
    understanding = await dependencies.understanding_client.understand(question_for_understanding)
```

Keep `rewrite_metadata = _rewrite_metadata(question, rewrite_result)` so the response decision records `original_question`, `standalone_question`, `is_follow_up`, and `used_history`.

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_qa_service.py backend\tests\test_query_understanding.py -q
```

Expected: pass.

---

### Task 3: Add History-Based Consolidation For Summary-Style Follow-Ups

**Files:**
- Modify: `backend/app/services/routing_terms.py`
- Modify: `backend/app/services/conversation_rewrite.py`
- Modify: `backend/app/services/qa_service.py`
- Test: `backend/tests/test_conversation_rewrite.py`
- Test: `backend/tests/test_qa_service.py`

- [ ] **Step 1: Write failing rewrite classification test**

Add to `backend/tests/test_conversation_rewrite.py`:

```python
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
```

- [ ] **Step 2: Add consolidation test in service layer**

Add to `backend/tests/test_qa_service.py`:

```python
@pytest.mark.asyncio
async def test_summary_style_followup_uses_rewritten_context_not_raw_query():
    session = FakeSession()
    qa_session_id = uuid.uuid4()
    existing_session = QaSession(id=qa_session_id)
    session.add(existing_session)
    previous = make_existing_record(
        question="这个告警会影响发电量吗？",
        answer="会，绝缘阻抗低会导致逆变器停机并造成发电量损失。",
    )
    previous.session_id = qa_session_id
    session.add(previous)
    rewrite_result = StandaloneQuestionResult(
        standalone_question="请把逆变器绝缘阻抗低告警的处理方法整理成运维人员能看懂的现场处理建议。",
        is_follow_up=True,
        used_history=True,
        reason="用户要求整理前文为现场建议",
    )
    dependencies = QaDependencies(
        understanding_client=FakeUnderstandingClient(make_understanding()),
        retriever=FakeRetriever(make_evidence(score=0.8)),
        answer_client=FakeAnswerClient(),
        context_rewriter=FakeContextRewriter(rewrite_result),
    )

    response = await answer_question(
        session=session,
        session_id=qa_session_id,
        question="能不能给我一个运维人员能看懂的处理建议？",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    assert response.answer_type == "rag"
    assert dependencies.retriever.calls == [
        "请把逆变器绝缘阻抗低告警的处理方法整理成运维人员能看懂的现场处理建议。"
    ]
```

- [ ] **Step 3: Add centralized consolidation terms**

In `backend/app/services/routing_terms.py`, add:

```python
CONSOLIDATION_FOLLOW_UP_TERMS = (
    "处理建议",
    "现场建议",
    "现场处理",
    "运维人员能看懂",
    "能看懂",
    "整理成",
    "总结一下",
    "给我一个",
)
```

Then include these in `REWRITE_FOLLOW_UP_TERMS`:

```python
REWRITE_FOLLOW_UP_TERMS = (
    *FOLLOW_UP_TERMS,
    *CONSOLIDATION_FOLLOW_UP_TERMS,
    ...
)
```

- [ ] **Step 4: Make rewrite prompt explicitly handle consolidation**

In `backend/app/prompts/qa_prompts.py`, update `build_standalone_question_messages` system prompt by adding:

```python
"如果当前问题是在要求“整理、总结、给出处理建议、给运维人员能看懂的说法”，"
"并且最近历史有明确故障或设备主题，必须把该主题补入 standalone_question。"
"例如：历史主题为逆变器绝缘阻抗低，当前问题为“能不能给我一个运维人员能看懂的处理建议”，"
"standalone_question 应改写为“请把逆变器绝缘阻抗低告警的处理方法整理成运维人员能看懂的现场处理建议”。"
```

- [ ] **Step 5: Run tests**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_conversation_rewrite.py backend\tests\test_qa_service.py backend\tests\test_qa_prompts.py -q
```

Expected: pass.

---

### Task 4: Reduce Evidence Noise For High-Confidence Questions

**Files:**
- Modify: `backend/app/services/evidence_filtering.py`
- Test: `backend/tests/test_evidence_filtering.py`

- [ ] **Step 1: Write failing test for high-confidence evidence selection**

Add to `backend/tests/test_evidence_filtering.py`:

```python
def test_high_confidence_single_dominant_evidence_limits_generation_noise():
    evidence = [
        SimpleNamespace(rerank_score=0.91),
        SimpleNamespace(rerank_score=0.44),
        SimpleNamespace(rerank_score=0.43),
        SimpleNamespace(rerank_score=0.31),
    ]

    policy = select_evidence_compression_policy(evidence)

    assert policy.max_items == 2
    assert policy.reason == "dominant_high_confidence_top2"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_evidence_filtering.py::test_high_confidence_single_dominant_evidence_limits_generation_noise -q
```

Expected: FAIL because the current policy may pass too many medium-low side evidences into generation.

- [ ] **Step 3: Implement dominant-evidence policy**

In `backend/app/services/evidence_filtering.py`, update `select_evidence_compression_policy` so:

```python
top_score = _score(evidence[0])
second_score = _score(evidence[1]) if len(evidence) > 1 else 0.0
if top_score >= 0.85 and top_score - second_score >= 0.25:
    return EvidenceCompressionPolicy(
        max_items=2,
        max_chars_per_item=700,
        reason="dominant_high_confidence_top2",
    )
```

Keep existing high/medium/low policies after this new branch.

- [ ] **Step 4: Run evidence filtering tests**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_evidence_filtering.py -q
```

Expected: pass.

---

### Task 5: Make RAG Answers Shorter And More Field-Operable

**Files:**
- Modify: `backend/app/prompts/qa_prompts.py`
- Test: `backend/tests/test_qa_prompts.py`

- [ ] **Step 1: Write failing prompt test**

Add to `backend/tests/test_qa_prompts.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_qa_prompts.py::test_rag_answer_prompt_prefers_concise_operational_structure -q
```

Expected: FAIL because current prompt does not constrain length/shape enough.

- [ ] **Step 3: Update RAG prompt**

In `backend/app/prompts/qa_prompts.py`, update the base `system_prompt` in `build_rag_answer_messages` to include:

```python
"回答默认控制在 6-10 条要点，除非用户明确要求详细展开。"
"优先输出现场可执行步骤，不要写成长报告。"
"推荐结构为：结论、排查步骤、处理建议、安全注意。"
"只有当问题涉及阈值、型号、故障码或标准参数且证据未提供时，才补充“当前知识库依据不足”的说明。"
```

- [ ] **Step 4: Run prompt tests**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_qa_prompts.py -q
```

Expected: pass.

---

### Task 6: End-To-End Regression For The Observed Conversation

**Files:**
- Modify: `backend/tests/test_qa_service.py`

- [ ] **Step 1: Add a compact multi-turn regression**

Add this test to `backend/tests/test_qa_service.py`:

```python
@pytest.mark.asyncio
async def test_observed_insulation_resistance_followup_sequence_keeps_context():
    session = FakeSession()
    qa_session_id = uuid.uuid4()
    existing_session = QaSession(id=qa_session_id)
    session.add(existing_session)
    first_record = make_existing_record(
        question="逆变器报“绝缘阻抗低”，一般应该怎么排查？",
        answer="重点检查直流线缆破皮、接头进水、绝缘电阻和安全隔离。",
    )
    first_record.session_id = qa_session_id
    session.add(first_record)

    dependencies = QaDependencies(
        understanding_client=FakeUnderstandingClient(make_understanding()),
        retriever=FakeRetriever(make_evidence(score=0.8)),
        answer_client=FakeAnswerClient(),
        context_rewriter=FakeContextRewriter(
            StandaloneQuestionResult(
                standalone_question="逆变器绝缘阻抗低告警下，组串电压正常但告警仍在，下一步如何处理？",
                is_follow_up=True,
                used_history=True,
                reason="补全告警上下文",
            )
        ),
    )

    response = await answer_question(
        session=session,
        session_id=qa_session_id,
        question="如果组串电压看起来正常，但告警还在，下一步怎么办？",
        dependencies=dependencies,
        min_rerank_score=0.2,
        strong_rerank_score=0.6,
        reference_top_k=5,
    )

    assert response.answer_type == "rag"
    assert response.decision["used_history"] is True
    assert "绝缘阻抗低" in response.decision["standalone_question"]
```

- [ ] **Step 2: Run regression**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_qa_service.py::test_observed_insulation_resistance_followup_sequence_keeps_context -q
```

Expected: pass after Tasks 1-3.

- [ ] **Step 3: Run all targeted tests**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_conversation_rewrite.py backend\tests\test_query_understanding.py backend\tests\test_qa_service.py backend\tests\test_qa_prompts.py backend\tests\test_evidence_filtering.py -q
```

Expected: pass.

---

## Manual Verification Checklist

Run the same user conversation in one session:

1. `逆变器报“绝缘阻抗低”，一般应该怎么排查？`
2. `如果这个告警是在雨后出现的，优先怀疑哪些位置？`
3. `刚才说的排查里，哪些步骤需要先停机或做好安全隔离？`
4. `如果组串电压看起来正常，但告警还在，下一步怎么办？`
5. `这个告警会影响发电量吗？`
6. `能不能给我一个运维人员能看懂的处理建议？`

Expected behavior:

- Questions 2-6 preserve the “逆变器绝缘阻抗低告警” topic in `standalone_question`.
- Question 4 does not retrieve unrelated “组串串联损失” as the primary basis.
- Question 6 does not retrieve “运维人员配置” as the primary basis.
- Answers are concise enough for field use.
- High-confidence first answer does not feed unrelated medium-score evidence into generation.

---

## Self-Review

- Spec coverage: The plan covers follow-up detection, hard-rule bypass, consolidation-style follow-ups, evidence noise, and answer length. Response speed is intentionally excluded.
- Placeholder scan: No unresolved placeholder markers remain.
- Type consistency: Tests use existing `QaDependencies`, `StandaloneQuestionResult`, `FakeSession`, `FakeRetriever`, and `make_evidence` patterns already present in the test suite.
