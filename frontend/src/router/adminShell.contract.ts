import AdminNav from "../components/app/AdminNav.vue";
import AdminShell from "../layouts/AdminShell.vue";
import AdminChatView from "../views/AdminChatView.vue";
import router from "./index";

const adminChatRoute = router.resolve("/admin/chat");
const adminDocumentsRoute = router.resolve("/admin/documents");
const adminLogsRoute = router.resolve("/admin/logs");

if (adminChatRoute.name !== "admin-chat") {
  throw new Error("/admin/chat route must resolve to admin-chat");
}

if (adminDocumentsRoute.name !== "admin-documents") {
  throw new Error("/admin/documents must stay available in AdminShell");
}

if (adminLogsRoute.name !== "admin-logs") {
  throw new Error("/admin/logs must stay available in AdminShell");
}

void AdminNav;
void AdminShell;
void AdminChatView;
