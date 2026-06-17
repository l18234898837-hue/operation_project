# 光伏智能问答系统

第一阶段目标是交付一个面向光伏运维场景的文档知识库 RAG Web MVP：管理员可以上传文档，系统完成解析、切块、向量化和入库，用户可以基于文档证据提问并获得带来源引用的回答。

## 技术栈

- 后端：FastAPI、SQLAlchemy 2.0、Pydantic、PostgreSQL 16、pgvector
- 前端：Vue 3、TypeScript、Vite、Element Plus、Pinia、Vue Router
- 检索：FAQ 优先匹配、关键词检索、向量检索、RRF 融合排序
- 模型：通过 API 配置 chat provider 和 embedding provider

## 目录结构

详细目录说明见 [docs/项目目录结构说明.md](docs/项目目录结构说明.md)。

## 后端启动

```powershell
cd D:\桌面\文件\operation_project
python -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
Copy-Item .env.example .env
cd backend
uvicorn app.main:app --reload
```

健康检查：

```text
GET http://127.0.0.1:8000/health
GET http://127.0.0.1:8000/api/health
```

## 前端启动

```powershell
cd D:\桌面\文件\operation_project\frontend
npm install
npm run dev
```

默认访问：

```text
http://127.0.0.1:5173
```

## 数据库准备

建议本地使用 PostgreSQL 16，并在项目数据库中启用：

```sql
CREATE DATABASE operation_pv;
\c operation_pv
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

## 当前初始化状态

当前提交只建立项目底座和目录规范，不包含真实 RAG 链路、数据库迁移、文档解析或页面业务实现。后续按正式参考文件中的 Module 01 至 Module 08 逐步推进。
