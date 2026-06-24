export const ADMIN_NAV_COLLAPSED_KEY = "pv-admin-nav-collapsed";

export function readAdminNavCollapsed(): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  return window.localStorage.getItem(ADMIN_NAV_COLLAPSED_KEY) === "true";
}

export function writeAdminNavCollapsed(collapsed: boolean) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(ADMIN_NAV_COLLAPSED_KEY, String(collapsed));
}
