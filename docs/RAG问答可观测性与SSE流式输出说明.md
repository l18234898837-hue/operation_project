# RAG 问答可观测性与 SSE 流式输出说明

本文说明本次 RAG 问答链路新增的三类能力：

- 每轮问答的阶段耗时入库，方便后续日志页面分析慢在哪里。
- SSE 流式问答接口，方便前端尽快展示处理状态和答案片段。
- 证据入模与引用展示阈值，避免弱相关证据进入答案或展示给用户。

## 1. 本次新增内容

### 1.1 问答耗时日志表

新增数据库表：`qa_trace_step`

该表用于记录每一轮问答的关键阶段耗时。它不是业务主表，而是后续日志页面、性能分析页面要优先读取的明细表。

典型阶段包括：

- `get_or_create_session`：获取或创建会话。
- `load_history`：读取多轮会话历史。
- `build_context`：构造上下文。
- `rewrite_question`：结合历史把当前问题改写成独立问题。
- `understand_intent`：意图识别。
- `retrieve_evidence`：向量检索、关键词检索、RRF、rerank。
- `filter_evidence`：证据阈值过滤。
- `answer_generation`：调用 chat 模型生成答案。
- `summary_update`：超过历史窗口后更新会话摘要。
- `db_write_record`：写入问答记录和引用。
- `db_commit`：提交事务。
- `qa_exception`：异常兜底记录。

同时，`qa_record.decision_metadata.timings_ms` 仍然保留，用于接口返回和命令行快速查看；`qa_trace_step` 更适合做后台统计和日志页面。

### 1.2 SSE 流式问答接口

新增接口：

```http
POST /api/qa/ask/stream
```

请求体与普通问答接口基本一致：

```json
{
  "question": "逆变器绝缘阻抗低怎么排查？",
  "session_id": "可选，会话 ID"
}
```

响应类型：

```http
Content-Type: text/event-stream
```

事件类型：

- `status`：后端当前处理阶段，例如理解问题、检索知识库、生成答案。
- `answer_delta`：答案增量片段。
- `references`：引用片段列表。
- `done`：完整问答结果。
- `error`：异常信息。

注意：系统不会展示模型原始思考链，只展示处理阶段、最终答案、引用证据和必要决策信息。

### 1.3 证据过滤和引用折叠

新增配置项：

```env
QA_EVIDENCE_MIN_SCORE=0.3
QA_REFERENCE_MIN_SCORE=0.3
QA_REFERENCE_VISIBLE_TOP_K=3
QA_REFERENCE_MAX_TOP_K=5
```

含义如下：

- `QA_EVIDENCE_MIN_SCORE`：控制证据是否进入 chat 模型。低于该 rerank 分数的证据不参与最终答案生成。
- `QA_REFERENCE_MIN_SCORE`：控制证据是否作为引用返回给前端。
- `QA_REFERENCE_VISIBLE_TOP_K`：默认展开展示的引用数量，当前建议为 3。
- `QA_REFERENCE_MAX_TOP_K`：后端最多返回的引用数量，当前建议为 5，其余由前端折叠展示。

每条引用新增 `visible` 字段：

```json
{
  "rank": 1,
  "heading_path": "03_线缆接头与绝缘故障 > 4. 绝缘阻抗问题",
  "rerank_score": 0.89,
  "visible": true
}
```

前端可以按 `visible=true` 默认展开 Top 3，`visible=false` 的引用放入折叠区。

## 2. 为什么这样设计

### 2.1 每轮问题都应该入库

多轮会话里，用户每问一个问题，都应该生成一条 `qa_record`。

原因：

- 后续日志页面需要看到完整会话轨迹。
- 每轮问题的意图、检索证据、答案、置信度可能都不同。
- 即使是拒答、低置信、通用回答、异常回答，也应该可追踪。

因此当前设计是：每一轮都写入 `qa_record`，并把该轮的耗时明细写入 `qa_trace_step`。

### 2.2 SSE 改善的是体感，不一定减少总耗时

从你之前的测试看，慢主要集中在模型调用：

- `answer_generation_ms` 较高，说明 chat 模型生成耗时长。
- `understand_intent_ms` 有时也较高，说明意图识别模型调用或网络等待较长。
- `retrieve_evidence_ms` 通常在 1 秒左右，不是主要瓶颈。

SSE 的价值是让用户更早看到：

- 系统正在理解问题。
- 系统正在检索知识库。
- 系统正在生成答案。
- 答案片段开始输出。

即使总耗时仍然接近，用户体感会明显好一些。

### 2.3 意图识别仍然保留

即使当前问题是追问，也不能直接跳过意图识别。

原因是用户可能在同一个会话中突然问无关问题，例如前面聊逆变器，后面问天气、闲聊或其他系统外问题。

因此当前约束是：

- 多轮历史只用于生成 `standalone_question`。
- 意图识别仍然基于当前轮问题和必要上下文判断。
- 最终 RAG 回答仍然只基于当前轮重新检索出来的证据。

## 3. 手动验证方式

以下命令均在后端目录执行：

```powershell
cd D:\桌面\文件\operation_project\backend
```

### 3.1 执行数据库迁移

```powershell
python.exe -m alembic upgrade head
```

成功后会创建 `qa_trace_step` 表。

### 3.2 使用普通命令行问答

```powershell
python.exe -X utf8 scripts\chat_qa.py --show-timing --show-decision --show-references
```

建议测试：

```text
逆变器绝缘阻抗低怎么排查？
那如果只在下雨天出现呢？
下雨才坏，平时又正常，这是啥情况？
```

观察重点：

- 每一轮是否都有 `会话`、`类型`、`意图`、`置信度`。
- `耗时` 中是否能看到 `answer_generation_ms`、`retrieve_evidence_ms`、`rewrite_question_ms` 等阶段。
- 引用是否默认只展示强相关 Top 3。

### 3.3 使用 SSE 流式命令行问答

先启动后端 API 服务。

然后执行：

```powershell
python.exe -X utf8 scripts\stream_chat_qa.py
```

观察重点：

- 是否能先看到状态提示。
- 答案是否逐段输出。
- 完成后是否还能拿到完整结果和引用。

### 3.4 查询问答记录

把下面的 `session_id` 换成命令行输出里的会话 ID：

```sql
select id, session_id, question, answer_type, intent, confidence, created_at
from qa_record
where session_id = '<你的 session_id>'
order by created_at;
```

预期：多轮会话中的每一个问题都有一条记录。

### 3.5 查询阶段耗时

先从 `qa_record` 找到某一轮的 `trace_id`，再查询：

```sql
select step_name, duration_ms, status, model_name, error_message, created_at
from qa_trace_step
where trace_id = '<某一轮 trace_id>'
order by created_at;
```

预期：能看到该轮问答各阶段耗时。

### 3.6 查询引用记录

把 `qa_record_id` 换成某一轮问答记录 ID：

```sql
select rank, segment_id, relevance_score, ref_metadata
from qa_reference
where qa_record_id = '<某一轮 qa_record.id>'
order by rank;
```

预期：

- 高相关引用排在前面。
- 弱相关证据不会无限制进入引用。
- 前端后续可以根据接口返回的 `visible` 字段决定默认展开或折叠。

## 4. 后续建议

当前阶段建议先不要急着调阈值，等你收集一批真实问题后再统一评估：

- 如果答案经常引用弱相关片段，可以提高 `QA_EVIDENCE_MIN_SCORE` 和 `QA_REFERENCE_MIN_SCORE`。
- 如果答案经常因为证据不足而拒答，可以适当降低阈值。
- 如果 Top 3 不够用，前端可以默认展示 3 条，允许用户展开查看最多 5 条。
- 如果仍然觉得慢，优先看 `qa_trace_step` 中 `answer_generation` 和 `understand_intent` 的耗时，再决定是否换模型、缩短 prompt、减少入模证据或优化网络。
