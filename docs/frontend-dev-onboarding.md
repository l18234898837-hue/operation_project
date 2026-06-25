# 前端联调上手指南

这份文档给前端开发者使用，目标是从一份新拉取的代码开始，完成本地数据库、后端、前端和问答功能联调。

## 1. 环境准备

建议版本：

- Node.js 20+
- Python 3.12+
- Docker Desktop
- Git

项目默认端口：

- 前端 Vite: `http://127.0.0.1:5173`
- 后端 FastAPI: `http://127.0.0.1:8000`
- PostgreSQL: `127.0.0.1:5432`
- Redis: `127.0.0.1:6379`

## 2. 拉取代码

```powershell
git clone <你的仓库地址>
cd operation_project
```

如果已经有仓库：

```powershell
git pull
```

## 3. 配置环境变量

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

本地使用 `docker-compose.yml` 启动数据库时，建议 `.env` 至少确认这些值：

```env
APP_PORT=8000

DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=operation_pv
DB_USER=postgres
DB_PASSWORD=postgres

LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_API_KEY=你的 SiliconFlow Key
LLM_MODEL=deepseek-ai/DeepSeek-V4-Flash

EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_API_KEY=你的 SiliconFlow Key
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIMENSION=1024

RERANK_BASE_URL=https://api.siliconflow.cn/v1
RERANK_API_KEY=你的 SiliconFlow Key
RERANK_MODEL=BAAI/bge-reranker-v2-m3
RERANK_ENABLED=true
```

联调时建议打开 QA 调试日志：

```env
QA_DEBUG_LOG_ENABLED=true
QA_DEBUG_EVIDENCE_PREVIEW_ENABLED=true
```

## 4. 启动数据库和 Redis

项目已经提供 Docker Compose，本地直接启动即可：

```powershell
docker compose up -d postgres redis
```

首次启动 PostgreSQL 时会自动执行：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

检查容器状态：

```powershell
docker compose ps
```

如果数据库容器已经存在但密码或初始化脚本改过，需要重建数据卷：

```powershell
docker compose down -v
docker compose up -d postgres redis
```

注意：`down -v` 会删除本地数据库数据。

## 5. 安装后端依赖

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
pip install -r backend\requirements-dev.txt
```

之后每次打开新终端运行后端命令前，先激活虚拟环境：

```powershell
.\backend\.venv\Scripts\Activate.ps1
```

## 6. 迁移数据库

进入后端目录执行 Alembic 迁移：

```powershell
cd backend
alembic upgrade head
cd ..
```

当前迁移会创建 RAG 知识库、问答、引用、追踪等相关表。

如果想确认迁移状态：

```powershell
cd backend
alembic current
alembic history
cd ..
```

## 7. 导入知识库

问答功能依赖知识库数据。默认导入脚本会读取：

```text
data/knowledge_base/markdown
```

仓库里已经有一批 Markdown 示例知识库文件。确认 `.env` 中 `EMBEDDING_API_KEY` 已配置后执行：

```powershell
cd backend
python scripts\import_knowledge_base.py
cd ..
```

导入成功时终端会输出类似：

```text
imported 01_逆变器故障与维护.md -> <document_id>
```

如果导入失败，优先检查：

- PostgreSQL 是否已启动。
- `alembic upgrade head` 是否已执行。
- `.env` 中 `EMBEDDING_API_KEY` 是否有效。
- `EMBEDDING_DIMENSION` 是否和模型一致，当前默认是 `1024`。

## 8. 启动后端

```powershell
.\backend\.venv\Scripts\Activate.ps1
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

健康检查：

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/api/health
```

问答接口：

```text
POST http://127.0.0.1:8000/api/qa/ask
POST http://127.0.0.1:8000/api/qa/ask/stream
```

前端当前使用流式接口 `/api/qa/ask/stream`。

## 9. 启动前端

另开一个终端：

```powershell
cd frontend
npm install
npm run dev
```

访问：

```text
http://127.0.0.1:5173
```

Vite 已配置代理：

```text
/api -> http://127.0.0.1:8000
```

所以前端开发时不需要手动改接口域名。

## 10. 开始使用对话功能

1. 打开 `http://127.0.0.1:5173`。
2. 登录页面选择普通用户或管理员角色。
3. 进入问答页。
4. 输入和知识库相关的问题，例如：

```text
逆变器频繁告警应该怎么排查？
组件发电效率下降有哪些常见原因？
线缆绝缘故障怎么处理？
```

5. 页面会流式展示回答。
6. 回答完成后，如果后端检索到可展示引用，底部会显示引用文档文件名。
7. 左侧历史会话支持搜索、新建、删除；刷新页面后历史会话会保留在浏览器本地。

## 11. 命令行快速验证问答

如果想绕过前端先确认后端问答链路：

```powershell
.\backend\.venv\Scripts\Activate.ps1
cd backend
python scripts\stream_chat_qa.py
```

输入问题后会在终端看到流式输出。输入 `/exit` 退出。

## 12. 常见问题

### 后端启动后问答报数据库连接失败

检查 Docker 容器是否启动：

```powershell
docker compose ps
```

检查 `.env`：

```env
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=operation_pv
DB_USER=postgres
DB_PASSWORD=postgres
```

### 问答没有引用

优先检查是否导入过知识库：

```powershell
cd backend
python scripts\import_knowledge_base.py
```

也要确认提问和知识库内容相关。当前引用展示由后端根据检索和 rerank 分数决定，分数过低时不会展示。

### 终端看不到 QA 调试日志

确认 `.env`：

```env
QA_DEBUG_LOG_ENABLED=true
QA_DEBUG_EVIDENCE_PREVIEW_ENABLED=true
```

然后重启后端。联调时后端终端会输出 `qa_debug` 单行日志。

### 前端请求 404 或连接失败

确认后端运行在：

```text
http://127.0.0.1:8000
```

确认前端通过 Vite 启动，而不是直接打开 `index.html`：

```powershell
cd frontend
npm run dev
```

### 修改 `.env` 后不生效

后端配置在启动时读取。修改 `.env` 后需要重启 `uvicorn`。

## 13. 推荐联调顺序

第一次本地上手建议按这个顺序：

1. `docker compose up -d postgres redis`
2. `Copy-Item .env.example .env`
3. 修改 `.env` 中数据库密码和模型 API Key。
4. 安装后端依赖。
5. `alembic upgrade head`
6. `python scripts\import_knowledge_base.py`
7. `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
8. `cd frontend && npm install && npm run dev`
9. 打开 `http://127.0.0.1:5173` 开始问答。
