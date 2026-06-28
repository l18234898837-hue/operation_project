import { canRegenerateAssistantMessage } from "./retryVisibility";
import type { ChatMessage } from "./conversationModel";

const messages = [
  { id: "q-1", role: "user", content: "组件发热如何排查？", createdAt: "10:00", status: "complete" },
  { id: "a-1", role: "assistant", content: "先检查散热与负载。", createdAt: "10:01", status: "complete" },
  { id: "q-2", role: "user", content: "逆变器效率如何提升？", createdAt: "10:02", status: "complete" },
  { id: "a-2", role: "assistant", content: "可从 MPPT 与线损优化。", createdAt: "10:03", status: "complete" }
] satisfies ChatMessage[];

const latestAssistantCanRegenerate: boolean = canRegenerateAssistantMessage(messages, messages[3]);
const historicalAssistantCannotRegenerate: boolean = canRegenerateAssistantMessage(messages, messages[1]);
const userMessageCannotRegenerate: boolean = canRegenerateAssistantMessage(messages, messages[2]);

const pendingMessages = [
  ...messages,
  { id: "q-3", role: "user", content: "还有哪些检查项？", createdAt: "10:04", status: "complete" }
] satisfies ChatMessage[];

const previousAssistantBecomesHistory: boolean = canRegenerateAssistantMessage(pendingMessages, messages[3]);

void latestAssistantCanRegenerate;
void historicalAssistantCannotRegenerate;
void userMessageCannotRegenerate;
void previousAssistantBecomesHistory;
