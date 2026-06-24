import { useChatStore } from "../stores/chat";
import type { ChatMessage, ChatStatus, Conversation } from "./conversationModel";

type Assert<T extends true> = T;
type IsAssignable<TValue, TExpected> = TValue extends TExpected ? true : false;

const store = useChatStore();

type StatusIsChatStatus = Assert<IsAssignable<typeof store.status, ChatStatus>>;
type MessagesAreChatMessages = Assert<IsAssignable<typeof store.messages, ChatMessage[]>>;
type ConversationsAreConversationList = Assert<IsAssignable<typeof store.conversations, Conversation[]>>;

void store.pageTitle;
void store.latestResponse;
void store.historyGroups;
void store.answerDescription;
void store.canSend;
void store.question;
void store.errorMessage;
void store.copyMessage;
void store.sendQuestion("组件热斑如何排查？");
void store.selectConversation("daily-inspection");
void store.retryLastQuestion();
void store.copyAnswer("复制这条回答");
void (null as unknown as StatusIsChatStatus);
void (null as unknown as MessagesAreChatMessages);
void (null as unknown as ConversationsAreConversationList);
