import { ChatDotRound, Collection, Document } from "@element-plus/icons-vue";

export const adminNavItems = [
  { label: "智能问答", to: "/admin/chat", icon: ChatDotRound },
  { label: "文档管理", to: "/admin/documents", icon: Document },
  { label: "问答日志", to: "/admin/logs", icon: Collection }
] as const;
