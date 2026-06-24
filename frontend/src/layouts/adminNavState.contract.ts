import { ADMIN_NAV_COLLAPSED_KEY, readAdminNavCollapsed, writeAdminNavCollapsed } from "./adminNavState";

const key: "pv-admin-nav-collapsed" = ADMIN_NAV_COLLAPSED_KEY;
const collapsed: boolean = readAdminNavCollapsed();

writeAdminNavCollapsed(true);
writeAdminNavCollapsed(false);

void key;
void collapsed;
