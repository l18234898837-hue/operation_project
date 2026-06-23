<script setup lang="ts">
import { Checked, Hide, Key, Lock, User, View } from "@element-plus/icons-vue";
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import logoUrl from "../assets/logo-transparent.png";

const router = useRouter();

type LoginRole = "user" | "admin";

const account = ref("");
const password = ref("");
const role = ref<LoginRole>("user");
const rememberAccount = ref(true);
const showPolicy = ref(false);
const showPassword = ref(false);
const errorMessage = ref("");

const roleOptions: Array<{
  value: LoginRole;
  title: string;
  description: string;
}> = [
  {
    value: "user",
    title: "普通用户",
    description: "进入问答页，专注提问、回答、引用和反馈主流程。"
  },
  {
    value: "admin",
    title: "管理员",
    description: "进入管理工作台，查看文档状态、问答日志和未命中问题。"
  }
];

onMounted(() => {
  const savedAccount = localStorage.getItem("pvqa-account");
  const savedRole = localStorage.getItem("pvqa-role") as LoginRole | null;

  if (savedAccount) {
    account.value = savedAccount;
  }

  if (savedRole === "admin" || savedRole === "user") {
    role.value = savedRole;
  }
});

function submitLogin() {
  errorMessage.value = "";

  if (!account.value.trim()) {
    errorMessage.value = "请输入账号";
    return;
  }

  if (!password.value.trim()) {
    errorMessage.value = "请输入密码";
    return;
  }

  if (rememberAccount.value) {
    localStorage.setItem("pvqa-account", account.value.trim());
  } else {
    localStorage.removeItem("pvqa-account");
  }

  localStorage.setItem("pvqa-role", role.value);
  router.push(role.value === "admin" ? "/admin/documents" : "/chat");
}
</script>

<template>
  <main class="app-canvas">
    <section class="login-shell">
      <aside class="login-card">
        <div class="login-card-head">
          <img class="login-card-logo" :src="logoUrl" alt="" />
          <h1>光伏智能问答系统</h1>
          <p>可追踪的企业知识问答入口</p>
        </div>

        <form class="login-form" @submit.prevent="submitLogin">
          <label class="form-field">
            <User class="field-icon" aria-hidden="true" />
            <input v-model="account" autocomplete="username" placeholder="请输入账号" type="text" />
          </label>

          <div class="form-field">
            <Lock class="field-icon" aria-hidden="true" />
            <input
              v-model="password"
              autocomplete="current-password"
              placeholder="请输入密码"
              :type="showPassword ? 'text' : 'password'"
            />
            <button
              class="field-eye-button"
              type="button"
              :aria-label="showPassword ? '隐藏密码' : '显示密码'"
              @click="showPassword = !showPassword"
            >
              <View v-if="showPassword" class="field-eye" aria-hidden="true" />
              <Hide v-else class="field-eye" aria-hidden="true" />
            </button>
          </div>

          <p class="role-label">角色</p>
          <div class="role-selector" aria-label="选择角色">
            <button
              v-for="item in roleOptions"
              :key="item.value"
              class="role-card"
              :class="{ active: role === item.value }"
              type="button"
              @click="role = item.value"
            >
              <User v-if="item.value === 'user'" class="role-icon" aria-hidden="true" />
              <Key v-else class="role-icon" aria-hidden="true" />
              <strong>{{ item.title }}</strong>
              <span>{{ item.description }}</span>
            </button>
          </div>

          <div class="login-options">
            <label class="check-line">
              <input v-model="rememberAccount" type="checkbox" />
              <span>记住账号</span>
            </label>
            <button class="text-button" type="button" @click="showPolicy = true">授权说明</button>
          </div>

          <p v-if="errorMessage" class="form-error">{{ errorMessage }}</p>

          <button class="primary-login-button" type="submit">登录</button>
        </form>

        <div class="login-policy-line">
          <Checked class="policy-icon" aria-hidden="true" />
          <span>首次使用请阅读</span>
          <button class="text-button" type="button" @click="showPolicy = true">授权说明</button>
        </div>
      </aside>
    </section>

    <el-dialog v-model="showPolicy" title="授权说明" width="520px">
      <div class="policy-copy">
        <p>本系统第一阶段仅用于光伏运维文档知识库问答验证。</p>
        <p>系统回答应基于知识库证据，无法确认依据时会拒答或提示补充信息。</p>
        <p>当前登录为本地 mock，不代表生产权限模型；请勿在页面中输入真实敏感账号密码。</p>
      </div>
      <template #footer>
        <button class="dialog-confirm" type="button" @click="showPolicy = false">我已了解</button>
      </template>
    </el-dialog>
  </main>
</template>
