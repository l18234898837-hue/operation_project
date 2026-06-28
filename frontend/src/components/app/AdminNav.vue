<script setup lang="ts">
import { Expand, Fold } from "@element-plus/icons-vue";

import logoUrl from "../../assets/logo-transparent.png";
import { adminNavItems } from "./adminNavItems";

const collapsed = defineModel<boolean>("collapsed", { required: true });
</script>

<template>
  <aside class="admin-nav" :class="{ collapsed }">
    <RouterLink class="admin-brand" to="/admin/chat">
      <img :src="logoUrl" alt="光伏智能问答系统" />
      <span>光伏智能问答</span>
    </RouterLink>

    <button
      class="admin-nav-toggle"
      type="button"
      :aria-label="collapsed ? '展开管理员导航' : '折叠管理员导航'"
      :aria-pressed="collapsed"
      @click="collapsed = !collapsed"
    >
      <Expand v-if="collapsed" aria-hidden="true" />
      <Fold v-else aria-hidden="true" />
    </button>

    <nav class="admin-nav-list" aria-label="管理员导航">
      <RouterLink v-for="item in adminNavItems" :key="item.to" class="admin-nav-link" :to="item.to">
        <span class="admin-nav-icon">
          <component :is="item.icon" aria-hidden="true" />
        </span>
        <strong>{{ item.label }}</strong>
      </RouterLink>
    </nav>
  </aside>
</template>
