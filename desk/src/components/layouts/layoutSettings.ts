import LucideBookOpen from "~icons/lucide/book-open";
import LucideTicket from "~icons/lucide/ticket";
import PhoneIcon from "../icons/PhoneIcon.vue";
import LucideHome from "~icons/lucide/home";
import LucideStore from "~icons/lucide/store";
import LucideMonitor from "~icons/lucide/monitor";
import LucideCircleUser from "~icons/lucide/circle-user";
import LucideTrendingUp from "~icons/lucide/trending-up";
import { __ } from "@/translation";

// PYEK: trimmed the agent nav to what the POS/IT desk actually uses (matches the
// approved portal mockup). Customers and Contacts are dropped; Call Logs stays
// but is auto-hidden unless telephony is enabled (see AppSidebar). Knowledge
// Base returned 2026-08-14 — 26 agent-facing SOPs existed with no way to find
// them, and its badge carries the needs-SME-confirmation count.
export const agentPortalSidebarOptions = [
  // `group` places the item on the captioned rail and in the 15rem panel
  // (Mark, 2026-08-20): find = tools, queues = the three hero views, go =
  // places. `caption` is the rail's word under the icon — it must survive a
  // 4.5rem column, so it is sometimes shorter than the full label.
  {
    label: __("Home"),
    caption: __("Home"),
    group: "go",
    icon: LucideHome,
    to: "Home",
  },
  // Dashboard folded into Home (Mark, 2026-08-18): the ocean Home carries the
  // analytics now, so the separate entry retired. The route still answers by
  // URL for anyone with a bookmark.
  //
  // Queue jumps (Mark, 2026-08-18 evening: "the sidebar just isn't useful"):
  // the three hero views + Analytics, one click from any screen. `view` is a
  // saved-view LABEL resolved via publicViews at click time (names are
  // per-site); `countKey` wires the live-count pill from the queueCounts
  // store. Analytics is a jump to Home's chart section, not a place — it
  // never renders active.
  {
    label: __("POS"),
    caption: __("POS"),
    group: "queues",
    icon: LucideStore,
    view: "POS Tickets",
    countKey: "pos",
  },
  {
    label: __("IT"),
    caption: __("IT"),
    group: "queues",
    icon: LucideMonitor,
    view: "IT Tickets",
    countKey: "it",
  },
  {
    label: __("Mine"),
    caption: __("Mine"),
    group: "queues",
    icon: LucideCircleUser,
    view: "My Open Tickets",
    countKey: "mine",
  },
  {
    label: __("Tickets"),
    caption: __("Tickets"),
    group: "go",
    icon: LucideTicket,
    to: "TicketsAgent",
  },
  {
    label: __("Knowledge Base"),
    caption: __("Knowledge"),
    group: "go",
    icon: LucideBookOpen,
    to: "AgentKnowledgeBase",
  },
  {
    label: __("Analytics"),
    caption: __("Analytics"),
    group: "go",
    icon: LucideTrendingUp,
    to: "Home",
    hash: "#analytics",
  },
  {
    label: __("Call Logs"),
    caption: __("Calls"),
    group: "go",
    icon: PhoneIcon,
    to: "CallLogs",
  },
];

export const customerPortalSidebarOptions = [
  {
    label: __("Tickets"),
    caption: __("Tickets"),
    icon: LucideTicket,
    to: "TicketsCustomer",
  },
  {
    label: __("Knowledge Base"),
    caption: __("Knowledge"),
    icon: LucideBookOpen,
    to: "CustomerKnowledgeBase",
  },
];
