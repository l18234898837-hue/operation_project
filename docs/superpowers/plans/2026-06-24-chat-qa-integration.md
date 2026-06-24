# Chat QA Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the QA page from a mock-history prototype into a real session-based, stream-capable chat surface with searchable/deletable local sessions, document-file-name-only references, and a user logout menu.

**Architecture:** Use the existing Vue 3 + Pinia chat store as the frontend session boundary, with local in-browser sessions until backend session-list CRUD exists. Keep backend QA answering unchanged except for enriching reference response objects with `document_file_name`, because the frontend should display only the original document file name for citations. Stream answers through `POST /api/qa/ask/stream` using `fetch` + `ReadableStream` + SSE parsing, guarded by `AbortController` so session switching/deletion cannot leak old stream chunks into the wrong conversation.

**Tech Stack:** Vue 3, Vite, Pinia, TypeScript, Element Plus icons, FastAPI, Pydantic, SQLAlchemy, pytest, `vue-tsc`.

---

## File Structure

- Modify `backend/app/schemas/qa.py`: add `document_file_name` to `QaReferenceSchema`.
- Modify `backend/app/services/qa_service.py`: populate `document_file_name` by looking up `KbDocument.file_name` or falling back to `KbDocument.title`.
- Modify `backend/tests/test_qa_api.py`: add backend contract coverage for `document_file_name`.
- Modify `frontend/src/types/qa.ts`: add `document_file_name` and `visible` to `QaReference`; add stream event types.
- Modify `frontend/src/types/qa.contract.ts`: extend frontend type contract for the new reference fields.
- Modify `frontend/src/api/qa.ts`: add streaming QA client while keeping non-streaming `askQuestion` available for tests/fallback.
- Modify `frontend/src/chat/conversationModel.ts`: add richer session/message states and remove dependency on mock initial conversations.
- Delete `frontend/src/chat/initialConversations.ts`: remove mock history seed data.
- Modify `frontend/src/stores/chat.ts`: implement local real sessions, search, new/delete session, stream lifecycle, retry without duplicating user messages, and logout state hooks.
- Modify `frontend/src/views/ChatView.vue`: pass new sidebar/user-menu/search/session events into components.
- Modify `frontend/src/components/app/HistorySidebar.vue`: add search binding, new-session button, per-session three-dot menu, delete action, empty search state, and user settings dropdown.
- Modify `frontend/src/components/chat/ChatWorkspace.vue`: support empty state, stream status text, partial assistant messages, and cancellation-safe rendering.
- Modify `frontend/src/components/chat/AnswerCard.vue`: render assistant loading/error/streaming states cleanly.
- Modify `frontend/src/components/chat/SourceReferences.vue`: show only unique visible document file names.
- Modify `frontend/src/components/chat/FeedbackBar.vue`: keep copy/regenerate, but regeneration must target the latest user turn without duplicating it.
- Modify `frontend/src/components/chat/ChatComposer.vue`: keep Enter-to-send and add Shift+Enter multiline behavior explicitly.
- Modify `frontend/src/styles/main.css`: add styles for new-session button, history menu, delete confirm, empty states, stream cursor, document-only citation chips, and user dropdown.

## Implementation Tasks

### Task 1: Backend Reference Contract Adds Document File Name

**Files:**
- Modify: `backend/app/schemas/qa.py`
- Modify: `backend/app/services/qa_service.py`
- Test: `backend/tests/test_qa_api.py`

- [ ] **Step 1: Write the failing backend schema test**

Add this test after `test_qa_reference_schema_contains_scores` in `backend/tests/test_qa_api.py`:

```python
def test_qa_reference_schema_contains_document_file_name():
    reference = QaReferenceSchema(
        rank=1,
        segment_id="segment-1",
        document_id="document-1",
        document_file_name="inverter-maintenance.md",
        heading_path="逆变器故障与维护 > 漏电流故障",
        excerpt="漏电流可能与组件绝缘层破损有关。",
        vector_score=0.6,
        keyword_score=0.4,
        rrf_score=0.03,
        rerank_score=0.9,
        visible=True,
    )

    assert reference.document_file_name == "inverter-maintenance.md"
    assert reference.model_dump()["document_file_name"] == "inverter-maintenance.md"
```

- [ ] **Step 2: Run the schema test to verify it fails**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_qa_api.py::test_qa_reference_schema_contains_document_file_name', '-q']))"
```

Expected: `TypeError` or validation failure because `document_file_name` is not defined on `QaReferenceSchema`.

- [ ] **Step 3: Add `document_file_name` to the backend response schema**

In `backend/app/schemas/qa.py`, change `QaReferenceSchema` to:

```python
class QaReferenceSchema(BaseModel):
    rank: int
    segment_id: str | None
    document_id: str | None
    document_file_name: str | None = None
    heading_path: str
    excerpt: str
    vector_score: float | None
    keyword_score: float | None
    rrf_score: float | None
    rerank_score: float | None
    visible: bool = True
```

- [ ] **Step 4: Run the schema test to verify it passes**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_qa_api.py::test_qa_reference_schema_contains_document_file_name', '-q']))"
```

Expected: `1 passed`.

- [ ] **Step 5: Write a failing service contract test for populated file names**

Add imports near the top of `backend/tests/test_qa_api.py`:

```python
from app.services.qa_service import _reference_schema
```

Add this test after `test_qa_reference_schema_contains_document_file_name`:

```python
class _ReferenceItem:
    segment_id = "segment-1"
    document_id = "document-1"
    heading_path = "逆变器故障与维护 > 漏电流故障"
    clean_text = "漏电流可能与组件绝缘层破损有关。"
    vector_score = 0.6
    keyword_score = 0.4
    rrf_score = 0.03
    rerank_score = 0.9


def test_reference_schema_uses_document_file_name():
    schema = _reference_schema(
        rank=1,
        item=_ReferenceItem(),
        visible=True,
        document_file_name="inverter-maintenance.md",
    )

    assert schema.document_file_name == "inverter-maintenance.md"
```

- [ ] **Step 6: Run the service contract test to verify it fails**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_qa_api.py::test_reference_schema_uses_document_file_name', '-q']))"
```

Expected: `TypeError: _reference_schema() got an unexpected keyword argument 'document_file_name'`.

- [ ] **Step 7: Populate document file names in `qa_service`**

In `backend/app/services/qa_service.py`, add `KbDocument` to the model imports:

```python
from app.models.rag import (
    AnswerType,
    KbDocument,
    QaRecord,
    QaReference,
    QaSession,
    QaUnanswered,
)
```

Replace `_add_references` and `_reference_schema` with:

```python
def _add_references(
    session: Session,
    record: QaRecord,
    evidence: list[object],
    visible_top_k: int,
) -> list[QaReferenceSchema]:
    references: list[QaReferenceSchema] = []
    document_file_names = _document_file_names(session, evidence)
    for rank, item in enumerate(evidence, start=1):
        document_id = str(getattr(item, "document_id", "") or "")
        reference = QaReference(
            qa_record_id=record.id,
            document_id=_uuid_or_none(getattr(item, "document_id", None)),
            segment_id=_uuid_or_none(getattr(item, "segment_id", None)),
            rank=rank,
            relevance_score=getattr(item, "rerank_score", None),
            vector_score=getattr(item, "vector_score", None),
            keyword_score=getattr(item, "keyword_score", None),
            rrf_score=getattr(item, "rrf_score", None),
            excerpt=(getattr(item, "clean_text", "") or "")[:500],
            ref_metadata={"heading_path": getattr(item, "heading_path", "") or ""},
        )
        session.add(reference)
        references.append(
            _reference_schema(
                rank,
                item,
                visible=rank <= visible_top_k,
                document_file_name=document_file_names.get(document_id),
            )
        )
    return references


def _reference_schema(
    rank: int,
    item: object,
    visible: bool = True,
    document_file_name: str | None = None,
) -> QaReferenceSchema:
    return QaReferenceSchema(
        rank=rank,
        segment_id=str(getattr(item, "segment_id", "") or "") or None,
        document_id=str(getattr(item, "document_id", "") or "") or None,
        document_file_name=document_file_name,
        heading_path=getattr(item, "heading_path", "") or "",
        excerpt=(getattr(item, "clean_text", "") or "")[:500],
        vector_score=getattr(item, "vector_score", None),
        keyword_score=getattr(item, "keyword_score", None),
        rrf_score=getattr(item, "rrf_score", None),
        rerank_score=getattr(item, "rerank_score", None),
        visible=visible,
    )


def _document_file_names(session: Session, evidence: list[object]) -> dict[str, str]:
    document_ids = {
        parsed
        for item in evidence
        if (parsed := _uuid_or_none(getattr(item, "document_id", None))) is not None
    }
    if not document_ids:
        return {}

    rows = session.execute(
        select(KbDocument.id, KbDocument.file_name, KbDocument.title).where(KbDocument.id.in_(document_ids))
    ).all()
    return {
        str(document_id): file_name or title
        for document_id, file_name, title in rows
        if file_name or title
    }
```

- [ ] **Step 8: Run backend QA API tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_qa_api.py', '-q']))"
```

Expected: `24 passed` with the existing Starlette/httpx warning acceptable.

- [ ] **Step 9: Commit backend reference contract**

Run:

```powershell
git add backend/app/schemas/qa.py backend/app/services/qa_service.py backend/tests/test_qa_api.py
git commit -m "feat: expose QA reference document file names"
```

Expected: commit succeeds.

### Task 2: Frontend QA Types and Stream Parser Contract

**Files:**
- Modify: `frontend/src/types/qa.ts`
- Modify: `frontend/src/types/qa.contract.ts`
- Modify: `frontend/src/api/qa.ts`

- [ ] **Step 1: Add frontend type contract expectations**

In `frontend/src/types/qa.contract.ts`, replace the file with:

```ts
import type { QaAskRequest, QaAskResponse, QaReference, QaStreamEvent } from "./qa";

type Assert<T extends true> = T;
type IsAssignable<TValue, TExpected> = TValue extends TExpected ? true : false;
type BackendSessionId = `${string}-${string}-${string}-${string}-${string}`;

type RequestSessionIdIsBackendUuid = Assert<IsAssignable<NonNullable<QaAskRequest["session_id"]>, BackendSessionId>>;
type ResponseIncludesBackendSessionId = Assert<IsAssignable<QaAskResponse, { session_id: BackendSessionId }>>;
type ReferenceIncludesDocumentFileName = Assert<IsAssignable<QaReference, { document_file_name: string | null }>>;
type ReferenceIncludesVisibility = Assert<IsAssignable<QaReference, { visible: boolean }>>;
type StreamEventIncludesAnswerDelta = Assert<IsAssignable<{ event: "answer_delta"; data: { text: string } }, QaStreamEvent>>;

void (null as unknown as RequestSessionIdIsBackendUuid);
void (null as unknown as ResponseIncludesBackendSessionId);
void (null as unknown as ReferenceIncludesDocumentFileName);
void (null as unknown as ReferenceIncludesVisibility);
void (null as unknown as StreamEventIncludesAnswerDelta);
```

- [ ] **Step 2: Run frontend build to verify the contract fails**

Run:

```powershell
npm run build
```

From `frontend/`.

Expected: TypeScript errors because `document_file_name`, `visible`, and `QaStreamEvent` are missing.

- [ ] **Step 3: Add frontend QA stream and reference types**

In `frontend/src/types/qa.ts`, replace the file with:

```ts
export type AnswerType = "rag" | "general_llm" | "refused" | "none";

export type QaIntent =
  | "knowledge_base_qa"
  | "general_explanation"
  | "out_of_scope"
  | "realtime_external"
  | "invalid_input";

export type BackendSessionId = `${string}-${string}-${string}-${string}-${string}`;

export interface QaAskRequest {
  question: string;
  session_id?: BackendSessionId | null;
}

export interface QaReference {
  rank: number;
  segment_id: string | null;
  document_id: string | null;
  document_file_name: string | null;
  heading_path: string;
  excerpt: string;
  vector_score: number | null;
  keyword_score: number | null;
  rrf_score: number | null;
  rerank_score: number | null;
  visible: boolean;
}

export interface QaAskResponse {
  session_id: BackendSessionId;
  trace_id: string;
  answer_type: AnswerType;
  intent: QaIntent;
  answer: string;
  confidence: number | null;
  references: QaReference[];
  decision: Record<string, unknown>;
}

export type QaStreamStatusStage = "understanding" | "rewriting" | "retrieving" | "generating" | "done" | "error";

export type QaStreamEvent =
  | { event: "status"; data: { stage: QaStreamStatusStage; message: string } }
  | { event: "answer_delta"; data: { text: string } }
  | { event: "references"; data: { references: QaReference[] } }
  | { event: "done"; data: QaAskResponse }
  | { event: "error"; data: { stage: "error"; message: string; error?: string } };

export interface AskQuestionStreamOptions {
  signal?: AbortSignal;
  onEvent: (event: QaStreamEvent) => void;
}
```

- [ ] **Step 4: Add the streaming API client**

In `frontend/src/api/qa.ts`, replace the file with:

```ts
import type { AskQuestionStreamOptions, QaAskRequest, QaAskResponse, QaStreamEvent } from "../types/qa";

export async function askQuestion(payload: QaAskRequest): Promise<QaAskResponse> {
  const response = await fetch("/api/qa/ask", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`QA request failed: ${response.status}`);
  }

  return (await response.json()) as QaAskResponse;
}

export async function askQuestionStream(
  payload: QaAskRequest,
  { signal, onEvent }: AskQuestionStreamOptions
): Promise<void> {
  const response = await fetch("/api/qa/ask/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload),
    signal
  });

  if (!response.ok) {
    throw new Error(`QA stream request failed: ${response.status}`);
  }

  if (!response.body) {
    throw new Error("QA stream response body is empty");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const event = parseSseEvent(part);
      if (event) {
        onEvent(event);
      }
    }
  }

  buffer += decoder.decode();
  const finalEvent = parseSseEvent(buffer);
  if (finalEvent) {
    onEvent(finalEvent);
  }
}

function parseSseEvent(raw: string): QaStreamEvent | null {
  const lines = raw.split(/\r?\n/);
  const eventLine = lines.find((line) => line.startsWith("event: "));
  const dataLine = lines.find((line) => line.startsWith("data: "));

  if (!eventLine || !dataLine) {
    return null;
  }

  return {
    event: eventLine.slice("event: ".length),
    data: JSON.parse(dataLine.slice("data: ".length))
  } as QaStreamEvent;
}
```

- [ ] **Step 5: Run frontend build**

Run:

```powershell
npm run build
```

From `frontend/`.

Expected: build passes, with the existing Vite chunk-size warning acceptable.

- [ ] **Step 6: Commit frontend QA API contract**

Run:

```powershell
git add frontend/src/types/qa.ts frontend/src/types/qa.contract.ts frontend/src/api/qa.ts
git commit -m "feat: add QA stream frontend contract"
```

Expected: commit succeeds.

### Task 3: Real Local Sessions, New Session, Delete Session, and Search

**Files:**
- Modify: `frontend/src/chat/conversationModel.ts`
- Delete: `frontend/src/chat/initialConversations.ts`
- Modify: `frontend/src/stores/chat.ts`
- Modify: `frontend/src/views/ChatView.vue`
- Modify: `frontend/src/components/app/HistorySidebar.vue`
- Modify: `frontend/src/styles/main.css`

- [ ] **Step 1: Update conversation model**

In `frontend/src/chat/conversationModel.ts`, replace the file with:

```ts
import type { BackendSessionId, QaAskResponse } from "../types/qa";

export type ChatStatus = "idle" | "asking" | "streaming" | "answered" | "refused" | "error";
export type ChatMessageStatus = "complete" | "streaming" | "error";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  status?: ChatMessageStatus;
  response?: QaAskResponse;
}

export interface Conversation {
  id: string;
  backendSessionId?: BackendSessionId;
  title: string;
  time: string;
  group: string;
  status: ChatStatus;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

export interface ConversationSnapshot {
  title: string;
  status: ChatStatus;
  messages: ChatMessage[];
}

type MatchedConversationTitle<
  TConversations extends readonly Conversation[],
  TId extends string
> = Extract<TConversations[number], { id: TId }>["title"];

export function getConversationSnapshot<TConversations extends readonly Conversation[], TId extends string>(
  conversations: TConversations,
  activeConversationId: TId
): {
  title: MatchedConversationTitle<TConversations, TId> extends never ? string : MatchedConversationTitle<TConversations, TId>;
  status: ChatStatus;
  messages: ChatMessage[];
};
export function getConversationSnapshot<TConversations extends readonly Conversation[]>(
  conversations: TConversations,
  activeConversationId: null
): { title: "智能问答"; status: "idle"; messages: [] };
export function getConversationSnapshot(
  conversations: readonly Conversation[],
  activeConversationId: string | null
): ConversationSnapshot;
export function getConversationSnapshot(
  conversations: readonly Conversation[],
  activeConversationId: string | null
): ConversationSnapshot {
  const conversation = conversations.find((item) => item.id === activeConversationId);

  if (!conversation) {
    return {
      title: "智能问答",
      status: "idle",
      messages: []
    };
  }

  return {
    title: conversation.title,
    status: conversation.status,
    messages: conversation.messages
  };
}
```

- [ ] **Step 2: Remove mock initial conversations**

Delete `frontend/src/chat/initialConversations.ts`.

- [ ] **Step 3: Replace chat store with real local sessions**

In `frontend/src/stores/chat.ts`, replace the file with:

```ts
import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { askQuestionStream } from "../api/qa";
import { copyTextToClipboard } from "../chat/clipboard";
import { getConversationSnapshot, type ChatMessage, type Conversation } from "../chat/conversationModel";
import { describeAnswerType } from "../chat/qaPresentation";
import type { BackendSessionId, QaAskResponse, QaStreamEvent } from "../types/qa";

function createMessageId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createBackendSessionId(): BackendSessionId {
  return crypto.randomUUID() as BackendSessionId;
}

export function currentChatTime() {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(new Date());
}

function currentGroupLabel(date = new Date()) {
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);

  if (date.toDateString() === today.toDateString()) {
    return "今天";
  }

  if (date.toDateString() === yesterday.toDateString()) {
    return "昨天";
  }

  return "更早";
}

function createConversation(question: string, backendSessionId: BackendSessionId, userMessage: ChatMessage): Conversation {
  const now = Date.now();

  return {
    id: createMessageId(),
    backendSessionId,
    title: question,
    time: userMessage.createdAt,
    group: currentGroupLabel(new Date(now)),
    status: "asking",
    messages: [userMessage],
    createdAt: now,
    updatedAt: now
  };
}

export const useChatStore = defineStore("chat", () => {
  const question = ref("");
  const conversations = ref<Conversation[]>([]);
  const activeConversationId = ref<string | null>(null);
  const lastQuestion = ref("");
  const errorMessage = ref("");
  const copyMessage = ref("");
  const historyQuery = ref("");
  const streamStatusMessage = ref("");
  const activeStreamController = ref<AbortController | null>(null);

  const activeSnapshot = computed(() => getConversationSnapshot(conversations.value, activeConversationId.value));
  const status = computed(() => activeSnapshot.value.status);
  const messages = computed(() => activeSnapshot.value.messages);
  const latestResponse = computed(() => {
    const assistantMessages = messages.value.filter((message) => message.role === "assistant");
    return assistantMessages.at(-1)?.response ?? null;
  });
  const pageTitle = computed(() => activeSnapshot.value.title);
  const answerDescription = computed(() =>
    latestResponse.value ? describeAnswerType(latestResponse.value.answer_type) : describeAnswerType("none")
  );
  const canSend = computed(() => question.value.trim().length > 0 && status.value !== "asking" && status.value !== "streaming");
  const historyGroups = computed(() => {
    const query = historyQuery.value.trim().toLowerCase();
    const groupLabels = ["今天", "昨天", "更早"];

    return groupLabels
      .map((label) => ({
        label,
        items: conversations.value.filter((conversation) => {
          const matchesGroup = conversation.group === label;
          const matchesSearch =
            !query ||
            conversation.title.toLowerCase().includes(query) ||
            conversation.messages.some((message) => message.content.toLowerCase().includes(query));
          return matchesGroup && matchesSearch;
        })
      }))
      .filter((group) => group.items.length > 0);
  });
  const hasHistorySearchResults = computed(() => historyGroups.value.length > 0);

  function abortActiveStream() {
    activeStreamController.value?.abort();
    activeStreamController.value = null;
  }

  function newConversation() {
    abortActiveStream();
    activeConversationId.value = null;
    question.value = "";
    errorMessage.value = "";
    copyMessage.value = "";
    streamStatusMessage.value = "";
  }

  function deleteConversation(conversationId: string) {
    const wasActive = activeConversationId.value === conversationId;
    if (wasActive) {
      abortActiveStream();
      activeConversationId.value = null;
      question.value = "";
      errorMessage.value = "";
      streamStatusMessage.value = "";
    }

    conversations.value = conversations.value.filter((conversation) => conversation.id !== conversationId);
  }

  async function sendQuestion(nextQuestion = question.value) {
    const normalizedQuestion = nextQuestion.trim();

    if (!normalizedQuestion || status.value === "asking" || status.value === "streaming") {
      return;
    }

    abortActiveStream();

    const existingConversation = conversations.value.find((conversation) => conversation.id === activeConversationId.value);
    const backendSessionId = existingConversation?.backendSessionId ?? createBackendSessionId();
    const userMessage: ChatMessage = {
      id: createMessageId(),
      role: "user",
      content: normalizedQuestion,
      createdAt: currentChatTime(),
      status: "complete"
    };
    const assistantMessage: ChatMessage = {
      id: createMessageId(),
      role: "assistant",
      content: "",
      createdAt: currentChatTime(),
      status: "streaming"
    };

    question.value = "";
    lastQuestion.value = normalizedQuestion;
    errorMessage.value = "";
    copyMessage.value = "";
    streamStatusMessage.value = "正在连接问答服务...";

    let conversation = existingConversation;
    if (conversation) {
      conversation.title = normalizedQuestion;
      conversation.backendSessionId = backendSessionId;
      conversation.time = userMessage.createdAt;
      conversation.status = "streaming";
      conversation.updatedAt = Date.now();
      conversation.messages = [...conversation.messages, userMessage, assistantMessage];
    } else {
      conversation = createConversation(normalizedQuestion, backendSessionId, userMessage);
      conversation.status = "streaming";
      conversation.messages = [userMessage, assistantMessage];
      conversations.value.unshift(conversation);
      activeConversationId.value = conversation.id;
    }

    const targetConversationId = conversation.id;
    const targetAssistantMessageId = assistantMessage.id;
    const controller = new AbortController();
    activeStreamController.value = controller;

    try {
      await askQuestionStream(
        { question: normalizedQuestion, session_id: backendSessionId },
        {
          signal: controller.signal,
          onEvent: (event) => applyStreamEvent(targetConversationId, targetAssistantMessageId, event)
        }
      );
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }

      const target = conversations.value.find((item) => item.id === targetConversationId);
      errorMessage.value = "问答接口暂时不可用，请确认后端服务已启动后重试。";

      if (target) {
        target.status = "error";
        target.messages = target.messages.map((message) =>
          message.id === targetAssistantMessageId ? { ...message, status: "error", content: errorMessage.value } : message
        );
      }
    } finally {
      if (activeStreamController.value === controller) {
        activeStreamController.value = null;
      }
      streamStatusMessage.value = "";
    }
  }

  function applyStreamEvent(conversationId: string, assistantMessageId: string, event: QaStreamEvent) {
    const conversation = conversations.value.find((item) => item.id === conversationId);
    if (!conversation || activeConversationId.value !== conversationId) {
      return;
    }

    if (event.event === "status") {
      streamStatusMessage.value = event.data.message;
      return;
    }

    if (event.event === "answer_delta") {
      conversation.messages = conversation.messages.map((message) =>
        message.id === assistantMessageId ? { ...message, content: `${message.content}${event.data.text}` } : message
      );
      return;
    }

    if (event.event === "done") {
      updateConversationFromResponse(conversation, assistantMessageId, event.data);
      return;
    }

    if (event.event === "error") {
      errorMessage.value = event.data.message;
      conversation.status = "error";
      conversation.messages = conversation.messages.map((message) =>
        message.id === assistantMessageId ? { ...message, status: "error", content: event.data.message } : message
      );
    }
  }

  function updateConversationFromResponse(
    conversation: Conversation,
    assistantMessageId: string,
    response: QaAskResponse
  ) {
    conversation.backendSessionId = response.session_id;
    conversation.status = response.answer_type === "refused" ? "refused" : "answered";
    conversation.updatedAt = Date.now();
    conversation.messages = conversation.messages.map((message) =>
      message.id === assistantMessageId
        ? {
            ...message,
            content: response.answer || message.content,
            status: "complete",
            response
          }
        : message
    );
  }

  function selectConversation(conversationId: string) {
    activeConversationId.value = conversationId;
    errorMessage.value = "";
    copyMessage.value = "";
    streamStatusMessage.value = "";
  }

  function retryLastQuestion() {
    const conversation = conversations.value.find((item) => item.id === activeConversationId.value);
    const latestUserQuestion = [...(conversation?.messages ?? [])].reverse().find((message) => message.role === "user")?.content;

    if (!conversation || !latestUserQuestion) {
      return;
    }

    conversation.messages = conversation.messages.filter((message, index, allMessages) => {
      if (message.role !== "assistant") {
        return true;
      }

      const latestUserIndex = allMessages.findLastIndex((item) => item.role === "user");
      return index < latestUserIndex;
    });
    void sendQuestion(latestUserQuestion);
  }

  async function copyAnswer(answer = latestResponse.value?.answer ?? "") {
    const result = await copyTextToClipboard(answer);
    copyMessage.value = result.ok ? "回答已复制到剪贴板" : "复制失败，请手动选中回答文本复制";
  }

  function logout() {
    abortActiveStream();
    localStorage.removeItem("pvqa-role");
  }

  return {
    question,
    conversations,
    activeConversationId,
    lastQuestion,
    errorMessage,
    copyMessage,
    historyQuery,
    streamStatusMessage,
    activeSnapshot,
    status,
    messages,
    latestResponse,
    pageTitle,
    answerDescription,
    canSend,
    historyGroups,
    hasHistorySearchResults,
    sendQuestion,
    selectConversation,
    retryLastQuestion,
    copyAnswer,
    newConversation,
    deleteConversation,
    logout
  };
});
```

- [ ] **Step 4: Update ChatView wiring**

In `frontend/src/views/ChatView.vue`, replace the file with:

```vue
<script setup lang="ts">
import { storeToRefs } from "pinia";
import { useRouter } from "vue-router";

import HistorySidebar from "../components/app/HistorySidebar.vue";
import ChatWorkspace from "../components/chat/ChatWorkspace.vue";
import { useChatStore } from "../stores/chat";

const router = useRouter();
const chatStore = useChatStore();
const {
  activeConversationId,
  answerDescription,
  canSend,
  copyMessage,
  errorMessage,
  hasHistorySearchResults,
  historyGroups,
  historyQuery,
  latestResponse,
  messages,
  pageTitle,
  question,
  status,
  streamStatusMessage
} = storeToRefs(chatStore);

function logout() {
  chatStore.logout();
  void router.push("/login");
}
</script>

<template>
  <main class="chat-page">
    <HistorySidebar
      v-model:search-query="historyQuery"
      :active-conversation-id="activeConversationId"
      :has-search-results="hasHistorySearchResults"
      :history-groups="historyGroups"
      @delete="chatStore.deleteConversation"
      @new="chatStore.newConversation"
      @logout="logout"
      @select="chatStore.selectConversation"
    />

    <ChatWorkspace
      v-model:question="question"
      :answer-description="answerDescription"
      :can-send="canSend"
      :copy-message="copyMessage"
      :error-message="errorMessage"
      :latest-response="latestResponse"
      :messages="messages"
      :page-title="pageTitle"
      :status="status"
      :stream-status-message="streamStatusMessage"
      @ask="chatStore.sendQuestion"
      @copy="chatStore.copyAnswer"
      @retry="chatStore.retryLastQuestion"
      @send="chatStore.sendQuestion"
    />
  </main>
</template>
```

- [ ] **Step 5: Update HistorySidebar UI**

In `frontend/src/components/app/HistorySidebar.vue`, replace the file with:

```vue
<script setup lang="ts">
import { ChatDotRound, MoreFilled, Plus, Search, UserFilled } from "@element-plus/icons-vue";
import { ref } from "vue";

import logoUrl from "../../assets/logo-transparent.png";
import type { Conversation } from "../../chat/conversationModel";

const searchQuery = defineModel<string>("searchQuery", { required: true });

defineProps<{
  activeConversationId: string | null;
  historyGroups: Array<{
    label: string;
    items: Conversation[];
  }>;
  hasSearchResults: boolean;
  userName?: string;
  userRoleLabel?: string;
  brandTo?: string;
}>();

const emit = defineEmits<{
  select: [conversationId: string];
  new: [];
  delete: [conversationId: string];
  logout: [];
}>();

const openMenuConversationId = ref<string | null>(null);
const userMenuOpen = ref(false);

function toggleConversationMenu(conversationId: string) {
  openMenuConversationId.value = openMenuConversationId.value === conversationId ? null : conversationId;
}

function deleteConversation(conversationId: string) {
  if (window.confirm("确认删除这个会话吗？")) {
    emit("delete", conversationId);
  }
  openMenuConversationId.value = null;
}
</script>

<template>
  <aside class="chat-history">
    <RouterLink class="chat-brand" :to="brandTo ?? '/chat'">
      <img :src="logoUrl" alt="" />
      <strong>光伏智能问答系统</strong>
    </RouterLink>

    <div class="history-search-row">
      <label class="history-search">
        <Search class="history-search-icon" aria-hidden="true" />
        <input v-model="searchQuery" type="search" placeholder="搜索历史会话" />
      </label>
      <button class="history-new-button" type="button" aria-label="新建会话" @click="$emit('new')">
        <Plus aria-hidden="true" />
      </button>
    </div>

    <div class="history-groups">
      <p v-if="searchQuery && !hasSearchResults" class="history-empty">没有找到相关会话</p>

      <section v-for="group in historyGroups" :key="group.label" class="history-group">
        <h2>{{ group.label }}</h2>
        <div
          v-for="item in group.items"
          :key="item.id"
          class="history-item-shell"
          :class="{ active: activeConversationId === item.id }"
        >
          <button class="history-item" type="button" @click="$emit('select', item.id)">
            <ChatDotRound class="history-item-icon" aria-hidden="true" />
            <span>{{ item.title }}</span>
            <time>{{ item.time }}</time>
          </button>
          <button
            class="history-menu-button"
            type="button"
            aria-label="会话设置"
            @click.stop="toggleConversationMenu(item.id)"
          >
            <MoreFilled aria-hidden="true" />
          </button>
          <div v-if="openMenuConversationId === item.id" class="history-menu">
            <button type="button" @click="deleteConversation(item.id)">删除会话</button>
          </div>
        </div>
      </section>
    </div>

    <div class="chat-user-card">
      <span class="user-avatar"><UserFilled aria-hidden="true" /></span>
      <div>
        <strong>{{ userName ?? "张工" }}</strong>
        <p>{{ userRoleLabel ?? "普通用户" }}</p>
      </div>
      <button class="user-menu-toggle" type="button" aria-label="用户设置" @click="userMenuOpen = !userMenuOpen">
        ▾
      </button>
      <div v-if="userMenuOpen" class="user-menu">
        <button type="button" @click="$emit('logout')">退出系统</button>
      </div>
    </div>
  </aside>
</template>
```

- [ ] **Step 6: Add sidebar styles**

Append these styles near the existing history/user-card styles in `frontend/src/styles/main.css`:

```css
.history-search-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 44px;
  gap: 10px;
}

.history-new-button,
.history-menu-button,
.user-menu-toggle {
  border: 1px solid var(--pv-line);
  background: rgba(255, 255, 255, 0.88);
  color: var(--pv-primary);
  cursor: pointer;
}

.history-new-button {
  border-radius: 10px;
}

.history-new-button svg,
.history-menu-button svg {
  width: 18px;
  height: 18px;
}

.history-item-shell {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 30px;
  align-items: center;
  border-radius: 10px;
}

.history-item-shell.active {
  border: 1px solid var(--pv-primary);
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 12px 26px rgba(18, 107, 255, 0.08);
}

.history-item-shell .history-item {
  border-color: transparent;
  box-shadow: none;
}

.history-menu-button {
  width: 28px;
  height: 28px;
  border-radius: 8px;
}

.history-menu,
.user-menu {
  position: absolute;
  z-index: 20;
  min-width: 112px;
  padding: 6px;
  border: 1px solid var(--pv-line);
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 18px 42px rgba(28, 77, 156, 0.16);
}

.history-menu {
  right: 0;
  top: 36px;
}

.history-menu button,
.user-menu button {
  width: 100%;
  border: 0;
  border-radius: 8px;
  padding: 9px 10px;
  background: transparent;
  color: #d92d20;
  text-align: left;
  font-weight: 800;
  cursor: pointer;
}

.history-empty {
  margin: 18px 0;
  color: var(--pv-muted);
  font-weight: 700;
}

.chat-user-card {
  position: relative;
}

.user-menu-toggle {
  margin-left: auto;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 900;
}

.user-menu {
  right: 0;
  bottom: 48px;
}
```

- [ ] **Step 7: Run frontend build**

Run:

```powershell
npm run build
```

From `frontend/`.

Expected: build passes, with the existing Vite chunk-size warning acceptable.

- [ ] **Step 8: Commit session/sidebar work**

Run:

```powershell
git add frontend/src/chat/conversationModel.ts frontend/src/chat/initialConversations.ts frontend/src/stores/chat.ts frontend/src/views/ChatView.vue frontend/src/components/app/HistorySidebar.vue frontend/src/styles/main.css
git commit -m "feat: add real local chat sessions"
```

Expected: commit succeeds and includes deletion of mock initial conversations.

### Task 4: Streaming Workspace Rendering and Retry Without Duplicate User Messages

**Files:**
- Modify: `frontend/src/components/chat/ChatWorkspace.vue`
- Modify: `frontend/src/components/chat/AnswerCard.vue`
- Modify: `frontend/src/components/chat/FeedbackBar.vue`
- Modify: `frontend/src/components/chat/ChatComposer.vue`
- Modify: `frontend/src/styles/main.css`

- [ ] **Step 1: Update ChatWorkspace for stream status**

In `frontend/src/components/chat/ChatWorkspace.vue`, change the props block to include `streamStatusMessage`:

```ts
const props = defineProps<{
  pageTitle: string;
  messages: ChatMessage[];
  status: ChatStatus;
  latestResponse: QaAskResponse | null;
  answerDescription: AnswerTypeDescription;
  canSend: boolean;
  copyMessage: string;
  errorMessage: string;
  streamStatusMessage: string;
}>();
```

Replace the loading article with:

```vue
<article v-if="status === 'asking' || status === 'streaming'" class="chat-message assistant stream-status-row">
  <time>{{ currentChatTime() }}</time>
  <div class="message-bubble loading-bubble">
    <Loading class="loading-icon" aria-hidden="true" />
    {{ streamStatusMessage || "正在生成回答..." }}
  </div>
</article>
```

Change the composer disabled state to:

```vue
:disabled="status === 'asking' || status === 'streaming'"
:sending="status === 'asking' || status === 'streaming'"
```

- [ ] **Step 2: Update AnswerCard for streaming and error states**

In `frontend/src/components/chat/AnswerCard.vue`, replace the template with:

```vue
<template>
  <article :class="['chat-message', message.role, message.status]">
    <time>{{ message.createdAt }}</time>
    <div class="message-bubble">
      <p>
        {{ message.content }}
        <span v-if="message.status === 'streaming'" class="stream-cursor" aria-hidden="true"></span>
      </p>
      <SourceReferences v-if="message.response?.references.length" :references="message.response.references" />
    </div>

    <FeedbackBar
      v-if="message.role === 'assistant' && message.status !== 'streaming'"
      @copy="$emit('copy', message.content)"
      @retry="$emit('retry')"
    />
  </article>
</template>
```

- [ ] **Step 3: Make composer multiline behavior explicit**

In `frontend/src/components/chat/ChatComposer.vue`, keep the existing Enter send handler and add a title attribute to the textarea:

```vue
<textarea
  v-model="model"
  :disabled="disabled"
  rows="1"
  placeholder="请输入你的问题，系统将基于知识库回答"
  title="按 Enter 发送，按 Shift+Enter 换行"
  @keydown.enter.exact.prevent="$emit('send')"
/>
```

Expected behavior: Enter sends; Shift+Enter falls through to native textarea newline.

- [ ] **Step 4: Add streaming cursor styles**

Append to `frontend/src/styles/main.css`:

```css
.stream-cursor {
  display: inline-block;
  width: 8px;
  height: 1.1em;
  margin-left: 4px;
  border-radius: 4px;
  background: var(--pv-primary);
  vertical-align: -0.18em;
  animation: stream-cursor-blink 1s steps(2, start) infinite;
}

.chat-message.error .message-bubble {
  border-color: rgba(240, 68, 56, 0.28);
  background: rgba(240, 68, 56, 0.06);
}

@keyframes stream-cursor-blink {
  50% {
    opacity: 0;
  }
}
```

- [ ] **Step 5: Run frontend build**

Run:

```powershell
npm run build
```

From `frontend/`.

Expected: build passes, with the existing Vite chunk-size warning acceptable.

- [ ] **Step 6: Manually verify retry behavior**

Start frontend:

```powershell
npm run dev
```

From `frontend/`.

With backend running, open `/chat`, send one question, click `重新生成`, and verify the same user question is not duplicated in the transcript.

- [ ] **Step 7: Commit streaming rendering**

Run:

```powershell
git add frontend/src/components/chat/ChatWorkspace.vue frontend/src/components/chat/AnswerCard.vue frontend/src/components/chat/ChatComposer.vue frontend/src/styles/main.css
git commit -m "feat: render streaming QA responses"
```

Expected: commit succeeds.

### Task 5: Document-File-Name-Only References

**Files:**
- Modify: `frontend/src/components/chat/SourceReferences.vue`
- Modify: `frontend/src/styles/main.css`

- [ ] **Step 1: Replace SourceReferences display logic**

In `frontend/src/components/chat/SourceReferences.vue`, replace the file with:

```vue
<script setup lang="ts">
import { computed } from "vue";
import { Document } from "@element-plus/icons-vue";

import type { QaReference } from "../../types/qa";

const props = defineProps<{
  references: QaReference[];
}>();

const documentFileNames = computed(() => {
  const names = props.references
    .filter((reference) => reference.visible)
    .map((reference) => reference.document_file_name)
    .filter((name): name is string => Boolean(name?.trim()));

  return Array.from(new Set(names));
});
</script>

<template>
  <section v-if="documentFileNames.length > 0" class="source-panel document-only-sources" aria-label="来源文档">
    <div class="source-panel-head static">
      <Document class="source-icon" aria-hidden="true" />
      <strong>来源文档</strong>
    </div>
    <div class="source-file-list">
      <span v-for="fileName in documentFileNames" :key="fileName" class="source-file-chip">{{ fileName }}</span>
    </div>
  </section>
</template>
```

- [ ] **Step 2: Add document-only source styles**

Append to `frontend/src/styles/main.css`:

```css
.source-panel-head.static {
  cursor: default;
}

.source-file-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.source-file-chip {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 5px 10px;
  border: 1px solid rgba(18, 107, 255, 0.18);
  border-radius: 999px;
  background: rgba(239, 246, 255, 0.88);
  color: #1f4f9a;
  font-size: 13px;
  font-weight: 800;
}
```

- [ ] **Step 3: Run frontend build**

Run:

```powershell
npm run build
```

From `frontend/`.

Expected: build passes, with the existing Vite chunk-size warning acceptable.

- [ ] **Step 4: Commit reference display**

Run:

```powershell
git add frontend/src/components/chat/SourceReferences.vue frontend/src/styles/main.css
git commit -m "feat: show document file names for QA references"
```

Expected: commit succeeds.

### Task 6: Logout Menu Behavior and Final Verification

**Files:**
- Modify: `frontend/src/components/app/HistorySidebar.vue`
- Modify: `frontend/src/stores/chat.ts`
- Verify: full frontend/backend commands

- [ ] **Step 1: Confirm logout state cleanup is intentionally minimal**

Keep `logout()` in `frontend/src/stores/chat.ts` as:

```ts
function logout() {
  abortActiveStream();
  localStorage.removeItem("pvqa-role");
}
```

Reason: current login is local mock and only stores `pvqa-role` plus optional `pvqa-account`. Do not remove `pvqa-account`, because the login form has a "remember account" control.

- [ ] **Step 2: Verify user dropdown routes to login**

In `frontend/src/views/ChatView.vue`, ensure the logout handler remains:

```ts
function logout() {
  chatStore.logout();
  void router.push("/login");
}
```

- [ ] **Step 3: Run full frontend build**

Run:

```powershell
npm run build
```

From `frontend/`.

Expected: build passes, with the existing Vite chunk-size warning acceptable.

- [ ] **Step 4: Run backend QA API tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_qa_api.py', '-q']))"
```

Expected: all QA API tests pass, with the existing Starlette/httpx warning acceptable.

- [ ] **Step 5: Manual QA checklist**

Run backend API as the project normally does, then run:

```powershell
npm run dev
```

From `frontend/`.

Verify in the browser:

- Empty `/chat` page has no mock history.
- Clicking the new-session icon clears the current working area and does not create an empty history item.
- Sending the first question creates one history item.
- Streaming answer appears incrementally in the assistant message.
- Switching to another session during a stream does not append chunks into the wrong session.
- Searching by title filters history groups.
- Searching a missing term shows "没有找到相关会话".
- Three-dot menu can delete a non-active session without changing the active session.
- Deleting the active session returns to the empty new-chat state.
- "重新生成" does not duplicate the user message.
- References show only document file names, not heading path, excerpt, score, or "片段".
- The user dropdown shows "退出系统" and returns to `/login`.

- [ ] **Step 6: Commit final verification fixes if any**

If manual QA reveals tiny CSS or wiring fixes, commit them with:

```powershell
git add frontend backend
git commit -m "fix: polish QA chat integration"
```

If no fixes are needed, do not create an empty commit.

## Self-Review

**Spec coverage:** This plan covers removal of mock history, real local sessions, new session button beside search, delete via three-dot menu, implemented history search without `⌘K`, stream model integration with backend `POST /api/qa/ask/stream`, document-file-name-only references, and user settings/logout dropdown.

**Known backend contract note:** The current backend reference schema does not expose document file names. Task 1 adds `document_file_name` to backend responses before frontend display work.

**Deferred by user request:** Detailed error-message differentiation remains deferred. The implementation keeps one user-facing generic error while preserving stream error events in the code path.

**Placeholder scan:** No task uses TBD/TODO/fill-in placeholders. Each code-changing step includes concrete code.

**Type consistency:** The plan consistently uses `BackendSessionId`, `QaReference.document_file_name`, `QaReference.visible`, `QaStreamEvent`, `Conversation.status`, and `ChatMessage.status`.
