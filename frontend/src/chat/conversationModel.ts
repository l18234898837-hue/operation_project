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

export interface PersistedChatState {
  conversations: Conversation[];
  activeConversationId: string | null;
}

type SnapshotConversation = Pick<Conversation, "id" | "title" | "status" | "messages">;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isChatStatus(value: unknown): value is ChatStatus {
  return (
    value === "idle" ||
    value === "asking" ||
    value === "streaming" ||
    value === "answered" ||
    value === "refused" ||
    value === "error"
  );
}

function isMessageStatus(value: unknown): value is ChatMessageStatus {
  return value === "complete" || value === "streaming" || value === "error";
}

function isRole(value: unknown): value is ChatMessage["role"] {
  return value === "user" || value === "assistant";
}

function isQaAskResponse(value: unknown): value is QaAskResponse {
  return (
    isRecord(value) &&
    typeof value.session_id === "string" &&
    typeof value.trace_id === "string" &&
    typeof value.answer_type === "string" &&
    typeof value.intent === "string" &&
    typeof value.answer === "string" &&
    Array.isArray(value.references) &&
    isRecord(value.decision)
  );
}

function sanitizeMessage(value: unknown): ChatMessage | null {
  if (!isRecord(value) || typeof value.id !== "string" || !isRole(value.role) || typeof value.content !== "string") {
    return null;
  }

  const status = isMessageStatus(value.status) ? value.status : "complete";
  const interruptedStreamingAnswer = value.role === "assistant" && status === "streaming";

  return {
    id: value.id,
    role: value.role,
    content: interruptedStreamingAnswer ? value.content.trim() || "回答已中断" : value.content,
    createdAt: typeof value.createdAt === "string" ? value.createdAt : "",
    status: interruptedStreamingAnswer ? "error" : status,
    response: isQaAskResponse(value.response) ? value.response : undefined
  };
}

function sanitizeConversation(value: unknown): Conversation | null {
  if (!isRecord(value) || typeof value.id !== "string") {
    return null;
  }

  const messages = Array.isArray(value.messages) ? value.messages.map(sanitizeMessage).filter((item) => item !== null) : [];
  const status = isChatStatus(value.status) ? value.status : "idle";
  const restoredStatus = status === "asking" || status === "streaming" ? "error" : status;
  const now = Date.now();

  return {
    id: value.id,
    backendSessionId: typeof value.backendSessionId === "string" ? (value.backendSessionId as BackendSessionId) : undefined,
    title: typeof value.title === "string" && value.title.trim() ? value.title : "未命名会话",
    time: typeof value.time === "string" ? value.time : "",
    group: typeof value.group === "string" ? value.group : "更早",
    status: restoredStatus,
    messages,
    createdAt: typeof value.createdAt === "number" ? value.createdAt : now,
    updatedAt: typeof value.updatedAt === "number" ? value.updatedAt : now
  };
}

export function sanitizePersistedChatState(value: unknown): PersistedChatState {
  if (!isRecord(value)) {
    return { conversations: [], activeConversationId: null };
  }

  const conversations = Array.isArray(value.conversations)
    ? value.conversations.map(sanitizeConversation).filter((item) => item !== null)
    : [];
  const activeConversationId =
    typeof value.activeConversationId === "string" &&
    conversations.some((conversation) => conversation.id === value.activeConversationId)
      ? value.activeConversationId
      : null;

  return { conversations, activeConversationId };
}

type MatchedConversationTitle<
  TConversations extends readonly SnapshotConversation[],
  TId extends string
> = Extract<TConversations[number], { id: TId }>["title"];

export function getConversationSnapshot<TConversations extends readonly SnapshotConversation[], TId extends string>(
  conversations: TConversations,
  activeConversationId: TId
): {
  title: MatchedConversationTitle<TConversations, TId> extends never ? string : MatchedConversationTitle<TConversations, TId>;
  status: ChatStatus;
  messages: ChatMessage[];
};
export function getConversationSnapshot<TConversations extends readonly SnapshotConversation[]>(
  conversations: TConversations,
  activeConversationId: null
): { title: "智能问答"; status: "idle"; messages: [] };
export function getConversationSnapshot(
  conversations: readonly SnapshotConversation[],
  activeConversationId: string | null
): ConversationSnapshot;
export function getConversationSnapshot(
  conversations: readonly SnapshotConversation[],
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
