# RAG 知识库最小闭环流程说明

本文用于帮助理解当前项目里已经搭起来的第一阶段 RAG 知识库流程。它不是接口文档，而是一份“从知识库 Markdown 到 Top 5 证据片段”的完整链路说明，并附带手动验证方法。

## 1. 当前阶段做到了什么

当前已经完成的是 RAG 知识库的最小闭环：

1. 读取已经整理好的 Markdown 知识库文档。
2. 按标题树和内容语义切成 chunk。
3. 为每个 chunk 生成 `indexed_text` 和 `keyword_text`。
4. 调用 SiliconFlow 的 `BAAI/bge-m3` 生成 1024 维 embedding。
5. 将文档、切片、向量、关键词文本写入本地 Windows PostgreSQL 16。
6. 查询时同时走向量检索和 PostgreSQL 关键词检索。
7. 用 RRF 将两路结果融合。
8. 调用 SiliconFlow 的 `BAAI/bge-reranker-v2-m3` 做重排序。
9. 输出 Top 5 证据片段，为后续问答接口提供依据。

暂时还没有做完整问答接口、前端页面、多轮会话、权限系统、Docker 部署、拒答阈值等。这一阶段的目标是先确认“知识能入库，问题能检索，证据能返回”。

## 2. 技术路线

已确认并落地的路线如下：

- 数据库：本地 Windows PostgreSQL 16，数据库名 `operation_pv`
- 向量扩展：pgvector
- Embedding 模型：`BAAI/bge-m3`
- Embedding 维度：1024
- Embedding 调用方：SiliconFlow API
- 关键词检索：PostgreSQL full-text search，检索 `kb_document_segment.keyword_text`
- 融合排序：RRF
- Reranker：`BAAI/bge-reranker-v2-m3`
- Reranker 调用方：SiliconFlow API
- Chat 模型预留：`deepseek-ai/DeepSeek-V4-Flash`

## 3. 核心文件位置

和 RAG 最小闭环直接相关的文件主要是：

- `backend/app/models/rag.py`
  定义 RAG 相关 SQLAlchemy models。

- `backend/alembic/versions/20260621_0001_create_rag_tables.py`
  创建 RAG 表、pgvector、pg_trgm 和索引。

- `backend/app/services/markdown_chunker.py`
  Markdown 标题树解析和切片逻辑。

- `backend/app/services/keyword_index.py`
  查询和文本的关键词分词逻辑。

- `backend/app/services/siliconflow.py`
  SiliconFlow embedding 和 rerank 客户端。

- `backend/app/services/ingest.py`
  知识库 Markdown 导入流程。

- `backend/app/services/retrieval.py`
  向量检索、关键词检索、RRF 融合、rerank 编排。

- `backend/scripts/import_knowledge_base.py`
  手动导入知识库的 CLI 脚本。

- `backend/scripts/query_knowledge_base.py`
  手动查询 Top 5 证据片段的 CLI 脚本。

- `docs/rag-minimum-loop-verification.md`
  已执行过的验证结果记录。

## 4. 数据库表怎么理解

当前 RAG 核心表包括：

- `kb_document`
  一篇原始知识库文档对应一条记录，例如“逆变器故障与维护”“SVG与无功设备故障”。

- `kb_document_segment`
  一个 chunk 对应一条记录。这里是检索的核心表，包含标题路径、原始文本、清洗文本、索引文本、关键词文本和 embedding。

- `parse_task`
  记录文档解析和入库任务状态。

- `faq_item`
  预留 FAQ 形式问答。

- `qa_session`
  预留会话记录。

- `qa_record`
  预留问答记录。

- `qa_reference`
  预留答案引用证据记录。

- `qa_unanswered`
  预留无法回答或低置信问题记录。

第一阶段真正频繁使用的是 `kb_document` 和 `kb_document_segment`。后面的 `qa_*` 表是为了下一阶段完整问答链路准备的。

## 5. 入库流程

入库脚本是：

```powershell
backend\.venv\Scripts\python.exe backend\scripts\import_knowledge_base.py
```

整体流程如下：

1. 从项目根目录下的 `data/knowledge_base/markdown` 目录读取 `.md` 文件。
2. 每个 Markdown 文件先计算 SHA256。
3. 如果相同 SHA256 的文档已经入库，就跳过重复 embedding，避免反复调用 API。
4. Markdown 内容进入标题树解析器。
5. 解析器根据 `#`、`##`、`###`、`####` 等标题生成 `heading_path`。
6. 按切片策略生成 chunks。
7. 每个 chunk 生成：
   - `heading_path`
   - `raw_text`
   - `clean_text`
   - `indexed_text`
   - `keyword_text`
8. 批量调用 SiliconFlow `BAAI/bge-m3` 得到 1024 维向量。
9. 写入 `kb_document`、`parse_task`、`kb_document_segment`。
10. 文档状态变为 `ready`。

## 6. 切片策略怎么理解

当前切片不是简单按固定字数硬切，而是尽量尊重 Markdown 的标题结构。

核心规则：

1. 解析 Markdown 标题树，得到类似这样的标题路径：

```text
逆变器故障与维护 > 常见故障与处理 > PV 过压
```

2. 优先以最小有意义 section 为单位，一般优先使用 `###` 或 `####` 下的完整内容。

3. 如果一个 section 在 250 到 1000 字之间，直接作为一个 chunk。

4. 如果 section 小于 250 字，会尝试和相邻同级 section 或父级说明合并，但不能跨越不同故障主题。

5. 如果 section 超过 1000 字，会继续按段落、小标题、列表组拆分，目标长度约 500 到 800 字。

6. 每个 chunk 的 `indexed_text` 会拼接标题路径和正文。

7. overlap 只用于长文本拆分，短 section 和列表型 chunk 不强制 overlap。

这样做的目的，是让每个 chunk 尽量保持一个完整故障主题，而不是把“原因”“处理方法”“注意事项”切散到难以理解的碎片里。

## 7. indexed_text 和 keyword_text 的区别

### indexed_text

`indexed_text` 是用于 embedding 和语义检索的文本。它包含标题路径和正文，例如：

```text
逆变器故障与维护 > 常见故障与处理 > 漏电流故障
资料中解释，漏电流是逆变器检测到对地异常电流...
```

它的作用是让 embedding 模型不仅看到正文，还看到这段内容属于哪个主题。

### keyword_text

`keyword_text` 是用于 PostgreSQL 关键词检索的文本。它会经过分词和技术词保留，例如：

```text
逆变器 故障 维护 漏电流 绝缘 电缆 接头 PV1 SVG 10kV
```

它的作用是让关键词检索更容易命中中文词、设备名、故障码、技术缩写。

## 8. 查询流程

查询脚本是：

```powershell
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\query_knowledge_base.py "SVG 无功补偿异常怎么处理？"
```

整体流程如下：

1. 接收用户问题。
2. 规范化问题文本，压缩多余空白。
3. 调用 `BAAI/bge-m3` 为问题生成 query embedding。
4. 用 pgvector 做 dense 向量检索。
5. 对问题做关键词分词，生成 PostgreSQL tsquery。
6. 用 PostgreSQL full-text search 做关键词检索。
7. 将两路结果转为统一候选：
   - vector candidate
   - keyword candidate
8. 用 RRF 融合两路候选。
9. 取融合后的候选片段，送入 `BAAI/bge-reranker-v2-m3`。
10. 按 rerank 分数重新排序。
11. 输出 Top 5 证据片段。

## 9. 向量检索如何工作

向量检索使用 `kb_document_segment.embedding` 字段。

查询时：

1. 用户问题先生成 1024 维 query embedding。
2. PostgreSQL 使用 pgvector 的 cosine distance：

```sql
embedding <=> :query_embedding
```

3. 距离越小，语义越相似。
4. 代码中会转换为类似相似度的 `vector_score`。

向量检索擅长找到语义相近的内容，即使问题和原文不是完全相同的词，也可能命中。

## 10. 关键词检索如何工作

关键词检索使用 `kb_document_segment.keyword_text` 字段。

用户问题会先分词，例如：

```text
SVG 无功补偿异常怎么处理？
```

可能会变成：

```text
SVG 无功 补偿 异常 怎么 处理
```

然后构造成 OR 风格的 PostgreSQL tsquery：

```text
SVG | 无功 | 补偿 | 异常 | 怎么 | 处理
```

这样只要片段命中其中一部分关键词，就能进入候选；命中更多、更重要的片段分数会更高。

这里曾经修过一个关键问题：最初使用 `websearch_to_tsquery` 时，空格分词更接近“全部都要命中”，导致“怎么”“处理”“排查”等问句词不在文档里时，关键词检索可能一条结果都没有。现在已经改为安全的 OR-style `to_tsquery` 参数，并且空查询会跳过关键词检索，直接退回向量检索。

## 11. RRF 融合怎么理解

RRF 全称 Reciprocal Rank Fusion，用来融合多个排序列表。

当前有两个排序列表：

- 向量检索列表
- 关键词检索列表

RRF 不直接比较 `vector_score` 和 `keyword_score` 的绝对大小，因为这两个分数不是一个尺度。它更关注“某个候选在各自列表里排第几”。

简化理解：

```text
RRF 分数 = 1 / (k + 向量排名) + 1 / (k + 关键词排名)
```

如果一个片段同时在向量检索和关键词检索里排得比较靠前，它的 RRF 分数就会更高。

这很适合当前路线：

- 向量检索补语义
- 关键词检索补精确术语
- RRF 把两者稳妥融合

## 12. Reranker 的作用

RRF 后得到的是候选证据，但它还不是最终最优顺序。

Reranker 会拿到：

- 用户问题
- 候选 chunk 文本列表

然后判断每个 chunk 与问题的相关性。

当前使用：

```text
BAAI/bge-reranker-v2-m3
```

最终 CLI 输出里的 `rerank_score` 就是重排序模型给出的相关性分数。

通常可以这样理解：

- `vector_score`：语义向量相似度
- `keyword_score`：关键词命中相关性
- `rrf_score`：两路检索融合后的分数
- `rerank_score`：最终证据排序更应关注的分数

## 13. 当前验证结果

当前已经导入：

- 文档数：9
- 切片数：93
- 文档状态：9 个都是 `ready`

各文档切片数量：

- SVG与无功设备故障：8
- 安全风险与应急处理：8
- 变压器箱变与电气设备：10
- 发电量异常与效率损失：12
- 逆变器故障与维护：14
- 线缆接头与绝缘故障：7
- 巡检检测与预防维护：10
- 运维管理制度与人员配置：12
- 组件故障与低效问题：12

全量单元测试结果：

```text
58 passed
```

## 14. 两个典型查询结果

### SVG 无功补偿异常怎么处理？

Top 5 heading：

1. `04_SVG与无功设备故障 > 5. 电网电压异常保护`
2. `04_SVG与无功设备故障 > 3. SVG 装置停止工作`
3. `04_SVG与无功设备故障 > 6. 通信故障`
4. `04_SVG与无功设备故障 > 7. 运行中停机`
5. `04_SVG与无功设备故障 > 2. SVG 运行环境`

Top 1 分数：

- `vector_score`: 0.696720364396605
- `keyword_score`: 0.4
- `rrf_score`: 0.03252247488101534
- `rerank_score`: 0.9855281710624695

这说明 SVG 查询已经同时命中了向量检索和关键词检索，并经过 reranker 确认为高相关。

### 逆变器绝缘阻抗低怎么排查？

Top 5 heading：

1. `03_线缆接头与绝缘故障 > 4. 绝缘阻抗问题`
2. `01_逆变器故障与维护 > 3. 常见故障与处理 > 3.2 电网过压或欠压`
3. `01_逆变器故障与维护 > 3. 常见故障与处理 > 3.3 漏电流故障`
4. `01_逆变器故障与维护 > 3. 常见故障与处理 > 3.7 逆变器效率与线损检查`
5. `01_逆变器故障与维护 > 3. 常见故障与处理 > 3.1 PV 过压`

Top 1 分数：

- `vector_score`: 0.6402819156646729
- `keyword_score`: 0.5
- `rrf_score`: 0.03252247488101534
- `rerank_score`: 0.8569533824920654

这说明系统能把“逆变器绝缘阻抗低”正确拉到“线缆接头与绝缘故障”的相关片段。

## 15. 域外问题的当前表现

测试问题：

```text
今天上海天气怎么样？
```

当前系统仍会返回弱相关 PV 证据，但 rerank 分数非常低，Top 1 大约是：

```text
0.00178
```

这说明当前检索链路能暴露“相关性很弱”的信号，但还没有做拒答逻辑。下一阶段可以基于 rerank 分数阈值实现：

- 低于阈值时不回答。
- 写入 `qa_unanswered`。
- 提示用户换成光伏运维相关问题。

## 16. 手动验证前的准备

请确认：

1. PostgreSQL 16 正在运行。
2. 数据库 `operation_pv` 存在。
3. `.env` 已填写本地数据库连接信息。
4. `.env` 已填写 SiliconFlow API Key。
5. `.env` 中 embedding/rerank 配置类似如下：

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
```

注意：不要把真实 API Key 提交到 Git。

## 17. 手动验证方式

以下命令都在项目根目录执行：

```powershell
cd D:\桌面\文件\operation_project
```

### 17.1 验证单元测试

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests -v
```

期望结果：

```text
58 passed
```

### 17.2 验证数据库迁移

```powershell
cd D:\桌面\文件\operation_project\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
cd ..
```

期望结果：

- 命令无报错。
- RAG 表已经存在。

### 17.3 验证知识库导入

```powershell
backend\.venv\Scripts\python.exe backend\scripts\import_knowledge_base.py
```

期望结果：

- 输出每个 Markdown 文档对应的 document id。
- 如果文档已经导入过，重复执行时会复用已有文档，避免重复 embedding。

### 17.4 验证数据库文档和切片数量

使用 Python 方式检查，避免 PowerShell/psql 中文编码干扰：

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
@'
from sqlalchemy import text
from app.db.session import SessionLocal

with SessionLocal() as session:
    documents = session.execute(text("SELECT COUNT(*) FROM kb_document")).scalar_one()
    segments = session.execute(text("SELECT COUNT(*) FROM kb_document_segment")).scalar_one()
    statuses = session.execute(text("SELECT status::text, COUNT(*) FROM kb_document GROUP BY status::text ORDER BY status::text")).all()

    print("documents =", documents)
    print("segments =", segments)
    print("statuses =", [(row[0], row[1]) for row in statuses])

    rows = session.execute(text("""
        SELECT d.title, COUNT(s.id) AS segment_count
        FROM kb_document d
        LEFT JOIN kb_document_segment s ON s.document_id = d.id
        GROUP BY d.title
        ORDER BY d.title
    """)).all()

    for row in rows:
        print(row.title, row.segment_count)
'@ | backend\.venv\Scripts\python.exe -X utf8 -
```

期望结果：

```text
documents = 9
segments = 93
statuses = [('ready', 9)]
```

### 17.5 验证 SVG 查询

```powershell
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\query_knowledge_base.py "SVG 无功补偿异常怎么处理？"
```

你应该关注：

- Top 5 是否主要来自 `04_SVG与无功设备故障`。
- 输出里是否有 `keyword_score`，并且不是 `None`。
- `rerank_score` 是否较高。

一个正常结果通常会包含：

```text
04_SVG与无功设备故障 > 5. 电网电压异常保护
keyword_score=0.4
rerank_score=0.98...
```

### 17.6 验证逆变器绝缘阻抗查询

```powershell
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\query_knowledge_base.py "逆变器绝缘阻抗低怎么排查？"
```

你应该关注：

- Top 1 是否接近 `03_线缆接头与绝缘故障 > 4. 绝缘阻抗问题`。
- 是否有 `keyword_score`。
- `rerank_score` 是否明显高于域外问题。

### 17.7 验证域外问题

```powershell
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\query_knowledge_base.py "今天上海天气怎么样？"
```

当前预期：

- 仍可能返回一些 PV 相关片段。
- 但是 `rerank_score` 应该很低。
- 这说明后续需要加拒答阈值，而不是说明当前检索失败。

## 18. 如何判断验证通过

你可以按下面标准判断：

1. 单元测试通过。
2. 数据库中有 9 篇文档、93 个切片。
3. `kb_document` 中 9 篇文档都是 `ready`。
4. SVG 查询 Top 5 与 SVG、无功补偿、电网电压、通信故障等相关。
5. 逆变器绝缘阻抗查询 Top 1 与绝缘阻抗、线缆、接地等相关。
6. 正常业务问题有非空 `keyword_score`。
7. 正常业务问题 rerank 分数明显高于域外问题。

如果以上都满足，说明 RAG 最小闭环是可用的。

## 19. 常见问题

### 19.1 PowerShell 显示中文乱码怎么办？

文件本身是 UTF-8，但 PowerShell 有时显示会乱。建议：

- 脚本命令使用 `python.exe -X utf8`。
- 文档用 VS Code 或支持 UTF-8 的编辑器打开。
- 数据库检查优先用 Python 脚本，而不是直接在 PowerShell 里拼中文 SQL。

### 19.2 为什么重复导入没有生成更多切片？

导入时会根据文件 SHA256 判断是否已经入库。相同文件不会重复 embedding 和重复写入，这是为了节省 API 调用和避免重复数据。

### 19.3 为什么天气问题也会返回内容？

因为当前阶段只做检索，不做拒答。向量检索总会尽量找“最像”的内容，即使问题不属于光伏运维领域。这个问题后续要通过 rerank 阈值和 `qa_unanswered` 机制解决。

### 19.4 为什么要同时做向量检索和关键词检索？

向量检索擅长语义相似，关键词检索擅长术语和设备名精确命中。两者结合后，比单独使用其中一种更稳。

## 20. 下一阶段建议

推荐下一阶段按这个顺序推进：

1. 加一个正式问答接口。
2. 将 Top 5 证据传给 chat 模型生成答案。
3. 将引用片段写入 `qa_reference`。
4. 设置 rerank 拒答阈值。
5. 低置信问题写入 `qa_unanswered`。
6. 做一批人工标注的黄金问答集，用来评估召回和回答质量。
