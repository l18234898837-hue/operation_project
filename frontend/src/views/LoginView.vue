<script setup lang="ts">
import { useRouter } from "vue-router";

const router = useRouter();

function enterAs(role: "user" | "admin") {
  localStorage.setItem("pvqa-role", role);
  router.push(role === "admin" ? "/admin/documents" : "/chat");
}
</script>

<template>
  <main class="app-canvas">
    <section class="login-shell">
      <div class="login-hero">
        <div class="brand-lockup">
          <span class="brand-mark">PV</span>
          <div>
            <strong>光伏智能问答系统</strong>
            <p class="eyebrow">Document RAG Web MVP</p>
          </div>
        </div>

        <div>
          <p class="eyebrow">Phase 01</p>
          <h1>让运维资料能被提问、被引用、被追踪。</h1>
          <p class="lead">
            第一阶段聚焦文档知识库 RAG 闭环：上传资料、检索证据、生成带引用的回答，并在证据不足时稳定追问或拒答。
          </p>

          <div class="hero-metrics">
            <div class="metric-tile">
              <span>用户入口</span>
              <strong>极简问答</strong>
            </div>
            <div class="metric-tile">
              <span>管理员入口</span>
              <strong>文档 / 日志 / 未命中</strong>
            </div>
            <div class="metric-tile">
              <span>能力边界</span>
              <strong>不接实时系统</strong>
            </div>
          </div>
        </div>
      </div>

      <aside class="login-card">
        <p class="eyebrow">Role Entrance</p>
        <h2>选择一个本地 mock 角色</h2>
        <p>当前阶段只做角色分流和页面入口控制，不做真实鉴权。后续接入 `/api/auth/*` 后替换这里。</p>

        <div class="role-grid">
          <button class="role-card" type="button" @click="enterAs('user')">
            <strong>普通用户</strong>
            <span>进入问答页，只保留提问、回答、引用和反馈等主流程。</span>
          </button>
          <button class="role-card" type="button" @click="enterAs('admin')">
            <strong>管理员</strong>
            <span>进入管理工作台，查看文档状态、问答日志和未命中问题。</span>
          </button>
        </div>

        <div class="boundary-note">
          授权说明弹窗会在后续交互细化时补齐；当前 Step 1 只确认登录入口和角色路径。
        </div>
      </aside>
    </section>
  </main>
</template>
