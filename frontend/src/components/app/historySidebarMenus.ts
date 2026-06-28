import { ref, type Ref } from "vue";

export interface HistorySidebarMenuState {
  openConversationMenuId: Ref<string | null>;
  isUserMenuOpen: Ref<boolean>;
  toggleConversationMenu: (conversationId: string) => void;
  closeConversationMenu: () => void;
  toggleUserMenu: () => void;
  closeUserMenu: () => void;
  closeAllMenus: () => void;
}

export function createHistorySidebarMenuState(): HistorySidebarMenuState {
  const openConversationMenuId = ref<string | null>(null);
  const isUserMenuOpen = ref(false);

  function closeConversationMenu() {
    openConversationMenuId.value = null;
  }

  function closeUserMenu() {
    isUserMenuOpen.value = false;
  }

  function closeAllMenus() {
    closeConversationMenu();
    closeUserMenu();
  }

  function toggleConversationMenu(conversationId: string) {
    isUserMenuOpen.value = false;
    openConversationMenuId.value = openConversationMenuId.value === conversationId ? null : conversationId;
  }

  function toggleUserMenu() {
    closeConversationMenu();
    isUserMenuOpen.value = !isUserMenuOpen.value;
  }

  return {
    openConversationMenuId,
    isUserMenuOpen,
    toggleConversationMenu,
    closeConversationMenu,
    toggleUserMenu,
    closeUserMenu,
    closeAllMenus
  };
}

export function isPointerInsideSidebarMenuControls(target: EventTarget | null) {
  if (!(target instanceof Element)) {
    return false;
  }

  return target.closest(".history-menu, .history-menu-button, .chat-user-card") !== null;
}
