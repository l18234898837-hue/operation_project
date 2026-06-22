# QA API 验证记录

## 环境

- 数据库：本地 Windows PostgreSQL 16，数据库 `operation_pv`
- Embedding 模型：`BAAI/bge-m3`
- Rerank 模型：`BAAI/bge-reranker-v2-m3`
- Chat 模型：`deepseek-ai/DeepSeek-V4-Flash`
- Intent 模型：`deepseek-ai/DeepSeek-V4-Flash`
- API 路径：`POST /api/qa/ask`

## 已完成验证

### 单元测试

执行命令：

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests -v
```

结果：

- `99 passed`
- `1 warning`：`fastapi.testclient` 依赖提示 `StarletteDeprecationWarning`，不影响当前功能验证。

覆盖内容：

- QA 配置项读取。
- 数据库模型元数据与 `AnswerType.general_llm`、`AnswerType.refused`。
- SiliconFlow embedding、rerank、chat client payload 与响应解析。
- Query 意图识别、硬规则、LLM JSON 解析、query rewrite、post-validation。
- RAG/general answer prompt。
- QA service 编排、拒答、低置信记录、RAG 引用持久化。
- `/api/qa/ask` endpoint dependency override。
- `backend/scripts/ask_question.py` 导入安全。
- 非法 `session_id` 会在请求校验层返回 422，不会进入真实 answerer。

### 数据库基础连通性

执行端口探测：

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 5432 -InformationLevel Quiet
```

结果：

- 返回 `True`，说明本机 PostgreSQL 5432 端口可达。

执行 `psycopg` 直连探测：

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 -c "import psycopg; from app.core.config import settings; conn=psycopg.connect(host=settings.db_host, port=settings.db_port, dbname=settings.db_name, user=settings.db_user, password=settings.db_password, connect_timeout=5); cur=conn.execute('select 1'); print(cur.fetchone()[0]); conn.close()"
```

结果：

- 返回 `1`，说明当前 `.env` 中的 PostgreSQL 主机、端口、数据库、用户和密码可用于 `psycopg` 直连。

## 当前受阻项

### Alembic / SQLAlchemy 建连超时

尝试执行：

```powershell
cd D:\桌面\文件\operation_project\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
```

结果：

- 命令超时。

进一步尝试 SQLAlchemy `create_engine(...).connect()` 也超时；但 `psycopg.connect(...)` 可以成功 `select 1`。

当前判断：

- 数据库服务本身可达。
- 账号密码本身可用。
- 受阻点集中在 SQLAlchemy/Alembic 的建连路径，需要在本机终端继续复核。
- 已将 `Settings.database_url` 改为 SQLAlchemy `URL.create(...)`，避免数据库密码包含 `@`、`/`、`#`、`:` 等特殊字符时被 URL 字符串误解析。

## 手动验证方式

### 1. 执行迁移

在项目根目录执行：

```powershell
cd D:\桌面\文件\operation_project\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
cd ..
```

期望：

- Alembic 成功升级到最新版本。
- PostgreSQL enum `answer_type` 包含 `general_llm` 和 `refused`。

### 2. 验证 RAG 问题

如果当前目录在项目根目录，执行：

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\ask_question.py "逆变器绝缘阻抗低怎么排查？"
```

如果当前目录已经在 `backend`，执行：

```powershell
python.exe -X utf8 scripts\ask_question.py "逆变器绝缘阻抗低怎么排查？"
```

期望：

- `answer_type` 为 `rag`。
- `intent` 为 `knowledge_base_qa`。
- `references` 非空。
- `decision.used_knowledge_base` 为 `true`。

### 3. 验证通用解释问题

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\ask_question.py "什么是无功功率？"
```

如果当前目录已经在 `backend`，路径改为 `scripts\ask_question.py`。

期望：

- 通常为 `general_llm`，且 `references` 为空。
- 如果意图识别认为本地知识库覆盖该问题，也可能走 `rag`，此时必须带引用。

### 4. 验证实时外部问题拒答

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\ask_question.py "今天上海天气怎么样？"
```

如果当前目录已经在 `backend`，路径改为 `scripts\ask_question.py`。

期望：

- `answer_type` 为 `refused`。
- `intent` 为 `realtime_external`。
- `references` 为空。
- `decision.refusal_reason` 为 `realtime_external`。

### 5. 验证持久化结果

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
- 实时外部或低置信问题会增加 `qa_record` 和 `qa_unanswered`。

## 注意事项

- 不要把真实 SiliconFlow API Key 写入 `.env.example` 或提交到 Git。
- 如果 SiliconFlow chat completion 超时，可以在 `.env` 中调大 `MODEL_API_TIMEOUT_SECONDS`，例如 `300`。
- `general_llm` 答案必须保持 `references=[]`，表示未使用项目知识库。
- `rag` 答案必须带证据引用。
- 低于 `QA_RERANK_MIN_SCORE` 的知识库问题应该拒答并进入 `qa_unanswered`。
