# 光伏智能问答系统 Skill 使用规范

> 版本：v1.0  
> 适用阶段：第一阶段（文档知识库 RAG Web MVP）  
> 适用对象：两名开发者、使用 Codex 辅助开发的成员  
> 核心目标：明确什么时候使用什么 skill，降低“每次都不知道该不该用”的模糊感。

---

## 1. 文档目的

本项目会使用 Codex 和若干 skill 辅助开发。skill 的作用不是替代开发者决策，而是帮助团队在不同场景下更稳定地完成规划、设计、实现、检查和重构。

本文档用于回答三个问题：

- 什么时候应该使用 `superpowers`
- 不同开发阶段应该搭配哪些专项 skill
- 每次向 Codex 提 skill 任务时应该怎么描述，才能得到稳定结果

---

## 2. 总体原则

推荐使用方式：

```text
先用 superpowers 管流程。
再按具体任务选择专项 skill。
```

可以把 skill 分成两类：

```text
流程型 skill：帮助决定怎么推进
专项型 skill：帮助完成某类具体任务
```

本项目中建议这样理解：

```text
superpowers：流程、规划、拆分、检查
taskskill：任务拆解、Issue 拆分、验收清单
frontend-design：前端页面设计与实现
graphify：代码调用关系图谱和复杂链路理解
code simplifier：代码跑通后的局部简化和重构
find-skills：需要寻找新 skill 时使用
```

---

## 3. superpowers 什么时候使用

`superpowers` 是本项目最常用的流程型 skill。它适合在“事情还没完全清楚”或“需要把流程走稳”的时候使用。

## 3.1 每个模块开始前必须使用

每进入一个新模块前，建议先使用一次 `superpowers`。

目的：

- 确认模块目标
- 确认本模块包含和不包含什么
- 拆分两个人的任务
- 确认当天文件边界
- 确认共享文件主改人
- 确认完成标准
- 确认 PR 和 Issue 怎么写

推荐提问：

```text
我们要开始 Module 03 API 契约与数据模型。
请使用 superpowers 帮我们确认模块目标、任务拆分、文件边界、共享文件主改人、完成标准和 GitHub Issue/PR 计划。
```

## 3.2 任务超过半天时建议使用

如果一个任务需要改多个文件，或者涉及前后端、数据库、接口、文档中的两类以上，就建议先用 `superpowers`。

适用例子：

- 实现文档上传模块
- 实现 QA ask 接口
- 设计数据库迁移
- 联调问答页和后端接口
- 改接口返回结构
- 补日志和未命中问题记录

推荐提问：

```text
我要实现文档上传模块，涉及后端接口、数据库记录、前端上传页和文档列表。
请使用 superpowers 帮我拆解实现步骤、确认文件边界和验证方式。
```

## 3.3 两个人协作边界不清时必须使用

当出现以下情况时，应使用 `superpowers` 重新整理：

- 两个人可能要改同一个文件
- 不知道谁负责接口文档
- 不知道谁负责 mock 数据
- 不确定模块分支怎么开
- 不确定 PR 是否应该拆开
- 不确定一个功能是否属于当前模块

推荐提问：

```text
现在 Module 04 文档上传与管理里，我们不确定 A 和 B 的文件边界。
请使用 superpowers 帮我们重新划分当天任务、共享文件主改人和冲突预防方案。
```

## 3.4 卡住或混乱时必须使用

如果你们出现“知道要做，但不知道下一步先做什么”的状态，优先使用 `superpowers`。

常见场景：

- 页面已经有了，但不知道接口怎么接
- 后端接口写了一半，但数据库字段不确定
- PR 太大，不知道怎么拆
- 模块做着做着开始偏离第一阶段范围
- 联调问题很多，不知道先修哪个

推荐提问：

```text
我们现在 Module 06 检索与问答主链路有点混乱。
请使用 superpowers 帮我们梳理当前状态、阻塞点、优先级和下一步执行顺序。
```

## 3.5 PR 合并前建议使用

模块 PR 合并前，可以使用 `superpowers` 做一次合并前检查。

检查重点：

- 是否满足模块完成标准
- 是否有未记录的接口变化
- 是否有共享文件未 Review
- 是否有越界功能混入
- 是否有已知问题没有写进 PR
- 是否会阻塞下一模块

推荐提问：

```text
请使用 superpowers 帮我们检查 Module 04 的 PR 是否可以合并。
重点检查完成标准、接口一致性、共享文件变更、已知问题和对下一模块的影响。
```

---

## 4. 各 skill 的推荐使用时机

## 4.1 superpowers

定位：

- 流程总控
- 模块规划
- 协作边界
- PR 检查
- 混乱时重新梳理

最适合：

- 每个模块开始前
- 每次任务超过半天
- 两个人边界不清
- 联调卡住
- PR 合并前

不适合：

- 让它直接决定产品最终范围
- 让它替代人工 Review
- 让它在没有上下文的情况下大范围重写代码

## 4.2 taskskill

定位：

- 任务拆解
- Issue 拆分
- 验收清单
- 每日任务安排

最适合：

- 创建 GitHub Issues
- 拆模块子任务
- 写每日开工清单
- 写模块验收 checklist
- 把一个大任务拆成 3 到 8 个小任务

推荐提问：

```text
请使用 taskskill，把 Module 05 文档解析、切块与入库拆成 GitHub Issues。
要求每个 Issue 都有目标、修改范围、完成标准和验证方式。
```

## 4.3 frontend-design

定位：

- 前端页面设计
- 页面结构
- 视觉风格
- 交互状态
- 可用性打磨

最适合：

- Module 02 前端页面同步实现
- 问答页
- 文档管理页
- 日志页
- 未命中问题页
- loading / empty / error 状态

推荐提问：

```text
请使用 frontend-design，基于 Vue3 + TypeScript + Element Plus，帮我们实现第一阶段 Web MVP 的问答页。
页面要偏运维工作台风格，包含输入框、对话区、引用来源、追问状态、拒答状态和历史会话入口。
```

注意：

- 本项目是光伏运维工具，风格应清晰、稳定、可扫描
- 不需要营销页式 hero
- 不要加入移动端、语音、实时数据等第一阶段之外的功能

## 4.4 graphify

定位：

- 给代码生成调用关系图
- 理解复杂链路
- 辅助定位问题
- 提高 Review 和排查效率

最适合：

- 后端 RAG 链路初步形成后
- 文档解析链路变复杂后
- QA ask 调用链变长后
- 检索、重排、回答生成、引用组装之间关系不清时
- 新成员需要快速理解代码结构时

推荐提问：

```text
请使用 graphify 分析 QA ask 的调用关系。
重点展示从 API 入口到 query 处理、检索、回答生成、引用保存、日志记录的调用链。
```

不建议太早使用：

- 项目刚初始化时
- 只有页面壳或少量 mock 时
- 代码还没有形成稳定调用链时

## 4.5 code simplifier

定位：

- 简化已跑通的代码
- 消除重复
- 降低复杂度
- 改善可读性

最适合：

- 模块已经跑通后
- PR 合并前发现代码太绕
- 某个 service 文件过长
- 前端组件状态过多
- 重复 DTO / 类型 / 工具函数较多

推荐提问：

```text
请使用 code simplifier 简化文档上传模块的后端 service 代码。
要求不改变接口行为，不改数据库结构，只减少重复和提升可读性。
```

重要限制：

- 不要在功能还没跑通前使用
- 不要让它做大范围重构
- 不要让它同时改前端、后端、数据库
- 每次只简化一个模块或一个文件组

## 4.6 find-skills

定位：

- 查找是否有更合适的新 skill
- 帮助安装或评估外部 skill

最适合：

- 你们发现现有 skill 不够用
- 需要测试、部署、Docker、Playwright、CI/CD 等专项能力
- 想找 React / Vue / FastAPI / PostgreSQL 相关 skill

推荐提问：

```text
请使用 find-skills，帮我们找适合 FastAPI 测试或 Vue 前端测试的 skill。
要求优先考虑安装量高、来源可信、适合工程项目的 skill。
```

---

## 5. 按模块推荐使用方式

## 5.1 Module 01：项目底座

推荐 skill：

```text
superpowers
taskskill
```

使用目的：

- 确认项目底座范围
- 确认 Python 虚拟环境创建方式
- 确认后端依赖安装方式
- 确认前端依赖安装方式
- 确认 PostgreSQL + pgvector 等数据库环境
- 确认前后端和数据库启动方式
- 确认项目负责人先创建目录结构并推送仓库
- 确认同事拉取仓库后的环境复现步骤
- 拆 GitHub Issue
- 检查 README、`.env.example`、`docker-compose.yml` 是否足够完整

不建议：

- 此时不需要 graphify
- 此时不需要 code simplifier

推荐提问：

```text
当前模块：Module 01 项目底座
希望使用的 skill：superpowers
目标：确认项目底座的共同环境初始化流程。
补充说明：目录结构由我先创建并推送到 GitHub，同事只需要拉取仓库并按 README 配置；本模块不做 A/B 分工，两个人都要完成 Python 虚拟环境、依赖安装、数据库环境和前后端启动验证。
请帮我们检查项目底座需要包含哪些文件、README 应写哪些步骤、同事如何复现环境、完成标准是什么。
```

## 5.2 Module 02：前端页面同步实现

推荐 skill：

```text
superpowers
frontend-design
taskskill
```

使用目的：

- 用 `superpowers` 确认页面范围和两人边界
- 用 `frontend-design` 设计并实现页面壳
- 用 `taskskill` 拆页面 Issue 和验收清单

输出目标：

- 问答页
- 文档管理页
- 日志页
- 未命中问题页
- mock 数据
- loading / empty / error 状态

## 5.3 Module 03：API 契约与数据模型

推荐 skill：

```text
superpowers
taskskill
```

使用目的：

- 根据前端页面字段反推接口
- 拆接口文档任务
- 确认状态枚举
- 确认核心表
- 确认 QA 返回结构

可选：

```text
find-skills
```

如果需要找 API 文档生成、OpenAPI 或测试相关 skill，可使用。

## 5.4 Module 04：文档上传与管理

推荐 skill：

```text
superpowers
taskskill
```

使用目的：

- 拆上传接口、文档表、前端上传页、状态展示
- 确认共享文件主改人
- 确认上传验证方式

可选：

```text
code simplifier
```

仅在模块跑通后用于简化上传 service 或前端上传组件。

## 5.5 Module 05：文档解析、切块与入库

推荐 skill：

```text
superpowers
taskskill
```

可选 skill：

```text
graphify
code simplifier
```

使用方式：

- 模块开始前用 `superpowers`
- 任务拆分用 `taskskill`
- 解析链路变复杂后用 `graphify`
- 文档解析和切块代码跑通后再用 `code simplifier`

## 5.6 Module 06：检索与问答主链路

推荐 skill：

```text
superpowers
graphify
taskskill
```

可选 skill：

```text
code simplifier
```

使用方式：

- 模块开始前用 `superpowers`
- 复杂调用链形成后用 `graphify`
- QA service 过长或逻辑重复后用 `code simplifier`

重点检查：

- query 处理
- 检索
- 融合排序
- 回答生成
- 引用组装
- 拒答
- 日志

## 5.7 Module 07：会话、日志与未命中问题

推荐 skill：

```text
superpowers
taskskill
```

可选 skill：

```text
graphify
code simplifier
```

使用目的：

- 明确日志写入点
- 明确 trace_id 链路
- 拆历史会话、日志页、未命中问题页
- 后期查看调用关系和简化重复查询逻辑

## 5.8 Module 08：评测、验收与演示

推荐 skill：

```text
superpowers
taskskill
```

可选 skill：

```text
find-skills
```

使用目的：

- 拆验收清单
- 准备 golden QA
- 准备演示流程
- 检查模块完成度
- 如需自动化测试 skill，可用 `find-skills` 查找

---

## 6. 选择 skill 的快速判断表

| 场景 | 推荐 skill |
|---|---|
| 不知道下一步怎么推进 | superpowers |
| 模块刚开始 | superpowers |
| 两个人边界不清 | superpowers |
| PR 合并前检查 | superpowers |
| 要拆 GitHub Issue | taskskill |
| 要写验收 checklist | taskskill |
| 要做前端页面 | frontend-design |
| 页面状态和交互很多 | frontend-design |
| 想看代码调用关系 | graphify |
| 后端链路太复杂 | graphify |
| 代码跑通后想变清爽 | code simplifier |
| 想找新的专项 skill | find-skills |

---

## 7. 向 Codex 提 skill 任务的标准格式

为了减少回答发散，建议每次使用 skill 时都按以下格式描述：

```text
当前模块：
当前目标：
希望使用的 skill：
允许修改的范围：
禁止修改的范围：
已有参考文件：
需要输出什么：
验收标准：
```

示例：

```text
当前模块：Module 02 前端页面同步实现
当前目标：实现问答页页面壳
希望使用的 skill：frontend-design
允许修改的范围：frontend/src/pages, frontend/src/components, frontend/src/mock
禁止修改的范围：backend, 数据库设计文档
已有参考文件：05_前端页面设计.md, 06_二人模块化协作执行规范.md
需要输出什么：可运行的问答页，包含输入、对话、引用、追问、拒答状态
验收标准：页面可用 mock 数据完整演示
```

---

## 8. 不要过度使用 skill

skill 是辅助工具，不是每个小动作都必须使用。

以下情况可以不用 skill：

- 改一个错别字
- 修改一个很小的样式
- 补一个简单字段
- 改一个明确的 bug
- 按已有模式复制一个很小的接口

以下情况应该用 skill：

- 任务会持续半天以上
- 涉及多个文件或多个模块
- 需要两个人协作
- 涉及接口、数据库、页面联调
- 有范围判断和取舍
- PR 合并前需要检查

---

## 9. 一句话规则

如果只记一条规则，就记这条：

**凡是涉及“怎么推进、怎么分工、怎么合并、怎么检查”，先用 `superpowers`；凡是涉及具体专项能力，再叠加对应 skill。**
