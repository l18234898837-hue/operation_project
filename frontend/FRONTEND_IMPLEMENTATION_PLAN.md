# 光伏智能问答系统前端实现方案

> 分支：`front`  
> 适用阶段：第一阶段 Web MVP  
> 参考资料：`正式参考文件/前端页面设计图`、`正式参考文件/05_前端页面设计.md`、`正式参考文件/第一阶段功能清单.md`、`docs/RAG问答接口闭环流程说明.md`

## 1. 目标与结论

第一阶段前端要交付的不是完整运营后台，而是一个可演示、可联调、可追踪的光伏运维 RAG 问答 Web MVP。

核心目标：

- 普通用户可以登录后进入问答页，提出光伏运维问题。
- 系统可以调用当前已完成的 `POST /api/qa/ask`，展示回答、引用、置信度和拒答状态。
- 管理员可以进入问答、文档管理、问答日志页面，看到设计图中的工作台结构。
- 文档管理和日志页第一阶段先实现目标态 UI 与 mock 数据，等待后端补齐接口后再切换真实数据。
- 前端视觉以设计图为准，采用浅色、蓝白、光伏工业科技风，而不是当前代码里的深色绿色风格。

## 2. 已使用的 skills 与方法

本方案按以下工作流整理：

- `superpowers:brainstorming`：先分析目标、范围、约束和设计取舍，不直接进入编码。
- `frontend-design`：分析页面视觉方向、布局、组件和交互状态。
- `superpowers:writing-plans`：把方案整理为可执行的分阶段实现文档。

## 3. 设计图分析

### 3.1 登录页

参考图：`1登录页.png`

页面特征：

- 中央登录卡片，背景是低透明度光伏电站线稿。
- 机器人 logo 位于顶部，标题为“光伏智能问答系统”。
- 表单包含账号、密码、角色选择、记住账号、忘记密码、授权说明。
- 角色有普通用户和管理员两个入口。
- 主视觉是蓝白渐变、柔和阴影和玻璃拟态边框。

实现建议：

- 登录页独立于 AppShell，不显示侧边栏。
- 第一阶段继续使用本地 mock 登录，不做真实鉴权。
- 登录成功后写入 `localStorage` 和 Pinia：`role=user|admin`。
- 普通用户跳转 `/chat`，管理员跳转 `/admin/chat` 或 `/chat?role=admin`。
- 授权说明先做弹窗占位，内容来自产品边界说明。

### 3.2 普通用户问答页

参考图：`2-1用户问答页-空状态.png`、`2-1用户问答页-问答状态.png`

页面特征：

- 左侧为会话历史侧栏，包含搜索、今天/昨天/更早分组和用户信息。
- 右侧为问答主区域。
- 空状态包含机器人图标、问候语、纯文字推荐问题按钮。
- 问答状态包含顶部问题标题、用户气泡、机器人回答卡片、引用来源折叠区、复制按钮；仅当前会话最新一条助手回答显示重新生成按钮，历史助手回答只保留复制。
- 输入框固定在底部。

实现建议：

- 普通用户只保留会话侧栏和问答主区域，不展示管理员导航。
- 推荐问题点击后可以直接发送。
- 初期会话历史使用本地状态或 mock 数据。
- 回答卡片要支持 `rag`、`general_llm`、`refused`、`none` 四种回答类型。
- 引用区映射当前后端 `references` 字段，展示 `heading_path`、`excerpt`、`rerank_score`。

### 3.3 管理员问答页

参考图：`2-2管理员问答页-空状态.png`、`2-2管理员问答页-问答状态.png`

页面特征：

- 比普通用户多一列最左侧应用导航。
- 导航包含问答、文档管理、问答日志。
- 中间仍然保留会话历史侧栏。
- 右侧问答主区域与普通用户一致。

实现建议：

- 管理员布局拆成 `AdminShell`：左侧应用导航 + 页面内容。
- 问答页内部复用 `ChatWorkspace`，避免用户端和管理员端复制两套问答逻辑。
- 管理员问答页可以显示更多状态徽标，但不要把检索调试信息塞进普通问答卡片。

### 3.4 文档管理页

参考图：`3文档管理页面.png`

页面特征：

- 左侧是管理员应用导航，第二列是文档分类侧栏。
- 主区域包含统计卡片、筛选栏、文档表格、分页。
- 状态包括全部文档、解析中、解析失败、已启用。
- 表格字段包括文档名称、类型、解析状态、启用状态、更新时间、失败原因、操作。

当前后端状态：

- 已有数据库模型和导入脚本。
- 暂无 `POST /api/documents/upload`、`GET /api/documents/list` 等真实 API。

实现建议：

- 第一阶段先做 mock UI。
- 字段和交互按后续接口预留。
- 上传按钮先弹出“接口待接入”或仅做前端模拟新增。
- 解析失败可打开失败原因弹窗。

### 3.5 问答日志页

参考图：`4问答日志页.png`

页面特征：

- 主区域顶部有统计卡片：全部记录、已回答、证据不足、拒答、低置信度、高耗时。
- 中部有分类 tab、搜索和筛选。
- 日志表格字段包括问题、回答类型、状态、置信度、trace_id、引用片段数、总耗时、时间、处理状态。
- 右侧有日志详情抽屉，展示问答摘要、链路信息、引用片段、阶段耗时、知识缺口判断和处理按钮。

当前后端状态：

- `qa_record`、`qa_reference`、`qa_unanswered` 已写入。
- 暂无 `GET /api/logs/qa`、`GET /api/unanswered` 查询接口。

实现建议：

- 第一阶段日志页使用 mock 数据还原目标态。
- 真实 API 完成后只替换 `api/logs.ts` 和 store。
- 右侧详情抽屉字段对齐 `qa_record.decision_metadata`、`trace_id`、`latency_ms`、`references`。

## 4. 当前代码现状

当前前端已经具备：

- Vue 3 + TypeScript + Vite + Vue Router + Pinia + Element Plus。
- Vite 已配置 `/api` 代理到 `http://127.0.0.1:8000`。
- 路由入口：`/login`、`/chat`、`/admin/chat`、`/admin/documents`、`/admin/logs`。旧 `/admin/unanswered` 仅作为兼容路径重定向到 `/admin/logs`，不再暴露独立导航入口。
- 登录页已按设计图校正为居中单卡片结构，使用项目图标库和透明背景 logo，密码显示/隐藏可交互。
- `/chat` 已实现普通用户全屏问答工作区，包含历史会话、推荐问题、消息流、底部输入框、真实 `POST /api/qa/ask` 调用、引用展示、复制、重试和反馈入口。
- `/admin/chat` 已接入 `AdminShell`，复用普通用户问答组件和 `chat` store，避免重复实现问答链路。
- 管理端最左侧导航已独立为 `AdminNav`，支持折叠/展开；展开和折叠时都使用贴左边缘的同尺寸浮动按钮，折叠后左栏宽度为 0，并把状态写入 `localStorage`。
- 已建立 `api/`、`types/`、`stores/`、`components/`、`layouts/`、`chat/`、`styles/` 分层。

主要差距：

- 文档管理页和问答日志页已按设计图完成第一版 mock 可操作链路；未命中问题当前收敛到问答日志详情中的知识缺口处理能力，不再作为设计图之外的独立页面推进。
- 会话历史仍使用本地状态，等待后端补齐 `GET /api/sessions` 后再切换真实数据源。
- 角色权限仍是本地 mock 分流，尚未接入真实鉴权。
- 日志和文档管理页已完成前端 mock store/api 预留，等待后端真实接口替换；未命中问题暂无真实 HTTP API，当前只在日志详情中保留候选处理入口。
- `frontend/package-lock.json` 当前有本地漂移，不建议作为本次方案提交内容，除非确认依赖变更确实需要提交。

## 5. 前端架构方案

### 5.1 推荐目录结构

```text
frontend/src/
├─ api/
│  ├─ http.ts
│  ├─ qa.ts
│  ├─ documents.ts
│  ├─ logs.ts
│  └─ unanswered.ts
├─ assets/
│  └─ logo.png
├─ components/
│  ├─ app/
│  │  ├─ AdminNav.vue
│  │  ├─ HistorySidebar.vue
│  │  └─ UserBadge.vue
│  ├─ chat/
│  │  ├─ AnswerCard.vue
│  │  ├─ ChatComposer.vue
│  │  ├─ ChatWorkspace.vue
│  │  ├─ RecommendedQuestions.vue
│  │  └─ SourceReferences.vue
│  └─ common/
│     ├─ EmptyState.vue
│     ├─ MetricCard.vue
│     └─ StatusTag.vue
├─ layouts/
│  ├─ AdminShell.vue
│  └─ UserShell.vue
├─ mock/
│  ├─ documents.ts
│  ├─ logs.ts
│  ├─ qa.ts
│  └─ sessions.ts
├─ router/
│  └─ index.ts
├─ stores/
│  ├─ auth.ts
│  ├─ chat.ts
│  └─ admin.ts
├─ styles/
│  ├─ main.css
│  └─ tokens.css
├─ types/
│  ├─ qa.ts
│  ├─ document.ts
│  ├─ log.ts
│  └─ user.ts
└─ views/
   ├─ LoginView.vue
   ├─ ChatView.vue
   ├─ DocumentManageView.vue
   └─ QaLogsView.vue
```

### 5.2 布局拆分

推荐拆成两套壳：

- `UserShell`：历史会话侧栏 + 问答工作区。
- `AdminShell`：管理员应用导航 + 内部页面。

问答主体不放在 shell 里，而是抽成 `ChatWorkspace`：

- 普通用户：`UserShell -> ChatWorkspace`
- 管理员：`AdminShell -> HistorySidebar + ChatWorkspace`

这样可以保持用户端和管理员端问答体验一致，又能避免导航结构混杂。

### 5.3 视觉系统

设计图视觉关键词：

- 浅色背景
- 蓝白主色
- 科技玻璃卡片
- 光伏电站线稿背景
- 柔和边框和阴影
- 机器人 IP logo
- 状态色清晰但不过度鲜艳

建议 CSS tokens：

```css
:root {
  --pv-bg: #f6f9ff;
  --pv-surface: #ffffff;
  --pv-surface-soft: #f8fbff;
  --pv-line: #dbe6f7;
  --pv-line-strong: #b8cdf2;
  --pv-text: #0d1b3d;
  --pv-muted: #6c7da3;
  --pv-primary: #126bff;
  --pv-primary-strong: #0057f0;
  --pv-cyan: #26d7ef;
  --pv-success: #18b66a;
  --pv-warning: #ff9f1c;
  --pv-danger: #f04438;
  --pv-shadow: 0 18px 50px rgba(28, 77, 156, 0.12);
}
```

实现注意：

- 不使用默认 Element Plus 风格裸露页面，要用自定义 class 包一层。
- Element Plus 适合表格、弹窗、分页、上传，但核心页面结构和卡片视觉应自定义。
- 登录背景可以先用 CSS 低透明网格和光伏线稿感渐变模拟，后续再补正式背景图。

## 6. 数据与接口方案

### 6.1 当前可真实联调接口

后端已完成：

```text
POST /api/qa/ask
```

请求：

```ts
export interface QaAskRequest {
  question: string;
  session_id?: string | null;
}
```

响应：

```ts
export type AnswerType = "rag" | "general_llm" | "refused" | "none";

export type Intent =
  | "knowledge_base_qa"
  | "general_explanation"
  | "out_of_scope"
  | "realtime_external"
  | "invalid_input";

export interface QaReference {
  rank: number;
  segment_id: string | null;
  document_id: string | null;
  heading_path: string;
  excerpt: string;
  vector_score: number | null;
  keyword_score: number | null;
  rrf_score: number | null;
  rerank_score: number | null;
}

export interface QaAskResponse {
  trace_id: string;
  answer_type: AnswerType;
  intent: Intent;
  answer: string;
  confidence: number | null;
  references: QaReference[];
  decision: Record<string, unknown>;
}
```

### 6.2 设计图字段与当前后端字段映射

| 设计图字段 | 当前后端字段 | 第一阶段展示方式 |
| --- | --- | --- |
| 文档名 | 暂无 document_name | 先用 `document_id` 或从 `heading_path` 推导主题 |
| 章节 | `heading_path` | 直接展示 |
| 页码 | 暂无 page_no | 不展示或显示“知识片段” |
| 引用摘要 | `excerpt` | 直接展示 |
| 置信度 | `confidence` | 百分比或两位小数展示 |
| trace_id | `trace_id` | 管理端展示，用户端可弱化 |
| 回答类型 | `answer_type` | 标签展示：知识库回答、通用解释、拒答 |
| 拒答原因 | `decision.refusal_reason` | 用户端展示友好话术，管理端展示原因 |

### 6.3 待后端补齐接口

设计图完整落地还需要：

```text
GET  /api/sessions
GET  /api/sessions/{id}
POST /api/documents/upload
GET  /api/documents/list
POST /api/documents/{id}/enable
POST /api/documents/{id}/disable
GET  /api/logs/qa
GET  /api/unanswered
PATCH /api/unanswered/{id}
```

前端应先按这些契约写 mock 类型，不阻塞当前问答页真实联调。

## 7. 真实功能链路与模块实现方案

当前方案前半部分已经说明页面视觉和字段，但还不足以指导“真实可用功能链路”开发。后续开发必须按下面链路推进：每个模块都要有用户动作、状态流转、数据来源、组件边界和验收方式，避免只做静态页面。

### 7.1 全局前端架构原则

第一阶段前端按以下分层实现：

- `api/`：只负责 HTTP 调用和响应解析，不写页面状态。
- `types/`：定义后端响应、前端视图模型、筛选参数和状态枚举。
- `stores/`：承载跨页面状态，例如登录角色、当前会话、会话列表、管理端筛选条件。
- `components/`：承载可复用 UI 与局部交互，例如历史侧栏、回答卡片、引用列表、反馈栏、状态标签、统计卡、详情抽屉。
- `views/`：只组合布局、调用 store action，不直接堆复杂业务逻辑。
- `mock/`：在后端接口缺失时提供贴近真实接口的 mock 数据，字段名必须和未来 api 层可映射。
- `styles/`：保留全局视觉 token 和布局样式；组件样式随组件或按模块 class 分区，避免所有新增样式继续挤进单一大文件。

### 7.2 登录与角色链路

对应设计图：`1登录页.png`

功能链路：

- 用户输入账号、密码，选择或识别角色。
- 前端校验必填项，失败时在表单内展示错误，不跳转。
- mock 登录成功后写入 `auth` 状态和 `localStorage`。
- 普通用户跳转 `/chat`。
- 管理员跳转 `/admin/chat`；如果暂未实现管理员问答页，则临时跳转 `/admin/documents`，但文档必须标明这是过渡状态。
- 页面刷新后从 `localStorage` 恢复角色和账号。
- 授权说明弹窗可打开、关闭，首次进入是否自动弹出由 `localStorage` 记录。

建议文件：

- `stores/auth.ts`：`role`、`account`、`login()`、`logout()`、`restoreAuth()`。
- `views/LoginView.vue`：只处理表单和跳转。
- `types/user.ts`：`UserRole = "user" | "admin"`。

验收：

- 不填写账号或密码不能登录。
- 普通用户和管理员登录后进入不同入口。
- 刷新页面后仍能识别角色。
- 退出登录后清空本地登录状态。

### 7.3 普通用户问答链路

对应设计图：`2-1用户问答页-空状态.png`、`2-1用户问答页-问答状态.png`

功能链路：

- 空状态展示问候语和推荐问题。
- 点击纯文字推荐问题按钮：创建或复用当前会话，追加用户消息，调用 `POST /api/qa/ask`。
- 输入框发送：同上；发送中禁用输入与按钮，防止重复提交。
- 输入框文案：placeholder 使用宽泛提示“请输入你的问题”，输入框左下角以轻量键帽样式常驻显示“Enter 发送，Shift + Enter 换行”。
- 接口成功：追加助手消息，展示回答类型、置信度、引用来源、复制和反馈入口；重新生成只对当前会话最新一条助手回答开放，历史助手回答不能重新生成。
- 接口拒答：展示固定友好兜底话术和拒答原因，不展示伪来源。
- 接口失败：保留用户问题，展示错误卡片和重试按钮；重试必须复用同一问题，不额外创建重复历史项。
- 左侧历史会话点击：只切换右侧会话，不自动发送请求。
- 会话标题：新会话使用第一条用户问题命名，后续追问只更新会话时间和消息流，不覆盖历史列表标题；读取本地缓存时也按第一条用户问题恢复标题。
- 搜索历史会话：按标题和全部消息内容过滤本地会话列表，展示命中数量、命中类型、内容片段、空状态和清空入口；后续接真实会话接口时可把查询参数下沉到 `GET /api/sessions`。
- 当前后端支持 `session_id`，前端发送时应保存后端会话 id；如果后端暂未返回 session id，则前端使用本地 id，并在文档中标明限制。

建议文件：

- `api/qa.ts`：`askQuestion(payload)`。
- `types/qa.ts`：`QaAskRequest`、`QaAskResponse`、`QaReference`。
- `types/session.ts`：`ChatSession`、`ChatMessage`、`ChatMessageStatus`。
- `stores/chat.ts`：会话列表、当前会话、发送问题、重试、复制、反馈状态。
- `components/app/HistorySidebar.vue`：历史列表、搜索、分组、切换会话、会话删除菜单和账户菜单；账户菜单与会话删除菜单均支持点击触发按钮打开，左键点击菜单/触发按钮/用户卡片以外的任意窗体区域或按 `Esc` 收起，外部点击使用捕获阶段监听以避免被页面内部事件拦截。
- `components/chat/ChatWorkspace.vue`：问答主工作区。
- `components/chat/ChatComposer.vue`：输入框和发送按钮。
- `components/chat/AnswerCard.vue`：回答内容和操作按钮；消息流已补齐用户/系统头像，系统消息使用纯白底项目透明 logo，用户消息使用用户图标，左右镜像排列以贴近真实聊天界面；助手回答通过 `MarkdownAnswer` 渲染标题、列表、加粗、行内代码和代码块，避免直接裸显 `###`、`**` 等 Markdown 标记；回答类型、置信度随 `SourceReferences` 展示在回答底部的“来源文档”区域，不放在页面顶部问题标题下；重新生成按钮由 `retryVisibility` 统一控制，只在最新助手回答上显示。
- `components/chat/MarkdownAnswer.vue` + `chat/markdownRenderer.ts`：实现安全的轻量 Markdown 子集解析与渲染，不使用 `v-html` 直接插入模型返回内容。
- `components/chat/SourceReferences.vue`：引用折叠列表。
- `components/chat/FeedbackBar.vue`：点赞、点踩、反馈原因。

验收：

- 点击左侧不同历史项，右侧标题、消息流、引用和状态跟着切换。
- 点击推荐问题或发送输入会真实调用 `/api/qa/ask`。
- `rag` 展示引用；`general_llm` 明确提示未使用知识库；`refused` 不展示来源。
- 后端未启动或模型配置错误时，不丢失用户问题，可点击重试。
- 复制按钮能把当前回答写入剪贴板，并给出成功提示。
- 重新生成会基于同一问题重新调用接口，并替换或追加新回答；该入口只显示在当前会话最新一条助手回答上，历史助手回答只能复制，避免从旧回答触发上下文不明确的重试。

### 7.4 引用来源链路

对应设计图：`2-1用户问答页-问答状态.png` 的“引用 3 个来源”区域。

功能链路：

- 仅当 `references.length > 0` 时展示引用区。
- 默认展示 Top 3。
- 点击引用区标题可以折叠/展开。
- 超过 3 条时提供“查看全部/收起”。
- 每条引用展示：排名、章节路径、摘要、相关度。
- 当前后端没有文档名和页码时，前端用 `heading_path` 和 `document_id` 兜底；不得伪造 PDF 文件名或页码。
- 管理员视角可额外复制 `segment_id`、`document_id`；普通用户默认弱化这些调试字段。

建议文件：

- `components/chat/SourceReferences.vue`
- `chat/qaPresentation.ts`：`formatConfidence()`、`describeAnswerType()`、`formatReferenceTitle()`。

验收：

- `references = []` 时不显示空引用框。
- `references > 3` 时可展开全部。
- 折叠状态不影响回答正文。
- 引用内容来自接口字段，不写死。

### 7.5 管理员问答链路

对应设计图：`2-2管理员问答页-空状态.png`、`2-2管理员问答页-问答状态.png`

功能链路：

- 管理员进入 `/admin/chat`。
- 页面最左侧显示管理员应用导航：问答、文档管理、问答日志、未命中问题。
- 中间显示与用户端一致的历史会话侧栏。
- 右侧复用 `ChatWorkspace`，保证问答逻辑不复制。
- 管理员可在回答卡片中看到弱调试信息入口，例如 trace_id、answer_type、confidence；详细链路仍跳转日志页查看。

建议文件：

- `layouts/AdminShell.vue`
- `components/app/AdminNav.vue`
- `views/AdminChatView.vue`
- 复用 `components/app/HistorySidebar.vue` 和 `components/chat/ChatWorkspace.vue`

验收：

- 管理员问答页与普通用户问答页共享发送、引用、拒答、重试逻辑。
- 管理员导航切换不丢失当前会话状态。
- 普通用户 UI 不显示管理员导航。

### 7.6 文档管理链路

对应设计图：`3文档管理页面.png`

当前后端状态：暂无文档管理 HTTP API，但已有数据库模型和导入脚本。因此前端先实现“可操作 mock 链路”，不是静态表格。

功能链路：

- 管理员进入 `/admin/documents`。
- 左侧分类侧栏可筛选全部、解析中、解析失败、已启用、已禁用。
- 顶部统计卡根据当前文档列表实时计算。
- 上传按钮打开文件选择或上传弹窗；当前无真实接口时，前端创建一条 `processing` mock 记录，并显示“接口待接入”提示。
- 文档状态从 `uploaded/processing/ready/failed/disabled` 中选择。
- 启用/禁用按钮会更新本地 mock 状态，并影响统计和筛选。
- 解析失败行可打开失败原因弹窗。
- 搜索框按文档名称、类型过滤。
- 分页对当前筛选结果生效。

建议文件：

- `api/documents.ts`：预留 `listDocuments()`、`uploadDocument()`、`enableDocument()`、`disableDocument()`。
- `types/document.ts`
- `mock/documents.ts`
- `stores/documents.ts`
- `views/DocumentManageView.vue`
- `components/common/MetricCard.vue`
- `components/common/StatusTag.vue`

验收：

- 上传 mock 文档后列表出现新记录。
- 点击启用/禁用后状态和统计同步变化。
- 点击解析失败原因能打开弹窗。
- 搜索、分类、分页不是摆设。

### 7.7 问答日志链路

对应设计图：`4问答日志页.png`

当前后端状态：`qa_record`、`qa_reference`、`qa_unanswered` 已写入数据库，但暂无查询接口。因此前端先实现“可查询 mock 链路”，后续只替换 api 层。

功能链路：

- 管理员进入 `/admin/logs`。
- 顶部统计卡从日志列表计算：全部、已回答、证据不足、拒答、低置信度、高耗时。
- Tab 按回答类型或处理状态筛选。
- 搜索框按问题、trace_id 搜索。
- 日期/类型/状态筛选影响表格。
- 点击表格行打开右侧详情抽屉。
- 详情抽屉展示问题、回答摘要、answer_type、intent、confidence、trace_id、latency、references、decision。
- 详情中的“查看未命中”或“标记处理”与未命中问题模块联动；真实接口缺失时先更新本地 mock 状态。

建议文件：

- `api/logs.ts`
- `types/log.ts`
- `mock/logs.ts`
- `stores/logs.ts`
- `views/QaLogsView.vue`
- `components/admin/LogDetailDrawer.vue`

验收：

- 统计卡随筛选结果变化。
- 点击任一日志能打开详情，不是静态抽屉。
- trace_id 可复制。
- 引用片段数量与详情引用列表一致。

### 7.8 未命中问题链路

对应文档模块：未命中问题记录；设计图中日志详情也会关联知识缺口判断，当前不新增独立未命中问题页面。

当前后端状态：`qa_unanswered` 已写入数据库，但暂无查询/处理接口。

功能链路：

- 管理员进入 `/admin/logs`。
- 通过回答状态、处理状态或详情中的知识缺口判断定位未命中候选。
- 日志详情展示问题、拒答原因、用户、会话来源、时间、处理状态。
- 点击“标记已处理”更新本地状态。
- 点击“加入未命中问题候选”生成待补充记录；真实接口缺失时先 mock。
- 后续如出现批量运营、负责人分配、FAQ 回流等需求，再基于独立设计图拆出页面。

建议文件：

- 当前不新增独立 `unanswered` 前端页面文件。
- 后续如拆页，再新增 `api/unanswered.ts`、`types/unanswered.ts`、`mock/unanswered.ts`、`stores/unanswered.ts`、`views/UnansweredView.vue`。

验收：

- 问答日志详情可展示知识缺口判断。
- 可从日志详情加入未命中问题候选。
- 旧 `/admin/unanswered` 路径重定向到 `/admin/logs`。

### 7.9 当前后端缺口与前端处理策略

| 功能 | 后端现状 | 前端策略 |
| --- | --- | --- |
| QA 提问 | 已有 `POST /api/qa/ask` | 真实接入，必须处理 loading/success/refused/error |
| 会话列表 | 暂无 `GET /api/sessions` | 先用本地 store/mock，会话切换必须真实可用 |
| 引用展示 | QA 响应已有 `references` | 真实展示，不伪造文档名页码 |
| 文档管理 | 暂无 HTTP API | mock 可操作链路，api 层预留 |
| 日志查询 | 暂无 HTTP API | mock 可查询链路，字段对齐 `qa_record` |
| 未命中查询 | 暂无 HTTP API | 当前收敛在日志详情中处理候选，字段对齐 `qa_unanswered` |
| 反馈/点赞点踩 | 暂无 HTTP API | 先本地记录 UI 状态，后续补接口 |

### 7.10 下一步执行优先级

为了优先形成真实可用链路，后续步骤调整为：

1. 抽离问答页组件和 `chat` store：让会话切换、发送、重试、复制、反馈都由 store 驱动。
2. 完成 `SourceReferences`、`AnswerCard`、`FeedbackBar`，补齐引用折叠、复制、重新生成、反馈。
3. 实现 `AdminShell` 和 `/admin/chat`，复用问答工作区。
4. 实现文档管理 mock 可操作链路。
5. 实现问答日志 mock 可查询链路和详情抽屉。
6. 将未命中问题能力收敛到问答日志详情，暂不新增独立页面。
7. 后端补接口后，只替换 `api/` 和 `stores/` 中的数据来源，不重写页面。

## 8. 页面实现步骤

### Step 1：统一视觉基础

状态：已完成，并由人工测试通过。

目标：

- 把当前深色绿色主题替换为设计图的浅蓝白主题。
- 建立 `tokens.css`、全局背景、卡片、按钮、状态标签基础样式。
- 引入 `正式参考文件/前端页面设计图/logo.png` 到 `frontend/src/assets/logo.png`。

验收：

- 登录页和工作台背景接近设计图。
- logo、蓝色主按钮、浅色卡片、柔和边框统一。
- 移动端宽度下不破版。

### Step 2：重做登录页

状态：根据人工测试反馈校正中。上一版登录页采用左右分栏产品介绍，与设计图不一致；当前校正为居中单卡片登录结构，并使用项目已安装的 `@element-plus/icons-vue` 替换临时 Unicode 图标；logo 已改为透明背景资源，密码可见图标已接入显示/隐藏交互，并校正为显示明文时展示可见图标、隐藏密码时展示隐藏图标。

目标：

- 按设计图实现账号、密码、角色选择、记住账号、授权说明。
- 继续使用 mock 登录。

行为：

- 普通用户登录后进入 `/chat`。
- 管理员登录后进入 `/admin/chat` 或 `/admin/documents`。
- 记住账号写入 localStorage。
- 授权说明用 Element Plus Dialog 展示。

验收：

- 可以选择普通用户或管理员。
- 登录后路由正确。
- 刷新后角色仍可恢复。

### Step 3：实现问答工作区

状态：已完成第一版实现，并完成架构拆分，等待人工测试确认。当前 `/chat` 已从后台 `AppShell` 拆出为普通用户全屏问答页，按设计图实现左侧历史会话、空状态推荐问题、问答消息流、底部输入框、发送中、错误重试和基础引用展示；已接入真实 `POST /api/qa/ask`。消息流已补齐用户头像和系统助手头像，用户消息右侧显示用户图标，系统消息左侧显示纯白底项目透明 logo，更接近真实聊天界面。左侧历史会话已改为本地会话切换，点击历史项会切换右侧对应会话内容，不再重复发送该历史问题；历史搜索已补齐完整本地链路，支持标题/消息内容搜索、命中数量、命中片段、空状态和清空入口；左下角账户菜单与历史会话删除菜单已统一为轻量弹层，支持点击空白处和 `Esc` 收起。

本步架构更新：

- 新增 `src/stores/chat.ts`，统一承载会话列表、当前会话、发送问题、重试、复制、错误状态、推荐问题发问和历史搜索链路。
- 新增 `src/chat/conversationTitle.contract.ts`，约束会话标题只能由第一条用户问题决定，防止连续追问时被最后一个问题覆盖。
- 新增 `src/components/app/HistorySidebar.vue`，承载历史分组、会话切换、搜索结果反馈、用户信息、会话删除菜单和账户菜单弹层。
- 新增 `src/components/app/historySidebarMenus.ts` 与 `historySidebarMenus.contract.ts`，统一历史侧栏弹层状态、点击外部关闭和 `Esc` 关闭行为；外部点击关闭使用捕获阶段监听，仅把历史菜单本体、更多按钮和用户卡片视为内部点击区域。
- 新增 `src/components/chat/ChatWorkspace.vue`，承载问答主区域、空状态、消息流和输入框组合。
- 新增 `src/components/chat/ChatComposer.vue`、`AnswerCard.vue`、`SourceReferences.vue`、`FeedbackBar.vue`、`RecommendedQuestions.vue`，为后续管理员问答页复用做准备。
- 新增 `src/chat/retryVisibility.ts` 与 `retryVisibility.contract.ts`，约束重新生成入口只出现在当前会话最新一条助手回答上，历史助手回答只保留复制。
- 新增 `src/chat/chatStore.contract.ts` 作为轻量编译期契约，约束 store 必须暴露真实功能链路所需的 API。
- 新增 `src/chat/clipboard.ts`，复制回答时优先使用 Clipboard API，失败时降级到隐藏 textarea 复制，并在页面显示复制成功/失败提示。
- `ChatView.vue` 现在只负责连接 store 与页面布局，不再堆叠业务状态。

目标：

- 按用户问答页设计图完成空状态、推荐问题、消息流和底部输入框。
- 接入真实 `POST /api/qa/ask`。

核心状态：

- `idle`：空状态。
- `asking`：发送中。
- `answered`：返回答案。
- `refused`：拒答。
- `error`：接口失败。

验收：

- 输入“逆变器绝缘阻抗低怎么排查？”可以返回 `rag` 回答。
- 输入“今天上海天气怎么样？”可以返回 `refused`。
- `references` 非空时显示引用折叠区。
- 发送中按钮禁用并显示 loading。
- 接口错误时保留用户问题并显示可重试提示。
- 左侧历史会话点击后切换右侧会话标题和消息流；当前使用本地 mock 会话，真实会话接口后续接入。

### Step 4：实现引用组件

状态：已完成用户端第一版引用组件，并完成回答正文 Markdown 富文本渲染优化，等待人工测试确认；管理员端复制 `segment_id` / `document_id` 的调试能力后续在管理员问答页或日志详情中补齐。

目标：

- 将 `references` 展示成设计图中的来源卡片。
- 默认展开 Top 3，可手动展开全部。

展示字段：

- 排名。
- 章节路径 `heading_path`。
- 摘要 `excerpt`。
- 相关分 `rerank_score`。
- `segment_id` 和 `document_id` 管理端可复制。

验收：

- `references.length = 0` 时不显示来源区，或显示“本次未使用知识库来源”。
- `general_llm` 明确提示“通用解释，未使用项目知识库”。
- `refused` 不展示伪来源。

### Step 5：实现管理员 Shell

状态：已完成，并按人工测试反馈完成折叠交互微调。当前已新增 `/admin/chat`，管理员端最左侧应用导航已独立为 `AdminNav`，管理端页面统一挂载在 `AdminShell` 下。管理员问答页复用普通用户的 `HistorySidebar`、`ChatWorkspace` 和 `chat` store，因此发送、引用、拒答、重试、复制等链路不会重复实现。管理员身份只在历史侧栏左下角显示“管理员 / 系统管理员”，最左侧应用导航不额外显示说明卡。最左侧应用导航支持折叠/展开；展开和折叠时都使用贴左边缘的同尺寸浮动按钮，折叠后左栏彻底收起，折叠状态写入 `localStorage`，刷新后保持。

目标：

- 按管理员设计图实现最左侧导航。
- 导航包括：问答、文档管理、问答日志。
- 未命中问题入口收敛到问答日志详情里，不在当前设计图之外新增独立导航入口。

本步实现：

- 新增 `src/components/app/AdminNav.vue`，提供问答、文档管理、问答日志三个设计图内入口。
- 新增 `src/components/app/adminNavItems.ts`，集中维护管理员导航项，避免再次出现设计图之外的独立入口。
- 新增 `src/layouts/AdminShell.vue`，作为管理端统一外壳。
- 新增 `src/layouts/adminNavState.ts`，读写最左侧管理员导航折叠状态。
- 新增 `src/views/AdminChatView.vue`，复用已有问答组件和 store。
- `HistorySidebar` 支持传入用户名称、角色文案和品牌跳转地址，避免管理员页显示普通用户身份。
- 移除最左侧导航底部额外说明卡，管理员身份信息只保留在设计图对应的左下角位置。
- `AdminNav` 增加贴左边缘的浮动折叠按钮；展开时显示 logo、图标和中文导航名称，不再显示 QA / DOC / LOG 英文缩写，折叠时左栏宽度收为 0，按钮尺寸和位置在展开/折叠状态下保持一致。
- 路由新增 `/admin/chat`，并将 `/admin/documents`、`/admin/logs` 切换到 `AdminShell` 下；旧 `/admin/unanswered` 重定向到 `/admin/logs`。
- 新增 `src/router/adminShell.contract.ts`，约束管理员 Shell 相关模块和路由存在。
- 新增 `src/router/unansweredConsolidation.contract.ts`，约束未命中问题不作为独立管理员导航入口。

验收：

- 管理员访问 `/admin/chat` 可看到最左侧管理员导航 + 中间历史会话 + 右侧问答区。
- 点击最左侧贴边浮动按钮后，导航栏彻底收起；再次点击可展开，按钮尺寸和贴边位置保持一致。
- 折叠/展开状态刷新后保持。
- 管理员访问 `/admin/documents`、`/admin/logs` 有统一导航，旧 `/admin/unanswered` 会回到日志页。
- 普通用户无法通过 UI 进入管理导航。

### Step 6：实现文档管理 mock 页面

状态：已完成第一版，等待人工测试确认。当前 `/admin/documents` 已按 `3文档管理页面.png` 重做为三栏管理工作台结构：最左侧沿用 `AdminShell` 管理导航，第二列为文档分类侧栏，右侧为文档管理主区。页面已接入 `documents` store，支持分类筛选、关键词搜索、类型筛选、解析状态筛选、启用状态筛选、分页、模拟上传、启用/禁用、失败原因弹窗和重新解析 mock 链路。

目标：

- 还原设计图中的分类侧栏、统计卡、筛选栏、表格和分页。
- 当前使用 mock 数据。

本步实现：

- 新增 `src/types/document.ts`，定义文档、分类、筛选、统计和状态类型。
- 新增 `src/mock/documents.ts`，提供贴近设计图的文档分类和文档列表 mock 数据。
- 新增 `src/api/documents.ts`，预留 `listDocuments()`、`uploadDocument()`、`enableDocument()`、`disableDocument()`，后续真实接口接入时替换该层。
- 新增 `src/stores/documents.ts`，统一管理文档列表、筛选条件、统计、分页、上传模拟、启用/禁用、失败原因和重新解析。
- 新增 `src/documents/documentStore.contract.ts`，用编译期契约约束文档管理 store 暴露完整可操作链路。
- 重写 `src/views/DocumentManageView.vue`，去掉旧占位壳，改为真实可操作的文档管理界面。
- 扩展 `src/styles/main.css` 的 `document-` 样式区，覆盖分类侧栏、统计卡、筛选条、上传模拟条、表格、状态标签、分页和弹窗内容。

验收：

- 展示全部文档、解析中、解析失败、已启用统计。
- 表格展示文件类型、解析状态、启用状态、失败原因、操作。
- 点击分类、搜索、类型、解析状态、启用状态后表格和分页同步变化。
- 点击上传文档会新增一条 `processing` mock 记录，并显示“真实上传接口待接入”提示。
- 点击启用/禁用后列表状态与统计同步变化。
- 点击解析失败原因能打开弹窗，弹窗内可触发重新解析。

### Step 7：实现问答日志 mock 页面

状态：已完成第一版，等待人工测试确认。当前 `/admin/logs` 已按 `4问答日志页.png` 实现可查询、可筛选、可打开详情抽屉的 mock 链路。该页暂不接真实后端，因为当前后端暂无 `GET /api/logs/qa` 查询接口，但数据库侧已有 `qa_record`、`qa_reference`、`qa_unanswered` 可作为后续字段来源。

本步已实现：

- 新增 `src/types/log.ts`、`src/mock/logs.ts`、`src/api/logs.ts`、`src/stores/logs.ts` 和 `src/logs/logStore.contract.ts`。
- 重写 `src/views/QaLogsView.vue`，实现统计卡、回答类型 tab、关键词搜索、状态筛选、处理状态筛选、日志表格、分页、右侧详情抽屉。
- 详情抽屉支持展示 trace_id、回答类型、意图、置信度、引用片段、阶段耗时和知识缺口判断。
- 支持复制 trace_id、标记已处理、从日志加入未命中问题候选的本地 mock 操作链路。
- 扩展 `src/styles/main.css` 的 `qa-log-` 样式区，保持与文档管理页一致的浅蓝白管理工作台风格。

目标：

- 还原设计图中的日志统计、筛选、表格、右侧详情抽屉。
- 当前使用 mock 数据。

设计图对齐范围：

- 顶部统计卡：全部记录、已回答、证据不足、拒答、低置信度、高耗时。
- 中部筛选区：回答类型 tab、关键词搜索、回答类型筛选、状态筛选、日期筛选、重置。
- 表格字段：问题、回答类型、状态、置信度、trace_id、引用片段数、总耗时、时间、处理状态。
- 右侧详情抽屉：问题与回答摘要、链路信息、引用片段、阶段耗时、知识缺口判断、处理按钮。
- 管理端导航继续复用 `AdminShell` 和 `AdminNav`，不在日志页重复实现导航。

功能链路：

- 管理员进入 `/admin/logs` 后看到统计卡、筛选栏和日志表格。
- 统计卡基于当前筛选结果实时计算，而不是写死数字。
- 点击类型 tab 或筛选控件后，表格、统计卡和分页同步变化。
- 搜索框按问题内容、trace_id、回答摘要进行本地过滤。
- 点击任一日志行或“查看详情”按钮后打开详情抽屉。
- 详情抽屉展示当前行对应的 trace_id、answer_type、intent、confidence、references、decision 和耗时分布。
- 点击复制 trace_id 写入剪贴板，并给出复制成功/失败提示；可复用 `src/chat/clipboard.ts`。
- 点击“标记已处理”更新当前日志的处理状态，列表和详情同步变化。
- 如果日志命中知识缺口，可显示“加入未命中问题”按钮；真实接口缺失时只更新本地状态，并在文案中说明“待后端接入”。

建议文件：

- 新增 `src/types/log.ts`：定义 `QaLogItem`、`QaLogAnswerType`、`QaLogStatus`、`QaLogProcessStatus`、`QaLogReference`、`QaLogStageLatency`、`QaLogFilters`、`QaLogSummary`。
- 新增 `src/mock/logs.ts`：提供覆盖 `rag`、`general_llm`、`refused`、`none`、低置信度、高耗时、证据不足、未处理等场景的 mock 数据。
- 新增 `src/api/logs.ts`：预留 `listQaLogs()`、`markQaLogProcessed()`、`createUnansweredFromLog()`，后续真实接口完成后只替换该层。
- 新增 `src/stores/logs.ts`：统一管理日志列表、筛选条件、统计、分页、当前详情、复制状态和处理动作。
- 新增 `src/logs/logStore.contract.ts`：编译期契约，约束 store 必须暴露筛选、分页、详情、复制、处理等真实链路 API。
- 重写 `src/views/QaLogsView.vue`：页面只组合 store 和 UI，不堆复杂业务逻辑。
- 可选新增 `src/components/admin/LogDetailDrawer.vue`：如果 `QaLogsView.vue` 过大，则抽离详情抽屉。
- 扩展 `src/styles/main.css`：新增 `qa-log-` 样式区，覆盖统计卡、筛选条、表格、详情抽屉、状态标签和响应式布局。

建议数据字段：

```ts
export type QaLogAnswerType = "rag" | "general_llm" | "refused" | "none";
export type QaLogStatus = "answered" | "insufficient_evidence" | "refused" | "low_confidence" | "error";
export type QaLogProcessStatus = "new" | "reviewed" | "resolved";

export interface QaLogReference {
  rank: number;
  document_id: string | null;
  segment_id: string | null;
  heading_path: string;
  excerpt: string;
  rerank_score: number | null;
}

export interface QaLogStageLatency {
  stage: "intent" | "retrieve" | "rerank" | "generate" | "total";
  label: string;
  milliseconds: number;
}

export interface QaLogItem {
  id: string;
  question: string;
  answerPreview: string;
  answerType: QaLogAnswerType;
  intent: string;
  status: QaLogStatus;
  processStatus: QaLogProcessStatus;
  confidence: number | null;
  traceId: string;
  referenceCount: number;
  latencyMs: number;
  createdAt: string;
  userName: string;
  references: QaLogReference[];
  stageLatencies: QaLogStageLatency[];
  decision: Record<string, unknown>;
  knowledgeGap: boolean;
  gapReason: string | null;
}
```

TDD / 契约步骤：

1. 新增 `src/logs/logStore.contract.ts`，先引用尚不存在的 `useQaLogStore` 和 `QaLogItem`，运行 `npm run build`，确认 RED 失败原因是缺少日志类型和 store。
2. 新增 `types/log.ts`、`mock/logs.ts`、`api/logs.ts`、`stores/logs.ts`，只实现契约要求的最小功能。
3. 再运行 `npm run build`，确认 GREEN。
4. 重写 `QaLogsView.vue` 和样式后，再运行 `npm run build`。
5. 使用浏览器访问 `/admin/logs`，人工验证筛选、详情抽屉、复制 trace_id、标记处理。

实现顺序：

1. 分析 `4问答日志页.png` 的布局密度、统计卡数量、表格字段和详情抽屉位置。
2. 写 `logStore.contract.ts`，约束 store 的 API：`logs`、`filters`、`summary`、`filteredLogs`、`paginatedLogs`、`selectedLog`、`selectLog()`、`closeDetail()`、`setKeyword()`、`setAnswerType()`、`setStatus()`、`setProcessStatus()`、`setPage()`、`resetFilters()`、`copyTraceId()`、`markProcessed()`。
3. 实现类型、mock 数据和 store，让所有统计和筛选从数据计算。
4. 重写 `QaLogsView.vue` 为真实可操作页面。
5. 如果详情抽屉模板超过可维护范围，则抽 `components/admin/LogDetailDrawer.vue`。
6. 补样式，保持和 Step 6 文档管理页一致的浅蓝白工作台风格。
7. 更新 `README.md` 和本实施方案，把 Step 7 状态改为“已完成第一版，等待人工测试确认”。
8. 验证 `npm run build` 和 `/admin/logs` 路由。

验收：

- 能展示 trace_id、置信度、引用片段数、耗时、状态。
- 点击一条日志打开详情抽屉。
- 详情中展示问题、回答摘要、链路信息、引用片段、阶段耗时、知识缺口判断。
- 搜索、类型筛选、状态筛选、处理状态筛选、分页均可用，不是静态 UI。
- 统计卡随筛选结果变化。
- trace_id 可复制，并显示复制结果。
- 标记处理后，当前行和统计状态同步更新。
- 当前页面明确使用 mock 数据，后端接口接入前不声称能查询真实日志。

### Step 8：收敛未命中问题能力

目标：

- 不实现设计图之外的独立未命中问题页面。
- 将 `qa_unanswered` 对应能力收敛到问答日志详情中的知识缺口判断与处理动作。
- 当前使用 mock 数据，后续真实接口接入时优先增强日志页详情和筛选。

验收：

- 管理员导航不显示“未命中问题”独立入口。
- 访问旧 `/admin/unanswered` 会进入 `/admin/logs`。
- 日志详情可展示知识缺口判断，并支持加入未命中问题候选。
- 如后续需要批量处理、负责人分配或 FAQ 回流，再基于独立设计图新建页面。

### Step 9：补齐验证和文档

目标：

- 更新 `frontend/README.md`，记录启动、页面路径、当前接口接入状态。
- 增加前端自测清单。

验收：

- `npm run build` 通过。
- 浏览器可访问 `/login`、`/chat`、`/admin/documents`、`/admin/logs`。
- README 与实际页面一致。

## 9. 推荐开发顺序

建议分三轮开发，避免一次铺太大。

第一轮：问答闭环优先

1. 视觉 tokens 和 logo。
2. 登录页。
3. 用户问答页。
4. `POST /api/qa/ask` 接入。
5. 引用展示。

第二轮：管理员页面目标态

1. AdminShell。
2. 文档管理 mock 页面。
3. 问答日志 mock 页面。
4. 未命中问题 mock 页面。

第三轮：真实接口扩展

1. 后端补文档管理查询接口后接入文档页。
2. 后端补日志查询接口后接入日志页。
3. 后端补未命中查询接口后接入未命中页。
4. 补反馈、重新生成和会话历史持久化。

## 10. 测试与验收方案

### 9.1 本地命令

```powershell
cd frontend
npm run build
```

如果后续增加 lint/test，再补：

```powershell
npm run lint
npm run test
```

### 9.2 浏览器手动验收

必测路径：

```text
/login
/chat
/admin/documents
/admin/logs
```

必测问题：

```text
逆变器绝缘阻抗低怎么排查？
什么是无功功率？
今天上海天气怎么样？
```

预期：

- 第一个问题返回 `rag`，展示引用。
- 第二个问题可能返回 `general_llm` 或 `rag`，按返回类型展示。
- 第三个问题返回 `refused`，不展示引用。

### 9.3 视觉验收

- 登录页应接近设计图的浅蓝白机器人视觉。
- 用户问答页应有左侧历史侧栏、中央空状态、底部输入框。
- 管理员页应有最左侧导航。
- 文档管理和日志页应具备清晰表格、状态标签和筛选区。
- 普通用户界面不暴露过多 trace/debug 信息。

## 11. 风险与处理

| 风险 | 影响 | 处理 |
| --- | --- | --- |
| 文档管理和日志接口尚未完成 | 页面只能 mock | 先做目标态 UI，api 层预留 |
| 当前 `references` 无文档名和页码 | 来源展示不如设计图完整 | 第一阶段展示 `heading_path/excerpt/document_id` |
| 真实模型接口耗时较长 | 前端 loading 时间长 | 增加发送中状态、取消重复提交、错误重试 |
| `package-lock.json` 有本地漂移 | 提交噪音 | 不随本方案提交，等依赖变更时再处理 |
| 当前视觉和设计图不一致 | 演示观感割裂 | 第一轮优先替换视觉系统 |
| 管理员和用户问答逻辑重复 | 后期维护成本高 | 抽 `ChatWorkspace` 复用 |
| 只做静态 mock 页面 | 用户无法验证真实流程 | 每个模块必须实现可点击、可筛选、可切换、可重试的本地或真实链路 |
| 后端模型 API 未配置 | RAG 问题返回接口错误 | 前端展示可恢复错误；环境层补真实 `.env` 后再验收 RAG 成功路径 |
| 左侧会话时间使用缓存文本 | 跨天或旧 localStorage 数据可能显示不准 | 侧栏展示和“今天/昨天/更早”分组统一由 `updatedAt` 动态计算；`time/group` 仅作为历史兼容字段保留 |

## 12. 结论

前端下一步应优先做“用户问答真实闭环”，而不是先完整实现所有管理后台接口。

推荐最小可交付顺序：

1. 重做浅蓝白视觉和登录页。
2. 实现问答工作区并接入 `/api/qa/ask`。
3. 做好引用展示、拒答展示和错误状态。
4. 管理端先按设计图实现 mock 目标态。
5. 等后端补齐文档、日志、未命中接口后再切真实数据。

这样既能最快看到 RAG 后端成果，也能让前端页面和设计图保持一致。
