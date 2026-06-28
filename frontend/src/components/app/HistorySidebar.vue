<script setup lang="ts">
import { ChatDotRound, MoreFilled, Plus, Search, SwitchButton, UserFilled } from "@element-plus/icons-vue";
import { onBeforeUnmount } from "vue";

import logoUrl from "../../assets/logo-transparent.png";
import type { ConversationHistoryItem } from "../../stores/chat";
import {
  createHistorySidebarMenuState,
  isPointerInsideSidebarMenuControls
} from "./historySidebarMenus";

const searchQuery = defineModel<string>("searchQuery", { default: "" });

withDefaults(
  defineProps<{
    activeConversationId: string | null;
    historyGroups: Array<{
      label: string;
      items: ConversationHistoryItem[];
    }>;
    hasSearchResults?: boolean;
    isSearching?: boolean;
    searchResultCount?: number;
    userName?: string;
    userRoleLabel?: string;
    brandTo?: string;
  }>(),
  {
    hasSearchResults: true,
    isSearching: false,
    searchResultCount: 0,
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
  clearSearch: [];
}>();

const {
  openConversationMenuId,
  isUserMenuOpen,
  toggleConversationMenu,
  closeConversationMenu,
  toggleUserMenu,
  closeUserMenu,
  closeAllMenus
} = createHistorySidebarMenuState();

function selectConversation(conversationId: string) {
  closeConversationMenu();
  emit("select", conversationId);
}

function deleteConversation(conversation: ConversationHistoryItem) {
  if (window.confirm(`确定删除会话“${conversation.title}”？`)) {
    emit("delete", conversation.id);
  }

  closeConversationMenu();
}

function createNewSession() {
  closeAllMenus();
  emit("new");
}

function clearSearch() {
  emit("clearSearch");
}

function handleDocumentPointerDown(event: PointerEvent) {
  const hasOpenMenu = isUserMenuOpen.value || openConversationMenuId.value !== null;

  if (!hasOpenMenu || event.button !== 0) {
    return;
  }

  if (isPointerInsideSidebarMenuControls(event.target)) {
    return;
  }

  closeAllMenus();
}

function handleDocumentKeydown(event: KeyboardEvent) {
  if (event.key === "Escape") {
    closeAllMenus();
  }
}

if (typeof document !== "undefined") {
  document.addEventListener("pointerdown", handleDocumentPointerDown, true);
  document.addEventListener("keydown", handleDocumentKeydown);
}

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", handleDocumentPointerDown, true);
  document.removeEventListener("keydown", handleDocumentKeydown);
});

function logout() {
  closeUserMenu();
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

    <p v-if="isSearching" class="history-search-summary">
      找到 {{ searchResultCount }} 个相关会话
      <button type="button" @click="clearSearch">清空</button>
    </p>

    <div class="history-groups">
      <p v-if="!hasSearchResults" class="history-empty">没有找到相关会话，可换个关键词试试</p>

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
              <em v-if="isSearching && item.matchedMessageSnippet">
                {{ item.matchType === "title_message" ? "标题和内容命中" : "内容命中" }}：{{ item.matchedMessageSnippet }}
              </em>
              <small v-else-if="isSearching && item.matchType === 'title'">标题命中</small>
              <time>{{ item.displayTime }}</time>
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

            <div
              v-if="openConversationMenuId === item.id"
              class="history-menu"
              role="menu"
            >
              <button type="button" role="menuitem" @click="deleteConversation(item)">删除会话</button>
            </div>
          </div>
        </section>
      </template>
    </div>

    <div class="chat-user-card" :class="{ open: isUserMenuOpen }">
      <button
        class="user-menu-toggle"
        type="button"
        :aria-expanded="isUserMenuOpen"
        @click="toggleUserMenu"
      >
        <span class="user-avatar"><UserFilled aria-hidden="true" /></span>
        <span>
          <strong>{{ userName }}</strong>
          <p>{{ userRoleLabel }}</p>
        </span>
      </button>

      <div v-if="isUserMenuOpen" class="user-menu" role="menu">
        <div class="user-menu-profile">
          <span class="user-menu-avatar"><UserFilled aria-hidden="true" /></span>
          <div>
            <strong>{{ userName }}</strong>
            <p>{{ userRoleLabel }}</p>
          </div>
        </div>

        <button class="user-menu-logout" type="button" role="menuitem" @click="logout">
          <SwitchButton aria-hidden="true" />
          退出系统
        </button>
      </div>
    </div>
  </aside>
</template>
