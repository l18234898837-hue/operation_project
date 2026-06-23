<script setup lang="ts">
import { ref, watch } from "vue";

import AdminNav from "../components/app/AdminNav.vue";
import { readAdminNavCollapsed, writeAdminNavCollapsed } from "./adminNavState";

const isCollapsed = ref(readAdminNavCollapsed());

watch(isCollapsed, (collapsed) => {
  writeAdminNavCollapsed(collapsed);
});
</script>

<template>
  <div class="admin-shell" :class="{ collapsed: isCollapsed }">
    <AdminNav v-model:collapsed="isCollapsed" />
    <main class="admin-shell-main">
      <RouterView />
    </main>
  </div>
</template>
