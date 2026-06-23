import { adminNavItems } from "../components/app/adminNavItems";
import router from "./index";

const hasStandaloneUnansweredNav = adminNavItems.some((item) => String(item.to) === "/admin/unanswered");
const legacyUnansweredRoute = router.resolve("/admin/unanswered");

if (hasStandaloneUnansweredNav) {
  throw new Error("Unanswered questions must stay inside QA logs, not as a standalone admin nav entry.");
}

if (legacyUnansweredRoute.redirectedFrom?.fullPath !== "/admin/unanswered" && legacyUnansweredRoute.path !== "/admin/logs") {
  throw new Error("Legacy /admin/unanswered route must redirect to /admin/logs.");
}
