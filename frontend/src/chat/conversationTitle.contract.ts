import { shouldUseQuestionAsConversationTitle } from "../stores/chat";
import { getFirstUserQuestionTitle, type Conversation } from "./conversationModel";

type MinimalConversation = Pick<Conversation, "messages">;

const emptyConversation: MinimalConversation = { messages: [] };
const existingConversation: MinimalConversation = {
  messages: [
    { id: "q-1", role: "user", content: "第一个问题", createdAt: "10:00", status: "complete" },
    { id: "a-1", role: "assistant", content: "第一个回答", createdAt: "10:01", status: "complete" }
  ]
};

const newConversationCanUseQuestionAsTitle: boolean = shouldUseQuestionAsConversationTitle(emptyConversation);
const existingConversationKeepsOriginalTitle: boolean = shouldUseQuestionAsConversationTitle(existingConversation);
const titleComesFromFirstUserQuestion: string = getFirstUserQuestionTitle([
  { id: "q-1", role: "user", content: "第一个问题", createdAt: "10:00", status: "complete" },
  { id: "a-1", role: "assistant", content: "第一个回答", createdAt: "10:01", status: "complete" },
  { id: "q-2", role: "user", content: "最后一个问题", createdAt: "10:02", status: "complete" }
]);

void newConversationCanUseQuestionAsTitle;
void existingConversationKeepsOriginalTitle;
void titleComesFromFirstUserQuestion;
