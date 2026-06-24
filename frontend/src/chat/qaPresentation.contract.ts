import { describeAnswerType, formatConfidence } from "./qaPresentation";
import { getConversationSnapshot, type Conversation } from "./conversationModel";

const ragLabel: "基于知识库回答" = describeAnswerType("rag").label;
const refusedTone: "warn" = describeAnswerType("refused").tone;
const missingConfidence: "暂无置信度" = formatConfidence(null);
const percentConfidence: "86%" = formatConfidence(0.858);

void ragLabel;
void refusedTone;
void missingConfidence;
void percentConfidence;

const conversations = [
  {
    id: "daily-inspection",
    title: "光伏电站日常巡检有哪些内容？",
    time: "11:20",
    group: "今天",
    status: "answered",
    createdAt: 1_717_569_600_000,
    updatedAt: 1_717_573_200_000,
    messages: [
      {
        id: "m1",
        role: "user",
        content: "光伏电站日常巡检有哪些内容？",
        createdAt: "11:20"
      }
    ]
  }
] as const satisfies readonly Conversation[];

const selectedConversationTitle: "光伏电站日常巡检有哪些内容？" = getConversationSnapshot(
  conversations,
  "daily-inspection"
).title;
const emptyConversationStatus: "idle" = getConversationSnapshot(conversations, null).status;

void selectedConversationTitle;
void emptyConversationStatus;
