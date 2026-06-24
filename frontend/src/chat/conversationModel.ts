import type { QaAskResponse } from "../types/qa";

export type ChatStatus = "idle" | "asking" | "answered" | "refused" | "error";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  response?: QaAskResponse;
}

export interface Conversation {
  id: string;
  title: string;
  time: string;
  group: string;
  status: ChatStatus;
  messages: ChatMessage[];
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
