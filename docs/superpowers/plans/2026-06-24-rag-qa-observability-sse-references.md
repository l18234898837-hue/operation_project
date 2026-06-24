# RAG QA Observability, SSE, and Reference Filtering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为当前 RAG 问答系统增加可长期维护的耗时日志表、SSE 流式问答接口，以及“强相关证据入模/展示”的阈值策略。

**Architecture:** 保留现有 `qa_session / qa_record / qa_reference / qa_unanswered` 结构作为业务主表，新增 `qa_trace_step` 作为每轮问答的阶段耗时和模型调用日志表。SSE 接口复用现有 QA 编排逻辑，但以事件流方式向前端输出“理解中、检索中、生成中、答案片段、引用、完成”等状态；意图识别仍然保留，不因为历史追问而跳过。证据过滤分成“进入 chat 的证据”和“返回/展示的引用证据”两层配置。

**Tech Stack:** FastAPI, Server-Sent Events, SQLAlchemy 2.0, Alembic, PostgreSQL JSONB, Pydantic, httpx, pytest, SiliconFlow Chat/Embedding/Rerank API.

---

## 固定产品规则

1. 多轮会话中的每一个用户问题都必须写入 `qa_record`，不能只写第一轮。
2. 拒答、低置信、异常、通用回答、RAG 回答都必须有 `qa_record`。
3. 每一轮问答的关键耗时阶段写入 `qa_trace_step`，用于后续日志页面。
4. 意图识别不能因为“已有历史 + 追问”而跳过；用户可能在同一会话里问无关问题。
5. 多轮上下文仍只用于生成 `standalone_question`，最终回答仍只基于当前轮检索证据。
6. SSE 可以改善体感，但不承诺减少总耗时；目标是尽快返回状态事件和首字。
7. 不展示模型原始思考链；只展示系统状态、检索依据和简要决策。
8. 进入 chat 的证据必须满足入模阈值，展示引用也必须满足引用阈值。
9. 默认只展示强相关 Top 3，最多返回 Top 5 给前端折叠展示。
10. 本计划暂不做前端页面，只提供后端接口和命令行验证脚本。

## 当前项目事实

- QA API: `backend/app/api/qa.py`
- QA schema: `backend/app/schemas/qa.py`
- QA service: `backend/app/services/qa_service.py`
- Answer generation: `backend/app/services/answer_generation.py`
- SiliconFlow client: `backend/app/services/siliconflow.py`
- Config: `backend/app/core/config.py`
- RAG models: `backend/app/models/rag.py`
- Existing scripts:
  - `backend/scripts/ask_question.py`
  - `backend/scripts/chat_qa.py`
  - `backend/scripts/smoke_qa.py`
  - `backend/scripts/smoke_multiturn_qa.py`
- Current timing data exists in `qa_record.decision_metadata.timings_ms` but is not normalized into a trace table.
- Current reference behavior returns Top 5 references; displayed references are not yet filtered by a dedicated reference threshold.

## 文件结构

创建文件：

- `backend/app/services/qa_trace.py`
  - 封装 trace step 记录逻辑，避免在 `qa_service.py` 里散落数据库写入。
- `backend/app/services/qa_streaming.py`
  - 封装 SSE 事件类型、事件序列和流式问答入口。
- `backend/tests/test_qa_trace.py`
  - 测试 trace step 数据构造和写入。
- `backend/tests/test_qa_streaming.py`
  - 测试 SSE 事件顺序和安全导入。
- `backend/scripts/stream_chat_qa.py`
  - 命令行验证 SSE/流式输出效果。
- `backend/alembic/versions/20260624_0003_add_qa_trace_step.py`
  - 新增 `qa_trace_step` 表。

修改文件：

- `backend/app/models/rag.py`
  - 新增 `QaTraceStep` model 和 relationship。
- `backend/app/core/config.py`
  - 新增证据入模和引用展示配置。
- `.env.example`
  - 增加新增配置项中文说明。
- `backend/app/schemas/qa.py`
  - 增加引用可见性字段，必要时增加 SSE event schema。
- `backend/app/services/evidence_filtering.py`
  - 拆分“入模证据过滤”和“引用展示过滤”。
- `backend/app/services/qa_service.py`
  - 写入 `qa_trace_step`，返回过滤后的 references。
- `backend/app/services/answer_generation.py`
  - 增加更短回答的 prompt 约束，必要时增加 stream 版本。
- `backend/app/services/siliconflow.py`
  - 增加 chat streaming 方法。
- `backend/app/services/qa_dependencies.py`
  - 暴露支持 stream 的真实 answer client。
- `backend/app/api/qa.py`
  - 新增 `POST /api/qa/ask/stream` SSE endpoint。
- `backend/scripts/chat_qa.py`
  - 增加引用阈值后的显示兼容。
- `backend/tests/test_qa_service.py`
  - 覆盖 trace 写入和引用过滤。
- `backend/tests/test_qa_api.py`
  - 覆盖 SSE endpoint 安全行为。
- `backend/tests/test_config.py`
  - 覆盖新增配置。

不做：

- 前端页面。
- 日志后台 UI。
- WebSocket。
- 展示模型原始思考链。
- 跳过意图识别。
- 修改真实 `.env`。

---

### Task 1: 新增 QA Trace Step 数据表

**Files:**
- Modify: `backend/app/models/rag.py`
- Create: `backend/alembic/versions/20260624_0003_add_qa_trace_step.py`
- Test: `backend/tests/test_db_metadata.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_db_metadata.py` 增加：

```python
def test_qa_trace_step_table_is_registered():
    from app.db.base import Base

    table = Base.metadata.tables["qa_trace_step"]

    assert "qa_record_id" in table.c
    assert "trace_id" in table.c
    assert "step_name" in table.c
    assert "duration_ms" in table.c
    assert "status" in table.c
    assert "model_name" in table.c
    assert "metadata" in table.c
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 -m pytest backend\tests\test_db_metadata.py::test_qa_trace_step_table_is_registered -v
```

Expected: FAIL，原因是 `qa_trace_step` 尚未注册。

- [ ] **Step 3: 修改 SQLAlchemy model**

在 `backend/app/models/rag.py` 中新增：

```python
class QaTraceStep(TimestampMixin, Base):
    __tablename__ = "qa_trace_step"
    __table_args__ = (
        Index("ix_qa_trace_step_qa_record_id", "qa_record_id"),
        Index("ix_qa_trace_step_trace_id", "trace_id"),
        Index("ix_qa_trace_step_step_name", "step_name"),
        Index("ix_qa_trace_step_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    qa_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("qa_record.id", ondelete="CASCADE"),
    )
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    step_name: Mapped[str] = mapped_column(String(128), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="success")
    model_name: Mapped[str | None] = mapped_column(String(255))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    step_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB)

    record: Mapped[QaRecord | None] = relationship(back_populates="trace_steps")
```

并在 `QaRecord` 中增加：

```python
    trace_steps: Mapped[list[QaTraceStep]] = relationship(
        back_populates="record",
        cascade="all, delete-orphan",
    )
```

- [ ] **Step 4: 创建 Alembic migration**

创建 `backend/alembic/versions/20260624_0003_add_qa_trace_step.py`：

```python
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260624_0003"
down_revision = "20260622_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "qa_trace_step",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("qa_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("qa_record.id", ondelete="CASCADE")),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("step_name", sa.String(length=128), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="success"),
        sa.Column("model_name", sa.String(length=255)),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("error_message", sa.Text()),
        sa.Column("metadata", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_qa_trace_step_qa_record_id", "qa_trace_step", ["qa_record_id"])
    op.create_index("ix_qa_trace_step_trace_id", "qa_trace_step", ["trace_id"])
    op.create_index("ix_qa_trace_step_step_name", "qa_trace_step", ["step_name"])
    op.create_index("ix_qa_trace_step_status", "qa_trace_step", ["status"])


def downgrade() -> None:
    op.drop_index("ix_qa_trace_step_status", table_name="qa_trace_step")
    op.drop_index("ix_qa_trace_step_step_name", table_name="qa_trace_step")
    op.drop_index("ix_qa_trace_step_trace_id", table_name="qa_trace_step")
    op.drop_index("ix_qa_trace_step_qa_record_id", table_name="qa_trace_step")
    op.drop_table("qa_trace_step")
```

- [ ] **Step 5: 运行测试确认通过**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 -m pytest backend\tests\test_db_metadata.py -v
```

Expected: PASS。

---

### Task 2: 实现 Trace Step 写入服务

**Files:**
- Create: `backend/app/services/qa_trace.py`
- Modify: `backend/app/services/qa_service.py`
- Test: `backend/tests/test_qa_trace.py`
- Test: `backend/tests/test_qa_service.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_qa_trace.py`：

```python
import uuid

from app.models.rag import QaTraceStep
from app.services.qa_trace import QaTraceCollector, persist_trace_steps


class FakeSession:
    def __init__(self):
        self.added = []

    def add(self, item):
        self.added.append(item)


def test_trace_collector_records_success_step():
    collector = QaTraceCollector(trace_id="trace-1")

    collector.record_step(
        step_name="answer_generation",
        duration_ms=1234,
        status="success",
        model_name="deepseek-ai/DeepSeek-V4-Flash",
        metadata={"route": "rag"},
    )

    assert collector.steps[0].step_name == "answer_generation"
    assert collector.steps[0].duration_ms == 1234
    assert collector.steps[0].metadata == {"route": "rag"}


def test_persist_trace_steps_writes_models():
    session = FakeSession()
    record_id = uuid.uuid4()
    collector = QaTraceCollector(trace_id="trace-1")
    collector.record_step("retrieve_evidence", 900)

    persist_trace_steps(session=session, record_id=record_id, collector=collector)

    assert len(session.added) == 1
    assert isinstance(session.added[0], QaTraceStep)
    assert session.added[0].qa_record_id == record_id
    assert session.added[0].step_name == "retrieve_evidence"
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 -m pytest backend\tests\test_qa_trace.py -v
```

Expected: FAIL，原因是 `app.services.qa_trace` 不存在。

- [ ] **Step 3: 实现 trace 服务**

创建 `backend/app/services/qa_trace.py`：

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import uuid

from sqlalchemy.orm import Session

from app.models.rag import QaTraceStep


@dataclass(frozen=True)
class QaTraceStepData:
    step_name: str
    duration_ms: int
    status: str = "success"
    model_name: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    error_message: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class QaTraceCollector:
    trace_id: str
    steps: list[QaTraceStepData] = field(default_factory=list)

    def record_step(
        self,
        step_name: str,
        duration_ms: int,
        status: str = "success",
        model_name: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.steps.append(
            QaTraceStepData(
                step_name=step_name,
                duration_ms=duration_ms,
                status=status,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                error_message=error_message,
                metadata=metadata,
            )
        )

    def timings_ms(self) -> dict[str, int]:
        return {f"{step.step_name}_ms": step.duration_ms for step in self.steps}


def persist_trace_steps(
    session: Session,
    record_id: uuid.UUID,
    collector: QaTraceCollector,
) -> None:
    for step in collector.steps:
        session.add(
            QaTraceStep(
                qa_record_id=record_id,
                trace_id=collector.trace_id,
                step_name=step.step_name,
                duration_ms=step.duration_ms,
                status=step.status,
                model_name=step.model_name,
                input_tokens=step.input_tokens,
                output_tokens=step.output_tokens,
                error_message=step.error_message,
                step_metadata=step.metadata,
            )
        )
```

- [ ] **Step 4: 在 QA service 收尾处持久化 trace**

在 `backend/app/services/qa_service.py` 中：

1. 用 `QaTraceCollector` 替代裸 `timings: dict[str, int]` 或在现有 dict 基础上同步写 collector。
2. 每个阶段结束后调用：

```python
trace.record_step("rewrite_question", duration_ms)
trace.record_step("understand_intent", duration_ms)
trace.record_step("retrieve_evidence", duration_ms)
trace.record_step("answer_generation", duration_ms)
trace.record_step("summary_update", duration_ms)
trace.record_step("db_commit", duration_ms)
```

3. 在 `_finalize_response(...)` 中 `session.commit()` 前调用：

```python
persist_trace_steps(session=session, record_id=record.id, collector=trace)
```

4. 异常兜底分支也必须写入一条失败 step：

```python
trace.record_step(
    step_name="qa_exception",
    duration_ms=_latency_ms(start),
    status="failed",
    error_message=str(exc)[:1000],
    metadata={"reason": decision.reason},
)
```

- [ ] **Step 5: 增加 QA service 集成测试**

在 `backend/tests/test_qa_service.py` 增加：

```python
def test_answer_question_persists_trace_steps_for_rag_route():
    # 复用现有 FakeSession / make_dependencies / make_understanding / make_evidence。
    # 调用 answer_question 后，断言 FakeSession.added 中存在 QaTraceStep。
    trace_steps = get_added(session, QaTraceStep)

    assert {step.step_name for step in trace_steps} >= {
        "load_history",
        "rewrite_question",
        "understand_intent",
        "retrieve_evidence",
        "answer_generation",
        "summary_update",
        "db_commit",
    }
```

- [ ] **Step 6: 运行测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 -m pytest backend\tests\test_qa_trace.py backend\tests\test_qa_service.py -v
```

Expected: PASS。

---

### Task 3: 增加证据入模和引用展示阈值配置

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`
- Modify: `backend/app/services/evidence_filtering.py`
- Modify: `backend/app/services/qa_service.py`
- Test: `backend/tests/test_config.py`
- Test: `backend/tests/test_evidence_filtering.py`
- Test: `backend/tests/test_qa_service.py`

- [ ] **Step 1: 写配置失败测试**

在 `backend/tests/test_config.py` 增加：

```python
def test_settings_reads_reference_filtering_configuration():
    settings = Settings(
        qa_evidence_min_score="0.3",
        qa_reference_min_score="0.3",
        qa_reference_visible_top_k="3",
        qa_reference_max_top_k="5",
    )

    assert settings.qa_evidence_min_score == 0.3
    assert settings.qa_reference_min_score == 0.3
    assert settings.qa_reference_visible_top_k == 3
    assert settings.qa_reference_max_top_k == 5
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 -m pytest backend\tests\test_config.py::test_settings_reads_reference_filtering_configuration -v
```

Expected: FAIL。

- [ ] **Step 3: 增加配置字段**

在 `backend/app/core/config.py` 的 QA 配置附近增加：

```python
    qa_evidence_min_score: float = 0.3
    qa_reference_min_score: float = 0.3
    qa_reference_visible_top_k: int = 3
    qa_reference_max_top_k: int = 5
```

- [ ] **Step 4: 更新 `.env.example`**

增加：

```env
# 进入最终 chat 生成的证据最低 rerank 分数
QA_EVIDENCE_MIN_SCORE=0.3
# 返回给前端作为引用展示的最低 rerank 分数
QA_REFERENCE_MIN_SCORE=0.3
# 前端默认展开展示的引用数量
QA_REFERENCE_VISIBLE_TOP_K=3
# 后端最多返回给前端折叠展示的引用数量
QA_REFERENCE_MAX_TOP_K=5
```

- [ ] **Step 5: 拆分证据过滤函数**

修改 `backend/app/services/evidence_filtering.py`：

```python
def filter_evidence_for_answer(
    evidence: list[object],
    min_rerank_score: float,
    max_items: int,
) -> list[object]:
    return _filter_by_rerank_score(evidence, min_rerank_score, max_items)


def filter_references_for_response(
    evidence: list[object],
    min_rerank_score: float,
    max_items: int,
) -> list[object]:
    return _filter_by_rerank_score(evidence, min_rerank_score, max_items)


def _filter_by_rerank_score(
    evidence: list[object],
    min_rerank_score: float,
    max_items: int,
) -> list[object]:
    filtered: list[object] = []
    for item in evidence:
        score = getattr(item, "rerank_score", None)
        if score is None:
            continue
        if float(score) >= min_rerank_score:
            filtered.append(item)
        if len(filtered) >= max_items:
            break
    return filtered
```

- [ ] **Step 6: 增加过滤测试**

在 `backend/tests/test_evidence_filtering.py` 增加：

```python
def test_filter_references_for_response_applies_reference_threshold_and_limit():
    evidence = [
        SimpleNamespace(rerank_score=0.9),
        SimpleNamespace(rerank_score=0.7),
        SimpleNamespace(rerank_score=0.2),
        SimpleNamespace(rerank_score=0.4),
    ]

    result = filter_references_for_response(
        evidence,
        min_rerank_score=0.3,
        max_items=3,
    )

    assert [item.rerank_score for item in result] == [0.9, 0.7, 0.4]
```

- [ ] **Step 7: 接入 QA service**

修改 `answer_question(...)` 签名：

```python
qa_evidence_min_score: float = 0.3
qa_reference_min_score: float = 0.3
qa_reference_visible_top_k: int = 3
qa_reference_max_top_k: int = 5
```

在 RAG 分支中：

```python
evidence_for_answer = filter_evidence_for_answer(
    evidence=evidence,
    min_rerank_score=qa_evidence_min_score,
    max_items=qa_reference_visible_top_k,
)
evidence_for_response = filter_references_for_response(
    evidence=evidence,
    min_rerank_score=qa_reference_min_score,
    max_items=qa_reference_max_top_k,
)
```

在 `decision_metadata` 增加：

```python
"evidence_min_score": qa_evidence_min_score,
"reference_min_score": qa_reference_min_score,
"reference_visible_top_k": qa_reference_visible_top_k,
"reference_max_top_k": qa_reference_max_top_k,
"reference_count": len(evidence_for_response),
```

- [ ] **Step 8: 更新 API 调用参数**

在 `backend/app/api/qa.py` 调用 `answer_question(...)` 时增加：

```python
qa_evidence_min_score=settings.qa_evidence_min_score,
qa_reference_min_score=settings.qa_reference_min_score,
qa_reference_visible_top_k=settings.qa_reference_visible_top_k,
qa_reference_max_top_k=settings.qa_reference_max_top_k,
```

- [ ] **Step 9: 更新脚本调用参数**

在 `backend/scripts/ask_question.py` 调用 `answer_question(...)` 时增加同样参数。

- [ ] **Step 10: 运行测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 -m pytest backend\tests\test_config.py backend\tests\test_evidence_filtering.py backend\tests\test_qa_service.py -v
```

Expected: PASS。

---

### Task 4: 调整引用返回结构，支持默认 Top 3 和折叠展示

**Files:**
- Modify: `backend/app/schemas/qa.py`
- Modify: `backend/app/services/qa_service.py`
- Modify: `backend/scripts/chat_qa.py`
- Test: `backend/tests/test_qa_api.py`
- Test: `backend/tests/test_qa_service.py`

- [ ] **Step 1: 写 schema 测试**

在 `backend/tests/test_qa_api.py` 增加：

```python
def test_qa_reference_schema_supports_visibility_flag():
    reference = QaReferenceSchema(
        rank=1,
        segment_id="segment-1",
        document_id="document-1",
        heading_path="03_线缆接头与绝缘故障 > 4. 绝缘阻抗问题",
        excerpt="绝缘阻抗低可能与直流线缆破皮有关。",
        vector_score=0.6,
        keyword_score=0.4,
        rrf_score=0.03,
        rerank_score=0.9,
        visible=True,
    )

    assert reference.visible is True
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 -m pytest backend\tests\test_qa_api.py::test_qa_reference_schema_supports_visibility_flag -v
```

Expected: FAIL。

- [ ] **Step 3: 修改 schema**

在 `backend/app/schemas/qa.py` 的 `QaReferenceSchema` 增加：

```python
    visible: bool = True
```

- [ ] **Step 4: 修改引用构造**

修改 `backend/app/services/qa_service.py` 的 `_add_references(...)` 和 `_reference_schema(...)`：

```python
def _add_references(
    session: Session,
    record: QaRecord,
    evidence: list[object],
    visible_top_k: int,
) -> list[QaReferenceSchema]:
    references: list[QaReferenceSchema] = []
    for rank, item in enumerate(evidence, start=1):
        visible = rank <= visible_top_k
        ...
        references.append(_reference_schema(rank, item, visible=visible))
    return references


def _reference_schema(rank: int, item: object, visible: bool = True) -> QaReferenceSchema:
    return QaReferenceSchema(
        ...
        visible=visible,
    )
```

- [ ] **Step 5: 更新命令行显示**

修改 `backend/scripts/chat_qa.py`：

```python
visible_refs = [reference for reference in response.references if reference.visible]
hidden_refs = [reference for reference in response.references if not reference.visible]

for reference in visible_refs:
    ...

if hidden_refs:
    print(f"还有 {len(hidden_refs)} 条弱一些的引用，可在接口返回中查看。")
```

- [ ] **Step 6: 运行测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 -m pytest backend\tests\test_qa_api.py backend\tests\test_qa_service.py -v
```

Expected: PASS。

---

### Task 5: 增加 SiliconFlow Chat 流式输出能力

**Files:**
- Modify: `backend/app/services/siliconflow.py`
- Modify: `backend/app/services/answer_generation.py`
- Test: `backend/tests/test_siliconflow_client.py`
- Test: `backend/tests/test_answer_generation.py`

- [ ] **Step 1: 写 SiliconFlow stream 测试**

在 `backend/tests/test_siliconflow_client.py` 增加：

```python
import pytest
import httpx

from app.services.siliconflow import SiliconFlowChatClient


@pytest.mark.asyncio
async def test_chat_stream_yields_content_chunks(respx_mock):
    route = respx_mock.post("https://api.example.test/chat/completions").mock(
        return_value=httpx.Response(
            200,
            text=(
                'data: {"choices":[{"delta":{"content":"第一段"}}]}\n\n'
                'data: {"choices":[{"delta":{"content":"第二段"}}]}\n\n'
                "data: [DONE]\n\n"
            ),
            headers={"content-type": "text/event-stream"},
        )
    )
    client = SiliconFlowChatClient(
        client=httpx.AsyncClient(base_url="https://api.example.test"),
        api_key="test-key",
        model="test-model",
    )

    chunks = [chunk async for chunk in client.chat_stream([{"role": "user", "content": "hi"}])]

    assert route.called
    assert chunks == ["第一段", "第二段"]
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 -m pytest backend\tests\test_siliconflow_client.py::test_chat_stream_yields_content_chunks -v
```

Expected: FAIL。

- [ ] **Step 3: 实现 `chat_stream`**

在 `backend/app/services/siliconflow.py` 的 `SiliconFlowChatClient` 增加：

```python
import json
from collections.abc import AsyncIterator


async def chat_stream(
    self,
    messages: list[dict[str, str]],
    temperature: float = 0.1,
) -> AsyncIterator[str]:
    async with self._client.stream(
        "POST",
        "/chat/completions",
        headers=self._headers(),
        json={
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        },
    ) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue
            payload = line.removeprefix("data:").strip()
            if payload == "[DONE]":
                break
            data = json.loads(payload)
            delta = data["choices"][0].get("delta") or {}
            content = delta.get("content")
            if content:
                yield content
```

- [ ] **Step 4: 在 answer generation 增加 stream helper**

在 `backend/app/services/answer_generation.py` 增加：

```python
from collections.abc import AsyncIterator


class StreamingChatClient(ChatClient, Protocol):
    def chat_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
    ) -> AsyncIterator[str]:
        ...


async def stream_rag_answer(
    chat_client: StreamingChatClient,
    question: str,
    evidence: list[object],
    cautious: bool,
) -> AsyncIterator[str]:
    async for chunk in chat_client.chat_stream(
        messages=build_rag_answer_messages(question, evidence, cautious),
        temperature=0.1,
    ):
        yield chunk
```

- [ ] **Step 5: 运行测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 -m pytest backend\tests\test_siliconflow_client.py backend\tests\test_answer_generation.py -v
```

Expected: PASS。

---

### Task 6: 新增 SSE 事件模型和流式 QA 服务

**Files:**
- Create: `backend/app/services/qa_streaming.py`
- Modify: `backend/app/services/qa_dependencies.py`
- Test: `backend/tests/test_qa_streaming.py`

- [ ] **Step 1: 写 SSE 事件测试**

创建 `backend/tests/test_qa_streaming.py`：

```python
import json

from app.services.qa_streaming import format_sse_event


def test_format_sse_event_outputs_valid_sse_frame():
    frame = format_sse_event(
        event="status",
        data={"message": "正在检索知识库"},
    )

    assert frame.startswith("event: status\n")
    assert "data: " in frame
    assert frame.endswith("\n\n")
    payload = json.loads(frame.split("data: ", 1)[1])
    assert payload["message"] == "正在检索知识库"
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 -m pytest backend\tests\test_qa_streaming.py -v
```

Expected: FAIL。

- [ ] **Step 3: 实现 SSE 工具函数**

创建 `backend/app/services/qa_streaming.py`：

```python
from __future__ import annotations

from collections.abc import AsyncIterator
import json
from typing import Any


def format_sse_event(event: str, data: dict[str, Any]) -> str:
    return (
        f"event: {event}\n"
        f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    )
```

- [ ] **Step 4: 定义事件类型**

同文件增加：

```python
STATUS_UNDERSTANDING = "understanding"
STATUS_REWRITING = "rewriting"
STATUS_RETRIEVING = "retrieving"
STATUS_GENERATING = "generating"
STATUS_DONE = "done"
STATUS_ERROR = "error"
```

- [ ] **Step 5: 实现流式问答生成器**

在 `backend/app/services/qa_streaming.py` 增加：

```python
async def stream_qa_events(...) -> AsyncIterator[str]:
    yield format_sse_event("status", {"stage": STATUS_REWRITING, "message": "正在理解追问上下文"})
    yield format_sse_event("status", {"stage": STATUS_UNDERSTANDING, "message": "正在识别问题意图"})
    yield format_sse_event("status", {"stage": STATUS_RETRIEVING, "message": "正在检索知识库"})
    yield format_sse_event("status", {"stage": STATUS_GENERATING, "message": "正在生成答案"})
    # 第一版可以先复用非流式 answer_question，然后一次性输出 answer。
    # Task 7 再接入 token 级流式输出。
    response = await answer_question(...)
    yield format_sse_event("answer_delta", {"text": response.answer})
    yield format_sse_event("references", {"references": [item.model_dump() for item in response.references]})
    yield format_sse_event("done", response.model_dump(mode="json"))
```

注意：Task 6 先建立 SSE 协议和状态事件，Task 7 再把最终答案改成真正 token/chunk 流式输出。

- [ ] **Step 6: 运行测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 -m pytest backend\tests\test_qa_streaming.py -v
```

Expected: PASS。

---

### Task 7: 新增 `POST /api/qa/ask/stream` SSE 接口

**Files:**
- Modify: `backend/app/api/qa.py`
- Test: `backend/tests/test_qa_api.py`

- [ ] **Step 1: 写 API 测试**

在 `backend/tests/test_qa_api.py` 增加：

```python
def test_qa_stream_endpoint_returns_event_stream():
    app = create_app()

    async def fake_streamer(request):
        yield "event: status\ndata: {\"stage\":\"retrieving\"}\n\n"
        yield "event: done\ndata: {\"answer_type\":\"rag\"}\n\n"

    from app.api.qa import get_qa_streamer

    app.dependency_overrides[get_qa_streamer] = lambda: fake_streamer
    client = TestClient(app)

    with client.stream(
        "POST",
        "/api/qa/ask/stream",
        json={"question": "逆变器绝缘阻抗低怎么排查？"},
    ) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: status" in body
    assert "event: done" in body
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 -m pytest backend\tests\test_qa_api.py::test_qa_stream_endpoint_returns_event_stream -v
```

Expected: FAIL。

- [ ] **Step 3: 增加 FastAPI endpoint**

在 `backend/app/api/qa.py` 增加：

```python
from fastapi.responses import StreamingResponse
from collections.abc import AsyncIterator, Callable

QaStreamer = Callable[[QaAskRequest], AsyncIterator[str]]


def get_qa_streamer() -> QaStreamer:
    async def _stream(request: QaAskRequest) -> AsyncIterator[str]:
        async for event in stream_qa_events(...):
            yield event

    return _stream


@router.post("/ask/stream")
async def ask_question_stream(
    request: QaAskRequest,
    streamer: QaStreamer = Depends(get_qa_streamer),
) -> StreamingResponse:
    return StreamingResponse(
        streamer(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
```

- [ ] **Step 4: 运行测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 -m pytest backend\tests\test_qa_api.py -v
```

Expected: PASS。

---

### Task 8: 将最终答案接入真正 token/chunk 流式输出

**Files:**
- Modify: `backend/app/services/qa_service.py`
- Modify: `backend/app/services/qa_streaming.py`
- Modify: `backend/app/services/qa_dependencies.py`
- Test: `backend/tests/test_qa_streaming.py`
- Test: `backend/tests/test_qa_service.py`

- [ ] **Step 1: 定义 streaming answer client 协议**

在 `backend/app/services/qa_service.py` 或 `qa_streaming.py` 增加：

```python
class StreamingAnswerClient(Protocol):
    async def stream_rag(
        self,
        question: str,
        evidence: list[object],
        cautious: bool,
    ) -> AsyncIterator[str]:
        ...
```

- [ ] **Step 2: 在 RealAnswerClient 实现 `stream_rag`**

修改 `backend/app/services/qa_dependencies.py`：

```python
async def stream_rag(self, question: str, evidence: list[object], cautious: bool):
    async for chunk in stream_rag_answer(
        chat_client=self._chat_client,
        question=question,
        evidence=evidence,
        cautious=cautious,
    ):
        yield chunk
```

- [ ] **Step 3: 流式服务中复用检索和过滤逻辑**

`stream_qa_events(...)` 不能复制一份散乱 RAG 流程。需要从 `qa_service.py` 拆出一个内部 planning helper，例如：

```python
@dataclass
class QaPreparedAnswer:
    qa_session: QaSession
    understanding: QueryUnderstandingResult
    evidence_for_answer: list[object]
    evidence_for_response: list[object]
    cautious: bool
    decision_metadata: dict[str, object]
```

非流式和流式都先调用：

```python
prepared = await prepare_qa_answer(...)
```

然后：

- 非流式：调用 `generate_rag(...)`
- 流式：调用 `stream_rag(...)`，边收 chunk 边 `yield answer_delta`

- [ ] **Step 4: 流式完成后仍然写入完整 answer**

在 streaming 生成器中：

```python
answer_parts: list[str] = []
async for chunk in dependencies.answer_client.stream_rag(...):
    answer_parts.append(chunk)
    yield format_sse_event("answer_delta", {"text": chunk})

answer = "".join(answer_parts)
record = persist_prepared_answer(..., answer=answer)
yield format_sse_event("references", ...)
yield format_sse_event("done", response.model_dump(mode="json"))
```

- [ ] **Step 5: 增加流式测试**

在 `backend/tests/test_qa_streaming.py` 增加：

```python
@pytest.mark.asyncio
async def test_stream_qa_events_yields_answer_delta_before_done():
    events = [event async for event in stream_qa_events(...fake deps...)]

    answer_index = next(index for index, event in enumerate(events) if "event: answer_delta" in event)
    done_index = next(index for index, event in enumerate(events) if "event: done" in event)

    assert answer_index < done_index
```

- [ ] **Step 6: 运行测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 -m pytest backend\tests\test_qa_streaming.py backend\tests\test_qa_service.py -v
```

Expected: PASS。

---

### Task 9: 新增流式命令行验证脚本

**Files:**
- Create: `backend/scripts/stream_chat_qa.py`
- Test: `backend/tests/test_qa_api.py`

- [ ] **Step 1: 写安全导入测试**

在 `backend/tests/test_qa_api.py` 增加：

```python
def test_stream_chat_qa_script_imports_safely_without_executing_main():
    import backend.scripts.stream_chat_qa as stream_script

    assert hasattr(stream_script, "main")
```

- [ ] **Step 2: 创建脚本**

创建 `backend/scripts/stream_chat_qa.py`：

```python
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings


async def main() -> None:
    print("RAG SSE 流式问答")
    print("输入 /exit 退出。")
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{settings.app_port}", timeout=None) as client:
        session_id = None
        while True:
            question = input("你：").strip()
            if question.lower() in {"/exit", "exit", "quit", "q"}:
                break
            payload = {"question": question, "session_id": session_id}
            async with client.stream("POST", "/api/qa/ask/stream", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = json.loads(line.removeprefix("data: "))
                    if "text" in data:
                        print(data["text"], end="", flush=True)
                    if "session_id" in data:
                        session_id = data["session_id"]
                print()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: 运行导入测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 -m pytest backend\tests\test_qa_api.py::test_stream_chat_qa_script_imports_safely_without_executing_main -v
```

Expected: PASS。

---

### Task 10: 文档和手动验证说明

**Files:**
- Modify: `docs/RAG问答接口闭环流程说明.md` 或当前实际 QA 流程说明文档
- Test: manual

- [ ] **Step 1: 补充数据库日志说明**

文档中增加：

```markdown
### QA Trace Step

`qa_trace_step` 用于记录每轮问答的阶段耗时：

- `rewrite_question`
- `understand_intent`
- `retrieve_evidence`
- `answer_generation`
- `summary_update`
- `db_commit`

后续日志后台页面优先读取该表，而不是解析 `qa_record.decision_metadata`。
```

- [ ] **Step 2: 补充 SSE 说明**

文档中增加：

```markdown
### SSE 流式问答

接口：`POST /api/qa/ask/stream`

事件类型：

- `status`
- `answer_delta`
- `references`
- `done`
- `error`

系统不展示模型原始思考链，只展示处理阶段和最终依据。
```

- [ ] **Step 3: 补充引用阈值说明**

文档中增加：

```markdown
### 引用过滤策略

- `QA_EVIDENCE_MIN_SCORE` 控制证据是否进入 chat。
- `QA_REFERENCE_MIN_SCORE` 控制证据是否作为引用返回。
- `QA_REFERENCE_VISIBLE_TOP_K` 控制默认展开数量。
- `QA_REFERENCE_MAX_TOP_K` 控制后端最多返回数量。
```

- [ ] **Step 4: 手动验证命令**

```powershell
cd D:\桌面\文件\operation_project\backend
python.exe -m alembic upgrade head
python.exe -X utf8 scripts\chat_qa.py --show-timing --show-decision --show-references
python.exe -X utf8 scripts\stream_chat_qa.py
```

- [ ] **Step 5: 数据库验证 SQL**

```sql
select id, session_id, question, answer_type, created_at
from qa_record
where session_id = '<你的 session_id>'
order by created_at;

select step_name, duration_ms, status, model_name, created_at
from qa_trace_step
where trace_id = '<某一轮 trace_id>'
order by created_at;

select rank, relevance_score, ref_metadata
from qa_reference
where qa_record_id = '<某一轮 qa_record.id>'
order by rank;
```

- [ ] **Step 6: 全量测试**

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 -m pytest backend\tests -q
```

Expected: PASS。

---

## Self-Review

**Spec coverage:** 本计划覆盖用户确认的三类需求：新增正式日志表用于后续日志页面；增加 SSE 流式问答改善体感；保留意图识别但增加证据入模和引用展示阈值。计划明确不跳过意图识别，不展示模型原始思考链，并保留每轮问题入库规则。

**Placeholder scan:** 本计划没有使用 TBD、TODO、implement later 或“自行补充测试”。每个任务均包含目标文件、测试、实现示例和验证命令。

**Type consistency:** 计划中统一使用 `QaTraceStep`、`QaTraceCollector`、`filter_evidence_for_answer`、`filter_references_for_response`、`qa_evidence_min_score`、`qa_reference_min_score`、`qa_reference_visible_top_k`、`qa_reference_max_top_k`、`chat_stream`、`stream_qa_events` 命名。`QaReferenceSchema.visible` 与命令行折叠展示逻辑一致。

**Important guardrail:** 执行本计划时不要修改真实 `.env`，不要删除数据库，不要跳过 Alembic migration。SSE 首版可以先提供状态事件和一次性答案，随后再接 token/chunk 级流式输出，避免一次改动过大。
