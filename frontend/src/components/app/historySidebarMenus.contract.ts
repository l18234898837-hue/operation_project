import {
  createHistorySidebarMenuState,
  isPointerInsideSidebarMenuControls,
  type HistorySidebarMenuState
} from "./historySidebarMenus";

type Assert<T extends true> = T;
type IsAssignable<TValue, TExpected> = TValue extends TExpected ? true : false;

const menuState = createHistorySidebarMenuState();

type MenuStateHasConversationId = Assert<
  IsAssignable<typeof menuState.openConversationMenuId.value, string | null>
>;
type MenuStateHasUserMenuFlag = Assert<IsAssignable<typeof menuState.isUserMenuOpen.value, boolean>>;
type MenuStateShapeIsExported = Assert<IsAssignable<typeof menuState, HistorySidebarMenuState>>;
type SidebarMenuControlsCheckReturnsBoolean = Assert<
  IsAssignable<ReturnType<typeof isPointerInsideSidebarMenuControls>, boolean>
>;

menuState.toggleConversationMenu("conversation-1");
menuState.closeConversationMenu();
menuState.toggleUserMenu();
menuState.closeAllMenus();
isPointerInsideSidebarMenuControls(null);

void (null as unknown as MenuStateHasConversationId);
void (null as unknown as MenuStateHasUserMenuFlag);
void (null as unknown as MenuStateShapeIsExported);
void (null as unknown as SidebarMenuControlsCheckReturnsBoolean);
