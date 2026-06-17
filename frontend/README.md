# 光伏智能问答系统前端实现说明

本文档用于指导第一阶段 Web MVP 的前端实现。前端目标不是做复杂 AI 助手，而是先交付一个可用、可信、可追踪的光伏运维文档问答入口，并能支撑管理员完成文档管理、日志查看和未命中问题回流。

## 1. 前端定位

第一阶段前端聚焦以下闭环：

1. 用户登录或选择角色进入系统。
2. 普通用户在问答页发起自然语言提问。
3. 系统展示结构化回答、来源引用、追问或拒答结果。
4. 管理员可以上传文档、查看解析状态和失败原因。
5. 管理员可以查看问答日志、trace_id、未命中问题。
6. 页面使用 mock 数据即可先完整演示，后续再逐步接入真实后端接口。

第一阶段不做移动端悬浮助手、语音输入、实时数据查询、SCADA / DCS 接入、工单系统和复杂 Agent 能力。

## 1.1 当前状态

当前仓库里的前端已完成 `Module 02 / Step 1` 的主布局和路由入口，仍属于页面壳阶段，尚未完成真实业务联调。

已完成：

- 登录入口 `/login`
- 问答页入口 `/chat`
- 文档管理入口 `/admin/documents`
- 基础日志入口 `/admin/logs`
- 未命中问题入口 `/admin/unanswered`
- 通用工作台布局 `src/layouts/AppShell.vue`

尚未完成：

- 真实 API 接入
- 角色权限和会话状态管理
- 完整 mock 数据流
- 问答、上传、日志和未命中问题的真实交互

因此本文档中的完整目录结构仍属于第一阶段目标结构，不代表已经在代码里全部实现。

## 2. 技术栈

- Vue 3
- TypeScript
- Vite
- Vue Router
- Pinia
- Element Plus
- Axios

## 3. 启动方式

```powershell
cd C:\Users\Sakura\Desktop\Money\frontend
npm install
npm run dev
```

默认访问：

```text
http://127.0.0.1:5173
```

后端默认地址：

```text
http://127.0.0.1:8000
```

## 4. 推荐目录结构

当前项目只保留了最小 Vue 入口。进入第一阶段前端实现时，建议扩展为：

```text
frontend/src/
├─ api/                  后端接口封装
│  ├─ http.ts            Axios 实例、错误处理
│  ├─ auth.ts            登录和用户信息接口
│  ├─ qa.ts              问答接口
│  ├─ documents.ts       文档上传和管理接口
│  ├─ sessions.ts        会话历史接口
│  ├─ logs.ts            问答日志接口
│  └─ unanswered.ts      未命中问题接口
├─ components/           通用组件
│  ├─ RecommendedQuestions.vue
│  ├─ SourceReferences.vue
│  ├─ FeedbackBar.vue
│  ├─ HistorySidebar.vue
│  ├─ AnswerCard.vue
│  ├─ EmptyState.vue
│  └─ PageShell.vue
├─ layouts/
│  ├─ UserLayout.vue
│  └─ AdminLayout.vue
├─ mock/                 Module 02 阶段 mock 数据
│  ├─ qa.ts
│  ├─ documents.ts
│  ├─ sessions.ts
│  ├─ logs.ts
│  └─ unanswered.ts
├─ router/
│  └─ index.ts
├─ stores/
│  ├─ auth.ts
│  ├─ qa.ts
│  └─ ui.ts
├─ styles/
│  ├─ main.css
│  └─ tokens.css
├─ types/
│  ├─ api.ts
│  ├─ qa.ts
│  ├─ document.ts
│  ├─ session.ts
│  └─ user.ts
├─ views/
│  ├─ LoginView.vue
│  ├─ ChatView.vue
│  ├─ DocumentManageView.vue
│  ├─ QaLogsView.vue
│  └─ UnansweredView.vue
├─ App.vue
└─ main.ts
```

## 5. 页面实现步骤

建议当前只按 `Module 02` 的范围先落地页面壳、路由、布局和 mock 数据，不要一开始就把 Module 03 到 Module 07 一次性做完。

### Step 1：建立主布局和路由

状态：已完成基础页面壳。

目标：

- 将当前占位首页替换为正式 Web MVP 路由结构。
- 先实现登录页、用户问答页、管理员管理页入口。

建议路由：

```text
/login                 登录页
/chat                  问答页
/admin/documents       文档管理页
/admin/logs            基础日志页
/admin/unanswered      未命中问题页
```

完成标准：

- 前端可以启动。
- 访问 `/login` 可进入登录页。
- 登录后根据角色跳转。
- 普通用户入口跳转到 `/chat`。
- 管理员入口跳转到 `/admin/documents`。
- 管理页面已有统一工作台布局和导航入口。

当前实现文件：

```text
src/layouts/AppShell.vue
src/views/LoginView.vue
src/views/ChatView.vue
src/views/DocumentManageView.vue
src/views/QaLogsView.vue
src/views/UnansweredView.vue
src/router/index.ts
src/styles/main.css
```

### Step 2：实现登录和角色入口

目标：

- 第一阶段可先使用本地 mock 登录，不要求真实鉴权。
- 明确 `user` 和 `admin` 两类角色。

页面内容：

- 产品标题
- 账号输入
- 密码输入
- 登录按钮
- 项目能力边界说明
- 首次进入授权说明弹窗

建议：

- mock 账号可设置为 `user / user` 和 `admin / admin`。
- 登录状态先存入 Pinia 和 `localStorage`。
- 后续接入 `/api/auth/*` 时替换 mock。
- 当前阶段不做真实鉴权，登录只是本地角色分流和页面入口控制。

### Step 3：实现问答页

目标：

- 问答页是第一阶段前端主页面。
- 用户和管理员共用同一套问答布局，但不要在问答主界面展示调试信息。

页面结构：

- 左侧历史会话侧边栏
- 顶部标题栏
- 推荐问题区
- 对话消息区
- 输入框和发送按钮
- 回答操作区
- 来源引用区
- 反馈区

必须状态：

- 空会话状态
- 用户提问消息
- 回答加载中
- 正常回答
- 来源引用展示
- 追问回答
- 拒答或兜底回答
- 接口错误提示

通用组件：

- `HistorySidebar`
- `RecommendedQuestions`
- `AnswerCard`
- `SourceReferences`
- `FeedbackBar`

完成标准：

- 可以输入问题并发送。
- 推荐问题可以点击填入或直接发送。
- mock 返回可以展示 `answer`、`answer_type`、`references`、`trace_id`。
- 当 `answer_type = fallback` 或 `none` 时展示固定兜底或无依据提示。
- 有引用时展示文档名、章节、页码或片段摘要。

### Step 4：实现文档管理页

目标：

- 管理员可以上传文档并查看文档入库状态。
- Module 02 阶段可先用 mock 数据，Module 04 再接真实接口。

页面结构：

- 文档上传入口
- 文档列表
- 文档状态标签
- 启用 / 禁用操作
- 失败原因查看
- 文档详情或片段预览入口

文档状态：

```text
uploaded
processing
ready
failed
disabled
```

完成标准：

- 支持选择 TXT / MD / DOCX / PDF。
- 上传后列表出现记录。
- 可以展示解析状态。
- failed 状态可以查看 `error_message`。
- ready / disabled 状态有明确视觉区分。

### Step 5：实现基础日志页

目标：

- 管理员可以查看问答链路是否可追踪。
- 日志页用于调试和验收，不面向普通用户。

列表字段：

- 问题
- 回答类型
- 置信度
- 来源片段数量
- trace_id
- 耗时
- 时间

筛选建议：

- answer_type
- date_from / date_to
- trace_id

完成标准：

- 能用 mock 数据展示日志列表。
- 可以查看单条日志详情。
- trace_id 显示清晰，便于复制。

### Step 6：实现未命中问题页

目标：

- 收集拒答问题、证据不足问题和待补充知识点。
- 为 FAQ 和知识库补充形成回流闭环。

列表字段：

- 问题内容
- 触发原因
- 用户
- 会话来源
- 状态
- 时间

状态：

```text
new
reviewed
resolved
```

完成标准：

- 管理员可以查看未命中问题。
- 可以修改处理状态。
- 能区分证据不足、超范围、无关问题。

### Step 7：抽象 API 和类型

目标：

- 在 mock 阶段也按照真实 API 返回结构设计类型。
- 后续后端接口完成后，只替换 api 层，不大改页面。

QA 返回结构建议：

```ts
export interface QaAskResponse {
  answer: string;
  answer_type: "faq" | "rag" | "fallback" | "none";
  confidence: number;
  references: QaReference[];
  trace_id: string;
  route?: "faq" | "rag" | "fallback";
  tool_calls?: unknown[];
  decision?: Record<string, unknown>;
  fallback_reason?: string | null;
}
```

引用结构建议：

```ts
export interface QaReference {
  id: string;
  document_id?: string;
  document_name: string;
  segment_id?: string;
  page_no?: number | null;
  section_title?: string | null;
  excerpt: string;
  relevance_score?: number;
}
```

列表接口统一参数：

```ts
export interface ListQuery {
  page?: number;
  page_size?: number;
  status?: string;
  sort?: string;
}
```

统一错误格式：

```ts
export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
  };
}
```

### Step 8：从 mock 切换到真实接口

建议顺序：

1. 先接文档上传和文档列表。
2. 再接 `POST /api/qa/ask`。
3. 再接会话历史。
4. 再接日志和未命中问题。
5. 最后补反馈、重新生成、复制等增强能力。

当前阶段优先把 `Module 02` 的页面壳和 mock 数据做稳，再进入 `Module 03` 的 API 契约和类型整理，避免前端先铺太多接口依赖而卡住联调。

接口建议：

```text
POST /api/documents/upload
GET  /api/documents/list
GET  /api/documents/{id}
POST /api/documents/{id}/enable
POST /api/documents/{id}/disable

POST /api/qa/ask

GET  /api/sessions
GET  /api/sessions/{id}

GET  /api/logs/qa

GET   /api/unanswered
PATCH /api/unanswered/{id}
```

## 6. 视觉和交互方向

整体视觉建议采用“光伏运维中控台”风格：

- 清晰、稳定、可扫描。
- 强调来源引用、任务状态、置信度、trace_id。
- 普通用户页面应更轻，减少调试信息。
- 管理员页面可以更偏工作台和调试台。

不建议：

- 做营销落地页风格。
- 做移动端悬浮助手。
- 做语音输入。
- 把所有管理调试字段塞进普通用户问答页。

## 7. 前端模块推进顺序

建议按项目 Module 02 到 Module 07 推进：

1. Module 02：页面壳、路由、布局、mock 数据。
2. Module 03：根据页面字段反推 API 契约和前端类型。
3. Module 04：接入文档上传、文档列表、状态展示。
4. Module 05：展示解析状态、失败原因、片段预览。
5. Module 06：接入问答接口、引用展示、追问和拒答。
6. Module 07：接入会话、日志、未命中问题。
7. Module 08：补验收演示流程和页面回归测试。

## 8. 第一阶段前端验收标准

Module 02 页面壳完成标准：

- 前端可以启动。
- 登录或角色入口可进入系统。
- 问答页具备输入框、对话区、引用区、追问和拒答展示。
- 文档管理页具备上传入口、文档列表、状态展示。
- 日志页和未命中问题页有基础列表。
- 页面可以使用 mock 数据完整演示一遍。
- 后续 API 契约可以根据页面字段反推和校准。

第一阶段最终验收标准：

- 用户可以在 Web 页面输入问题。
- 系统可以展示回答。
- 有效回答必须展示来源引用。
- 无证据时展示 `fallback` 或 `none` 状态。
- 每次问答展示或记录 `trace_id`。
- 管理员可以查看文档状态、基础日志和未命中问题。

## 9. 建议的 mock 场景

问答场景：

- 正常 RAG 回答：逆变器 PV 过压常见原因有哪些？
- FAQ 回答：组件巡检一般要检查哪些项？
- 追问：帮我看下这个设备有问题。
- 拒答：帮我查今天实时发电量。
- 无关问题：帮我写年终总结。

文档场景：

- ready：已完成解析并可用于检索。
- processing：正在解析、切块和入库。
- failed：解析失败，展示 error_message。
- disabled：管理员禁用，不参与检索。

日志场景：

- answer_type = faq
- answer_type = rag
- answer_type = fallback
- answer_type = none

未命中场景：

- evidence_not_found
- out_of_scope
- missing_information
- unrelated

## 10. 开发注意事项

- 先保证页面流程可演示，再追求细节。
- mock 数据字段必须贴近真实接口，避免后续重写。
- 普通用户端不要展示检索调试细节。
- 管理员页面要保留 trace_id、状态、失败原因等排障字段。
- 所有列表页预留分页、筛选和排序参数。
- 所有回答引用都要能展示文档名和片段摘要。
- 第一阶段宁可保守拒答，也不要做无依据自由聊天。
