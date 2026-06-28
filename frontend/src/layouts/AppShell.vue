<script setup lang="ts">
import logoUrl from "../assets/logo-transparent.png";

const navItems = [
  { label: "智能问答", to: "/chat" },
  { label: "文档管理", to: "/admin/documents" },
  { label: "基础日志", to: "/admin/logs" }
];
</script>

<template>
  <div class="app-canvas">
    <div class="pv-shell">
      <aside class="side-nav">
        <RouterLink class="brand-lockup" to="/chat">
          <img class="brand-mark brand-logo" :src="logoUrl" alt="光伏智能问答系统" />
          <div>
            <strong>光伏智能问答</strong>
            <p class="eyebrow">RAG MVP</p>
          </div>
        </RouterLink>

        <section class="nav-section">
          <span class="nav-label">Module 02 页面壳</span>
          <nav class="nav-list" aria-label="主导航">
            <RouterLink v-for="item in navItems" :key="item.to" class="nav-link" :to="item.to">
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
