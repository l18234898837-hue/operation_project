<script setup lang="ts">
import { storeToRefs } from "pinia";
import { useRouter } from "vue-router";

import HistorySidebar from "../components/app/HistorySidebar.vue";
import ChatWorkspace from "../components/chat/ChatWorkspace.vue";
import { useChatStore } from "../stores/chat";

const router = useRouter();
const chatStore = useChatStore();
const {
  activeConversationId,
  answerDescription,
  canSend,
  copyMessage,
  errorMessage,
  hasHistorySearchResults,
  historyGroups,
  historyQuery,
  historySearchResultCount,
  isHistorySearching,
  messages,
  pageTitle,
  question,
  status,
  streamStatusMessages
} = storeToRefs(chatStore);

function logout() {
  chatStore.logout();
  void router.push("/login");
}
</script>

<template>
  <div class="admin-chat-page">
    <HistorySidebar
      v-model:search-query="historyQuery"
      :active-conversation-id="activeConversationId"
      brand-to="/admin/chat"
      :has-search-results="hasHistorySearchResults"
      :history-groups="historyGroups"
      :is-searching="isHistorySearching"
      :search-result-count="historySearchResultCount"
      user-name="管理员"
      user-role-label="系统管理员"
      @clear-search="chatStore.clearHistorySearch"
      @delete="chatStore.deleteConversation"
      @logout="logout"
      @new="chatStore.newConversation"
      @select="chatStore.selectConversation"
    />

    <ChatWorkspace
      v-model:question="question"
      :answer-description="answerDescription"
      :can-send="canSend"
      :copy-message="copyMessage"
      :error-message="errorMessage"
      :messages="messages"
      :page-title="pageTitle"
      :status="status"
      :stream-status-messages="streamStatusMessages"
      @ask="chatStore.sendQuestion"
      @copy="chatStore.copyAnswer"
      @retry="chatStore.retryLastQuestion($event)"
      @send="chatStore.sendQuestion"
    />
  </div>
</template>
