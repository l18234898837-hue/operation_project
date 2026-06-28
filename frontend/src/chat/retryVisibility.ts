import type { ChatMessage } from "./conversationModel";

export function canRegenerateAssistantMessage(messages: readonly ChatMessage[], message: ChatMessage): boolean {
  const latestMessage = messages.at(-1);

  return latestMessage?.id === message.id && message.role === "assistant" && message.status !== "streaming";
}
