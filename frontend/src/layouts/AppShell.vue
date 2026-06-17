<script setup lang="ts">
const navItems = [
  { label: "智能问答", to: "/chat", code: "QA" },
  { label: "文档管理", to: "/admin/documents", code: "DOC" },
  { label: "基础日志", to: "/admin/logs", code: "LOG" },
  { label: "未命中问题", to: "/admin/unanswered", code: "MISS" }
];
</script>

<template>
  <div class="app-canvas">
    <div class="pv-shell">
      <aside class="side-nav">
        <RouterLink class="brand-lockup" to="/chat">
          <span class="brand-mark">PV</span>
          <div>
            <strong>光伏智能问答</strong>
            <p class="eyebrow">RAG MVP</p>
          </div>
        </RouterLink>

        <section class="nav-section">
          <span class="nav-label">Module 02 页面壳</span>
          <nav class="nav-list" aria-label="主导航">
            <RouterLink v-for="item in navItems" :key="item.to" class="nav-link" :to="item.to">
              <span class="nav-chip">{{ item.code }}</span>
              <span>{{ item.label }}</span>
            </RouterLink>
          </nav>
        </section>

        <section class="boundary-note">
          当前只实现前端页面入口、角色分流和 mock 状态；真实鉴权、上传、问答和日志接口在后续模块接入。
        </section>
      </aside>

      <main class="shell-main">
        <RouterView />
      </main>
    </div>
  </div>
</template>
