import LucideBookOpen from "~icons/lucide/book-open";
import LucideTicket from "~icons/lucide/ticket";
import PhoneIcon from "../icons/PhoneIcon.vue";
import LucideHome from "~icons/lucide/home";
import { __ } from "@/translation";

// PYEK: trimmed the agent nav to what the POS/IT desk actually uses (matches the
// approved portal mockup). Customers and Contacts are dropped; Call Logs stays
// but is auto-hidden unless telephony is enabled (see AppSidebar). Knowledge
// Base returned 2026-08-14 — 26 agent-facing SOPs existed with no way to find
// them, and its badge carries the needs-SME-confirmation count.
export const agentPortalSidebarOptions = [
  {
    label: __("Home"),
    icon: LucideHome,
    to: "Home",
  },
  // Dashboard folded into Home (Mark, 2026-08-18): the ocean Home carries the
  // analytics now, so the separate entry retired. The route still answers by
  // URL for anyone with a bookmark.
  {
    label: __("Tickets"),
    icon: LucideTicket,
    to: "TicketsAgent",
  },
  {
    label: __("Knowledge Base"),
    icon: LucideBookOpen,
    to: "AgentKnowledgeBase",
  },
  {
    label: __("Call Logs"),
    icon: PhoneIcon,
    to: "CallLogs",
  },
];

export const customerPortalSidebarOptions = [
  {
    label: __("Tickets"),
    icon: LucideTicket,
    to: "TicketsCustomer",
  },
  {
    label: __("Knowledge Base"),
    icon: LucideBookOpen,
    to: "CustomerKnowledgeBase",
  },
];
