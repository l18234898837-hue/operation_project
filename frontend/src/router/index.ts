import { createRouter, createWebHistory } from "vue-router";

import AppShell from "../layouts/AppShell.vue";
import ChatView from "../views/ChatView.vue";
import DocumentManageView from "../views/DocumentManageView.vue";
import LoginView from "../views/LoginView.vue";
import QaLogsView from "../views/QaLogsView.vue";
import UnansweredView from "../views/UnansweredView.vue";

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
      path: "/",
      component: AppShell,
      children: [
        {
          path: "chat",
          name: "chat",
          component: ChatView
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
          name: "admin-unanswered",
          component: UnansweredView
        }
      ]
    }
  ]
});

export default router;
