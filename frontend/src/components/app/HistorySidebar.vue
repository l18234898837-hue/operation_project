<script setup lang="ts">
import { ChatDotRound, Search, UserFilled } from "@element-plus/icons-vue";

import logoUrl from "../../assets/logo-transparent.png";
import type { Conversation } from "../../chat/conversationModel";

defineProps<{
  activeConversationId: string | null;
  historyGroups: Array<{
    label: string;
    items: Conversation[];
  }>;
  userName?: string;
  userRoleLabel?: string;
  brandTo?: string;
}>();

defineEmits<{
  select: [conversationId: string];
}>();
</script>

<template>
  <aside class="chat-history">
    <RouterLink class="chat-brand" :to="brandTo ?? '/chat'">
      <img :src="logoUrl" alt="" />
      <strong>光伏智能问答系统</strong>
    </RouterLink>

    <label class="history-search">
      <Search class="history-search-icon" aria-hidden="true" />
      <input type="search" placeholder="搜索历史会话" />
      <kbd>⌘K</kbd>
    </label>

    <div class="history-groups">
      <section v-for="group in historyGroups" :key="group.label" class="history-group">
        <h2>{{ group.label }}</h2>
        <button
          v-for="item in group.items"
          :key="item.id"
          class="history-item"
          :class="{ active: activeConversationId === item.id }"
          type="button"
          @click="$emit('select', item.id)"
        >
          <ChatDotRound class="history-item-icon" aria-hidden="true" />
          <span>{{ item.title }}</span>
          <time>{{ item.time }}</time>
        </button>
      </section>
    </div>

    <div class="chat-user-card">
      <span class="user-avatar"><UserFilled aria-hidden="true" /></span>
      <div>
        <strong>{{ userName ?? "张工" }}</strong>
        <p>{{ userRoleLabel ?? "普通用户" }}</p>
      </div>
    </div>
  </aside>
</template>
