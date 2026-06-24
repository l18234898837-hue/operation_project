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

type SnapshotConversation = Pick<Conversation, "id" | "title" | "status" | "messages">;

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
