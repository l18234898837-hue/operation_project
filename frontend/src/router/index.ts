import { createRouter, createWebHistory } from "vue-router";

import AdminShell from "../layouts/AdminShell.vue";
import AdminChatView from "../views/AdminChatView.vue";
import ChatView from "../views/ChatView.vue";
import DocumentManageView from "../views/DocumentManageView.vue";
import LoginView from "../views/LoginView.vue";
import QaLogsView from "../views/QaLogsView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      redirect: "/login"
    },
    {
      path: "/login",
      name: "login",
      component: LoginView
    },
    {
      path: "/chat",
      name: "chat",
      component: ChatView
    },
    {
      path: "/",
      component: AdminShell,
      children: [
        {
          path: "admin/chat",
          name: "admin-chat",
          component: AdminChatView
        },
        {
          path: "admin/documents",
          name: "admin-documents",
          component: DocumentManageView
        },
        {
          path: "admin/logs",
          name: "admin-logs",
          component: QaLogsView
        },
        {
          path: "admin/unanswered",
          redirect: "/admin/logs"
        }
      ]
    }
  ]
});

export default router;
