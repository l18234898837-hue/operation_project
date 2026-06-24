import { ChatDotRound, Collection, Document } from "@element-plus/icons-vue";

export const adminNavItems = [
  { label: "智能问答", to: "/admin/chat", code: "QA", icon: ChatDotRound },
  { label: "文档管理", to: "/admin/documents", code: "DOC", icon: Document },
  { label: "问答日志", to: "/admin/logs", code: "LOG", icon: Collection }
] as const;
