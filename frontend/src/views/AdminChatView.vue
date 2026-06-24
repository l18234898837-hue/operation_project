<script setup lang="ts">
import { storeToRefs } from "pinia";

import HistorySidebar from "../components/app/HistorySidebar.vue";
import ChatWorkspace from "../components/chat/ChatWorkspace.vue";
import { useChatStore } from "../stores/chat";

const chatStore = useChatStore();
const {
  activeConversationId,
  answerDescription,
  canSend,
  copyMessage,
  errorMessage,
  historyGroups,
  latestResponse,
  messages,
  pageTitle,
  question,
  status
} = storeToRefs(chatStore);
</script>

<template>
  <div class="admin-chat-page">
    <HistorySidebar
      :active-conversation-id="activeConversationId"
      brand-to="/admin/chat"
      :history-groups="historyGroups"
      user-name="管理员"
      user-role-label="系统管理员"
      @select="chatStore.selectConversation"
    />

    <ChatWorkspace
      v-model:question="question"
      :answer-description="answerDescription"
      :can-send="canSend"
      :copy-message="copyMessage"
      :error-message="errorMessage"
      :latest-response="latestResponse"
      :messages="messages"
      :page-title="pageTitle"
      :status="status"
      @ask="chatStore.sendQuestion"
      @copy="chatStore.copyAnswer"
      @retry="chatStore.retryLastQuestion"
      @send="chatStore.sendQuestion"
    />
  </div>
</template>
