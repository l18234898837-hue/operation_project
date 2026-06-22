# RAG 问答接口闭环流程说明

本文用于帮助理解当前项目里刚完成的 RAG 问答接口闭环。它是在“RAG 知识库最小闭环”的基础上继续往后走的一层：不再只返回 Top 5 证据片段，而是把证据交给 chat 模型生成答案，并把问答记录、引用片段和无法回答的问题写入数据库。

它不是前端页面说明，也不是完整 API 文档，而是一份“从用户问题到 RAG 答案”的完整链路说明，并附带手动验证方式。

## 1. 当前阶段做到了什么

当前已经完成的是 RAG 问答接口的最小闭环：

1. 接收用户问题。
2. 对用户问题做基础校验。
3. 通过硬规则和 LLM 判断问题意图。
4. 对口语化问题做规范化和 query rewrite。
5. 判断是否需要使用知识库。
6. 如果是知识库问题，调用已有 RAG 检索链路取证据。
7. 用 rerank 分数判断是否拒答。
8. 对可信证据调用 chat 模型生成答案。
9. 返回答案、置信度、Top 证据引用和决策信息。
10. 将问答记录写入 `qa_record`。
11. 将 RAG 答案引用写入 `qa_reference`。
12. 将无法回答或低置信问题写入 `qa_unanswered`。

这意味着当前系统已经从“能检索证据”推进到了“能基于证据回答问题”。

暂时还没有做前端页面、多轮会话、流式输出、权限系统、人工标注评测集和生产级监控。这一阶段的目标是先确认“问题能进入接口，接口能判断路线，知识库问题能生成带引用的答案，低置信或实时外部问题能拒答”。

## 2. 技术路线

当前问答闭环使用的路线如下：

- 数据库：本地 Windows PostgreSQL 16，数据库名 `operation_pv`
- 向量扩展：pgvector
- Embedding 模型：`BAAI/bge-m3`
- Embedding 维度：1024
- Embedding 调用方：SiliconFlow API
- 关键词检索：PostgreSQL full-text search，检索 `kb_document_segment.keyword_text`
- 融合排序：RRF
- Reranker：`BAAI/bge-reranker-v2-m3`
- Reranker 调用方：SiliconFlow API
- Intent 模型：`deepseek-ai/DeepSeek-V4-Flash`
- Chat 模型：`deepseek-ai/DeepSeek-V4-Flash`
- API 路径：`POST /api/qa/ask`
- 手动验证脚本：`backend/scripts/ask_question.py`

## 3. 核心文件位置

和问答闭环直接相关的文件主要是：

- `backend/app/api/qa.py`
  定义 `POST /api/qa/ask` 接口，并组装真实依赖。

- `backend/app/api/router.py`
  将 QA router 挂载到 `/api/qa` 下。

- `backend/app/schemas/qa.py`
  定义问答请求、响应和引用片段 schema。

- `backend/app/services/query_understanding.py`
  负责意图识别、硬规则、LLM JSON 解析、query rewrite 和后置校验。

- `backend/app/services/retrieval.py`
  复用上一阶段的向量检索、关键词检索、RRF 融合和 rerank。

- `backend/app/services/answer_generation.py`
  定义 RAG 答案 prompt 和通用 LLM 答案 prompt。

- `backend/app/services/qa_service.py`
  负责编排完整问答流程，并写入 `qa_record`、`qa_reference`、`qa_unanswered`。

- `backend/app/services/qa_dependencies.py`
  封装真实 SiliconFlow client、retriever 和 answer client 的依赖构造。

- `backend/app/services/siliconflow.py`
  包含 SiliconFlow embedding、rerank 和 chat client。

- `backend/scripts/ask_question.py`
  用于手动验证问答闭环的 CLI 脚本。

- `backend/alembic/versions/20260622_0002_add_qa_answer_types.py`
  为 `answer_type` enum 增加 `general_llm` 和 `refused`。

- `docs/qa-api-verification.md`
  记录 QA API 的验证命令和结果。

## 4. 数据库表怎么理解

问答接口主要使用下面这些表：

- `qa_session`
  表示一次会话。当前接口已经支持传入 `session_id`，但还没有做完整多轮上下文。

- `qa_record`
  每次用户提问都会写入一条记录，包括原始问题、规范化问题、答案、答案类型、置信度、耗时和决策信息。

- `qa_reference`
  RAG 答案引用了哪些知识库片段，就写入这里。通用 LLM 答案不会写引用。

- `qa_unanswered`
  无法回答的问题会写入这里，例如实时外部问题、领域外问题、低置信知识库问题。

- `kb_document_segment`
  检索和引用的核心来源表。RAG 答案里的 `segment_id` 和 `document_id` 都来自这里。

当前新增的答案类型包括：

- `rag`
  使用知识库证据生成的答案。

- `general_llm`
  不使用项目知识库，仅使用模型自身知识回答的通用解释答案。

- `refused`
  拒答，表示系统当前无法可靠回答。

- `none`
  内部默认状态。

## 5. 问答接口整体流程

用户请求进入 `POST /api/qa/ask` 后，整体流程如下：

1. FastAPI 使用 `QaAskRequest` 校验请求。
2. `question` 会去掉前后空白。
3. 空问题会被拒绝。
4. 非法 `session_id` 会在请求校验层返回 422，避免进入服务层后变成 500。
5. 接口创建 SiliconFlow chat、embedding、rerank client。
6. 创建数据库 session。
7. 调用 `answer_question(...)` 进入服务层。
8. 服务层先做 query understanding。
9. 根据意图选择：
   - RAG 路线
   - 通用 LLM 路线
   - 拒答路线
10. 生成答案或拒答消息。
11. 写入数据库。
12. 返回 `QaAskResponse`。

返回结构大致包含：

```json
{
  "trace_id": "...",
  "answer_type": "rag",
  "intent": "knowledge_base_qa",
  "answer": "...",
  "confidence": 0.858,
  "references": [],
  "decision": {}
}
```

## 6. 意图识别怎么工作

当前意图识别分三层。

### 6.1 硬规则

硬规则先处理明显问题：

1. 空问题、全标点、过短输入：`invalid_input`
2. 天气、新闻、股票、汇率、当前时间等实时外部问题：`realtime_external`
3. 光伏运维领域词 + 故障/处理动作词：强制 `knowledge_base_qa`

例如：

```text
逆变器绝缘阻抗低怎么排查？
```

会命中“领域词 + 故障动作词”，直接进入知识库问答路线。

```text
今天上海天气怎么样？
```

会命中实时外部问题，直接拒答，不调用知识库检索。

### 6.2 LLM 意图识别和 Query 改写

对于硬规则无法明确判断的问题，会调用 `deepseek-ai/DeepSeek-V4-Flash` 做结构化 JSON 输出。

模型只做判断和改写，不直接回答用户问题。

输出内容包括：

- `intent`
- `confidence`
- `should_use_knowledge_base`
- `normalized_question`
- `search_query`
- `reason`

这样做的目的，是把用户口语化的问题改成更适合检索的形式，同时保留设备名称、故障码、型号、英文缩写和技术术语。

### 6.3 后置校验

模型输出不能完全相信，所以还会做后置校验：

1. 如果模型说是 `general_explanation`，但问题里有领域词和故障动作词，会改回 `knowledge_base_qa`。
2. 如果知识库问题的 `search_query` 为空，会回退到 `normalized_question`。
3. 如果模型 JSON 解析失败，会使用规则兜底。

这相当于用提示词做能力，用代码规则做边界。

## 7. 三条回答路线

### 7.1 RAG 路线

当意图是 `knowledge_base_qa` 时，会进入 RAG 路线。

流程如下：

1. 使用 `search_query` 或 `normalized_question` 做检索。
2. 调用 `BAAI/bge-m3` 生成 query embedding。
3. 走 pgvector dense 向量检索。
4. 走 PostgreSQL 关键词检索。
5. 用 RRF 融合两路结果。
6. 调用 `BAAI/bge-reranker-v2-m3` 重排序。
7. 取最终证据。
8. 根据 top1 `rerank_score` 判断是否低置信。
9. 如果分数足够，调用 chat 模型生成答案。
10. 返回答案和引用。

RAG 答案必须满足：

- `answer_type = rag`
- `references` 非空
- `decision.used_knowledge_base = true`

### 7.2 通用 LLM 路线

当意图是 `general_explanation`，并且 `should_use_knowledge_base = false` 时，会走通用 LLM 路线。

例如：

```text
什么是无功功率？
```

这类问题可以不依赖项目知识库，直接由模型解释。

通用 LLM 答案必须满足：

- `answer_type = general_llm`
- `references = []`
- `decision.used_knowledge_base = false`

也就是说，如果没有使用知识库，就不应该伪造来源引用。

### 7.3 拒答路线

以下情况会拒答：

1. 输入无效。
2. 实时外部问题。
3. 领域外问题。
4. 知识库问题检索结果为空。
5. top1 `rerank_score` 低于 `QA_RERANK_MIN_SCORE`。

拒答答案必须满足：

- `answer_type = refused`
- `references = []`
- 写入 `qa_unanswered`

## 8. Rerank 阈值怎么理解

当前有两个阈值：

- `QA_RERANK_MIN_SCORE=0.2`
  低于这个值，系统认为证据不可靠，拒答。

- `QA_RERANK_STRONG_SCORE=0.6`
  高于这个值，系统认为证据比较强，可以正常回答。

如果 top1 分数在 `0.2` 到 `0.6` 之间，当前会生成谨慎答案，prompt 中会强调“根据当前知识库中相关片段”。

已经验证过的问题：

```text
逆变器绝缘阻抗低怎么排查？
```

top1 `rerank_score` 约为：

```text
0.858
```

这明显高于 `0.6`，所以系统正常生成 RAG 答案。

## 9. 答案生成怎么约束

RAG 答案生成使用专门 prompt，核心约束是：

1. 只能基于给定证据回答。
2. 不能编造证据中没有的信息。
3. 如果证据不足，需要明确说明。
4. 中等置信问题要用谨慎语气。

通用 LLM 答案使用另一套 prompt，核心约束是：

1. 不引用项目知识库。
2. 用通用知识回答。
3. 返回时 `references` 保持为空。

这两套 prompt 分开，是为了避免模型把“知识库答案”和“模型自身知识答案”混在一起。

## 10. 持久化流程

每次调用 `answer_question(...)` 都会创建或复用一个 `qa_session`，然后写入 `qa_record`。

### RAG 答案

会写入：

- `qa_record`
- `qa_reference`

`qa_reference` 会保存：

- `qa_record_id`
- `document_id`
- `segment_id`
- `rank`
- `relevance_score`
- `vector_score`
- `keyword_score`
- `rrf_score`
- `excerpt`
- `heading_path`

### 通用 LLM 答案

会写入：

- `qa_record`

不会写入：

- `qa_reference`

因为它没有使用知识库。

### 拒答问题

会写入：

- `qa_record`
- `qa_unanswered`

这样后续可以人工查看哪些问题没有被系统解决。

## 11. 当前验证结果

### 单元测试

当前全量单元测试结果：

```text
99 passed
```

其中覆盖了：

- QA 配置读取。
- `AnswerType.general_llm` 和 `AnswerType.refused`。
- SiliconFlow chat client。
- 意图识别和 query rewrite。
- RAG 和 general answer prompt。
- QA service 编排和持久化。
- `/api/qa/ask` endpoint。
- `ask_question.py` 脚本导入安全。
- 非法 `session_id` 返回 422。

### 数据库迁移

已经手动验证：

```powershell
python.exe -m alembic upgrade head
```

结果：

```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
```

说明 Alembic 可以正常连接本地 PostgreSQL 并执行迁移。

### RAG 问题验证

验证问题：

```text
逆变器绝缘阻抗低怎么排查？
```

返回结果符合预期：

- `answer_type`: `rag`
- `intent`: `knowledge_base_qa`
- `confidence`: 约 `0.858`
- `references`: 5 条
- `decision.used_knowledge_base`: `true`
- `decision.refusal_reason`: `null`

Top 1 证据：

```text
03_线缆接头与绝缘故障 > 4. 绝缘阻抗问题
```

这说明系统能够把“逆变器绝缘阻抗低”正确拉到“线缆接头与绝缘故障”的相关片段。

## 12. 手动验证前的准备

请确认：

1. PostgreSQL 16 正在运行。
2. 数据库 `operation_pv` 存在。
3. `.env` 已填写本地数据库连接信息。
4. `.env` 已填写 SiliconFlow API Key。
5. `.env` 中模型配置类似如下：

```env
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_API_KEY=你的硅基流动APIKey
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIMENSION=1024

RERANK_BASE_URL=https://api.siliconflow.cn/v1
RERANK_API_KEY=你的硅基流动APIKey
RERANK_MODEL=BAAI/bge-reranker-v2-m3
RERANK_ENABLED=true

LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_API_KEY=你的硅基流动APIKey
LLM_MODEL=deepseek-ai/DeepSeek-V4-Flash

QA_RERANK_MIN_SCORE=0.2
QA_RERANK_STRONG_SCORE=0.6
QA_REFERENCE_TOP_K=5
QA_INTENT_MODEL=deepseek-ai/DeepSeek-V4-Flash
QA_CHAT_MODEL=deepseek-ai/DeepSeek-V4-Flash
MODEL_API_TIMEOUT_SECONDS=300
```

注意：不要把真实 API Key 提交到 Git。

## 13. 手动验证方式

以下命令如果在项目根目录执行：

```powershell
cd D:\桌面\文件\operation_project
```

### 13.1 验证单元测试

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests -v
```

期望结果：

```text
99 passed
```

### 13.2 验证数据库迁移

```powershell
cd D:\桌面\文件\operation_project\backend
python.exe -m alembic upgrade head
```

期望结果：

- 命令无报错。
- `answer_type` enum 包含 `general_llm` 和 `refused`。

### 13.3 验证 RAG 问题

如果当前目录在 `backend`：

```powershell
python.exe -X utf8 scripts\ask_question.py "逆变器绝缘阻抗低怎么排查？"
```

如果当前目录在项目根目录：

```powershell
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\ask_question.py "逆变器绝缘阻抗低怎么排查？"
```

期望：

- `answer_type` 为 `rag`。
- `intent` 为 `knowledge_base_qa`。
- `references` 非空。
- Top 1 heading 接近 `03_线缆接头与绝缘故障 > 4. 绝缘阻抗问题`。
- `decision.used_knowledge_base` 为 `true`。

### 13.4 验证通用解释问题

```powershell
python.exe -X utf8 scripts\ask_question.py "什么是无功功率？"
```

期望：

- 通常为 `general_llm`。
- `references` 为空。
- `decision.used_knowledge_base` 为 `false`。

如果意图识别判断本地知识库覆盖该问题，也可能走 `rag`。这种情况下必须带引用。

### 13.5 验证实时外部问题

```powershell
python.exe -X utf8 scripts\ask_question.py "今天上海天气怎么样？"
```

期望：

- `answer_type` 为 `refused`。
- `intent` 为 `realtime_external`。
- `references` 为空。
- `decision.refusal_reason` 为 `realtime_external`。

### 13.6 验证持久化结果

在项目根目录执行：

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
@'
from sqlalchemy import text
from app.db.session import SessionLocal

with SessionLocal() as session:
    records = session.execute(text("SELECT answer_type::text, COUNT(*) FROM qa_record GROUP BY answer_type::text ORDER BY answer_type::text")).all()
    references = session.execute(text("SELECT COUNT(*) FROM qa_reference")).scalar_one()
    unanswered = session.execute(text("SELECT COUNT(*) FROM qa_unanswered")).scalar_one()

    print("records =", [(row[0], row[1]) for row in records])
    print("references =", references)
    print("unanswered =", unanswered)
'@ | backend\.venv\Scripts\python.exe -X utf8 -
```

期望：

- RAG 问题会增加 `qa_record` 和 `qa_reference`。
- 通用解释问题会增加 `qa_record`，但不增加 `qa_reference`。
- 实时外部问题或低置信问题会增加 `qa_record` 和 `qa_unanswered`。

## 14. 如何判断验证通过

可以按下面标准判断：

1. 单元测试通过。
2. Alembic 迁移无报错。
3. `POST /api/qa/ask` 或 `ask_question.py` 能返回结构化 JSON。
4. 知识库问题返回 `answer_type = rag`。
5. RAG 答案有非空 `references`。
6. RAG 答案的 Top 1 证据和问题主题高度相关。
7. 通用解释问题可以走 `general_llm`，且引用为空。
8. 实时外部问题会拒答。
9. 低置信问题会写入 `qa_unanswered`。
10. 真实 API Key 没有进入 `.env.example` 或 Git。

如果以上都满足，说明 RAG 问答接口闭环已经可用。

## 15. 常见问题

### 15.1 为什么第一次执行脚本提示找不到文件？

如果当前目录已经在 `backend`，就不能再写：

```powershell
python.exe -X utf8 backend\scripts\ask_question.py "问题"
```

因为这会变成：

```text
backend\backend\scripts\ask_question.py
```

正确写法是：

```powershell
python.exe -X utf8 scripts\ask_question.py "问题"
```

### 15.2 为什么 SiliconFlow 请求会超时？

RAG 问答会调用多次模型 API：

1. 意图识别 chat。
2. embedding。
3. rerank。
4. 最终答案生成 chat。

如果网络、代理或 SiliconFlow 服务响应慢，最后一步可能出现 `httpx.ReadTimeout`。

当前已经加入：

```env
MODEL_API_TIMEOUT_SECONDS=300
```

可以在 `.env` 中调大这个值。

### 15.3 为什么 Top 5 里会有弱相关证据？

当前接口默认返回 Top 5 证据。实际验证中，Top 1 非常准确，但第 4、第 5 条可能相关性较弱。

后续可以考虑：

- 只把 `rerank_score >= 0.2` 的证据传给 chat 模型。
- 或只把 Top 3 传给 chat 模型。
- 或在回答引用里隐藏低于阈值的证据。

### 15.4 为什么通用问题可以不走知识库？

有些问题是通用概念解释，例如：

```text
什么是无功功率？
```

这类问题不一定需要项目知识库。如果系统判断为 `general_explanation`，会使用模型自身知识回答，并保持 `references=[]`。

这样做的好处是：

- 简单问题响应更自然。
- 不会为了引用而强行检索弱相关片段。
- 用户能从空引用看出本次回答没有使用知识库。

### 15.5 为什么天气问题会拒答？

天气、新闻、股票、汇率、当前时间等问题属于实时外部信息。

当前系统没有接入实时外部工具，所以会返回：

- `answer_type = refused`
- `intent = realtime_external`
- `references = []`

这是预期行为。

## 16. 下一阶段建议

推荐下一阶段按这个顺序继续：

1. 给前端接入 `POST /api/qa/ask`。
2. 在前端展示答案、引用片段和置信度。
3. 对 `references` 做折叠展示，默认只显示 Top 3。
4. 对 `qa_unanswered` 做一个后台查看页面。
5. 增加人工黄金问答集，用来评估召回质量和答案质量。
6. 根据测试结果调整 `QA_RERANK_MIN_SCORE` 和 `QA_RERANK_STRONG_SCORE`。
7. 考虑只把高于阈值的证据传给 chat 模型，减少弱相关引用。
