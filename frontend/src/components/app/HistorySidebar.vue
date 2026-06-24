<script setup lang="ts">
import { ChatDotRound, MoreFilled, Plus, Search, SwitchButton, UserFilled } from "@element-plus/icons-vue";
import { ref } from "vue";

import logoUrl from "../../assets/logo-transparent.png";
import type { Conversation } from "../../chat/conversationModel";

const searchQuery = defineModel<string>("searchQuery", { default: "" });

withDefaults(
  defineProps<{
    activeConversationId: string | null;
    historyGroups: Array<{
      label: string;
      items: Conversation[];
    }>;
    hasSearchResults?: boolean;
    userName?: string;
    userRoleLabel?: string;
    brandTo?: string;
  }>(),
  {
    hasSearchResults: true,
    userName: "张工",
    userRoleLabel: "普通用户",
    brandTo: "/chat"
  }
);

const emit = defineEmits<{
  select: [conversationId: string];
  new: [];
  delete: [conversationId: string];
  logout: [];
}>();

const openConversationMenuId = ref<string | null>(null);
const isUserMenuOpen = ref(false);

function toggleConversationMenu(conversationId: string) {
  openConversationMenuId.value = openConversationMenuId.value === conversationId ? null : conversationId;
}

function selectConversation(conversationId: string) {
  openConversationMenuId.value = null;
  emit("select", conversationId);
}

function deleteConversation(conversation: Conversation) {
  if (window.confirm(`确定删除会话“${conversation.title}”？`)) {
    emit("delete", conversation.id);
  }

  openConversationMenuId.value = null;
}

function createNewSession() {
  openConversationMenuId.value = null;
  emit("new");
}

function logout() {
  isUserMenuOpen.value = false;
  emit("logout");
}
</script>

<template>
  <aside class="chat-history">
    <RouterLink class="chat-brand" :to="brandTo">
      <img :src="logoUrl" alt="" />
      <strong>光伏智能问答系统</strong>
    </RouterLink>

    <div class="history-search-row">
      <label class="history-search">
        <Search class="history-search-icon" aria-hidden="true" />
        <input v-model="searchQuery" type="search" placeholder="搜索历史会话" />
      </label>

      <button class="history-new-button" type="button" aria-label="新建会话" @click="createNewSession">
        <Plus aria-hidden="true" />
      </button>
    </div>

    <div class="history-groups">
      <p v-if="!hasSearchResults" class="history-empty">没有找到相关会话</p>

      <template v-else>
        <section v-for="group in historyGroups" :key="group.label" class="history-group">
          <h2>{{ group.label }}</h2>

          <div
            v-for="item in group.items"
            :key="item.id"
            class="history-item-shell"
            :class="{ active: activeConversationId === item.id }"
          >
            <button class="history-item" type="button" @click="selectConversation(item.id)">
              <ChatDotRound class="history-item-icon" aria-hidden="true" />
              <span>{{ item.title }}</span>
              <time>{{ item.time }}</time>
            </button>

            <button
              class="history-menu-button"
              type="button"
              :aria-expanded="openConversationMenuId === item.id"
              aria-label="会话更多操作"
              @click.stop="toggleConversationMenu(item.id)"
            >
              <MoreFilled aria-hidden="true" />
            </button>

            <div v-if="openConversationMenuId === item.id" class="history-menu">
              <button type="button" @click="deleteConversation(item)">删除会话</button>
            </div>
          </div>
        </section>
      </template>
    </div>

    <div class="chat-user-card">
      <button
        class="user-menu-toggle"
        type="button"
        :aria-expanded="isUserMenuOpen"
        @click="isUserMenuOpen = !isUserMenuOpen"
      >
        <span class="user-avatar"><UserFilled aria-hidden="true" /></span>
        <span>
          <strong>{{ userName }}</strong>
          <p>{{ userRoleLabel }}</p>
        </span>
      </button>

      <div v-if="isUserMenuOpen" class="user-menu">
        <button type="button" @click="logout">
          <SwitchButton aria-hidden="true" />
          退出系统
        </button>
      </div>
    </div>
  </aside>
</template>
