# RAG Minimum Loop Verification

## Environment

- Database: local Windows PostgreSQL 16, database `operation_pv`
- Vector extension: pgvector
- Embedding provider: SiliconFlow API
- Embedding model: `BAAI/bge-m3`
- Embedding dimension: 1024
- Keyword retrieval: PostgreSQL full-text search over `kb_document_segment.keyword_text`
- Fusion: RRF
- Rerank provider: SiliconFlow API
- Rerank model: `BAAI/bge-reranker-v2-m3`
- Chat model configured for later QA work: `deepseek-ai/DeepSeek-V4-Flash`

## Commands Run

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests -v

cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
cd ..

backend\.venv\Scripts\python.exe backend\scripts\import_knowledge_base.py

backend\.venv\Scripts\python.exe -X utf8 backend\scripts\query_knowledge_base.py "逆变器绝缘阻抗低怎么排查？"
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\query_knowledge_base.py "SVG 无功补偿异常怎么处理？"
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\query_knowledge_base.py "今天上海天气怎么样？"
```

## Test Results

- Backend unit tests: 58 passed.
- Alembic migration: applied successfully.
- Import script: imported 9 Markdown knowledge documents.
- RAG tables present: `faq_item`, `kb_document`, `kb_document_segment`, `parse_task`, `qa_record`, `qa_reference`, `qa_session`, `qa_unanswered`.

## Import Results

- Documents: 9
- Segments: 93
- Document statuses: 9 ready

Segment counts by document:

- SVG与无功设备故障: 8
- 安全风险与应急处理: 8
- 变压器箱变与电气设备: 10
- 发电量异常与效率损失: 12
- 逆变器故障与维护: 14
- 线缆接头与绝缘故障: 7
- 巡检检测与预防维护: 10
- 运维管理制度与人员配置: 12
- 组件故障与低效问题: 12

## Query Results

### 逆变器绝缘阻抗低怎么排查？

Top 5 headings:

1. `03_线缆接头与绝缘故障 > 4. 绝缘阻抗问题`
2. `01_逆变器故障与维护 > 3. 常见故障与处理 > 3.2 电网过压或欠压`
3. `01_逆变器故障与维护 > 3. 常见故障与处理 > 3.3 漏电流故障`
4. `01_逆变器故障与维护 > 3. 常见故障与处理 > 3.7 逆变器效率与线损检查`
5. `01_逆变器故障与维护 > 3. 常见故障与处理 > 3.1 PV 过压`

Observed scores:

- Top 1 vector score: 0.6402819156646729
- Top 1 keyword score: 0.5
- Top 1 RRF score: 0.03252247488101534
- Top 1 rerank score: 0.8569533824920654

### SVG 无功补偿异常怎么处理？

Top 5 headings:

1. `04_SVG与无功设备故障 > 5. 电网电压异常保护`
2. `04_SVG与无功设备故障 > 3. SVG 装置停止工作`
3. `04_SVG与无功设备故障 > 6. 通信故障`
4. `04_SVG与无功设备故障 > 7. 运行中停机`
5. `04_SVG与无功设备故障 > 2. SVG 运行环境`

Observed scores:

- Top 1 vector score: 0.696720364396605
- Top 1 keyword score: 0.4
- Top 1 RRF score: 0.03252247488101534
- Top 1 rerank score: 0.9855281710624695

### 今天上海天气怎么样？

Observed behavior:

- The retriever returned weak unrelated PV evidence.
- Rerank scores were very low, with Top 1 around 0.00178.
- This should feed later refusal-threshold and unanswered-question work.
- Refusal logic was intentionally not implemented in this phase.

## Keyword Retrieval Note

Initial verification found that keyword retrieval returned no rows for realistic Chinese questions when using `websearch_to_tsquery` with space-separated jieba tokens. The implementation was adjusted to build a safe OR-style `to_tsquery` parameter from filtered tokens, so terms such as `SVG | 无功 | 补偿 | 异常 | 怎么 | 处理` can contribute keyword candidates without requiring every question token to appear in one segment.

Post-fix evidence:

- `SVG 无功补偿异常怎么处理？` returned Top 5 evidence with non-null keyword scores.
- `逆变器绝缘阻抗低怎么排查？` returned Top 5 evidence with non-null keyword scores.
- Queries with no valid keyword terms skip keyword SQL and fall back to vector retrieval.

## Scope Checklist

- Database tables: covered.
- SQLAlchemy models and Alembic migration: covered.
- Markdown heading-aware chunking: covered.
- Markdown import script: covered.
- SiliconFlow embedding provider: covered.
- pgvector dense retrieval: covered.
- PostgreSQL keyword retrieval: covered.
- RRF fusion: covered.
- SiliconFlow reranker: covered.
- Top 5 evidence CLI output: covered.
- Minimal tests and verification commands: covered.

## Follow-Up Work

- Add QA answer generation endpoint.
- Persist citations into `qa_reference`.
- Add refusal threshold and unanswered-question recording.
- Build a golden QA evaluation set.
- Tune keyword filtering for pure date/weather/business-domain out-of-scope questions.
