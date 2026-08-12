<template>
  <!-- PYEK: persistent bottom tab bar for phones. Rendered only inside
       MobileLayout, so desktop is untouched. Big touch targets. Home opens the
       branded dashboard; POS / IT / Wrike / Mine jump straight to those saved
       ticket queues; Menu opens the nav drawer (all views, notifications,
       profile, logout). Order: Home · POS · IT · Wrike · Mine · Menu.

       "Mine" was added because the agent's OWN queue — the one queue that is
       personally theirs — was the only one not on the bar, so it took two taps
       through the drawer while three shared queues sat one tap away.

       Six tabs is what forced "Dashboard" down to "Home": at 375px six labels
       only fit if they're all short, and "Home" is the honest name for it
       anyway (the bare /dashboard analytics page is a different, desktop view).
       If six ever feels too many, swap Wrike out rather than Mine. -->
  <!-- Navy bar to match the sidebar brand; white/muted icons, bright-blue
       active. paddingBottom carries the iOS home-indicator safe-area inset so
       the labels never sit under the home bar. -->
  <nav
    class="flex shrink-0 items-stretch"
    :style="{
      backgroundColor: '#1B2A4A',
      borderTop: '1px solid rgba(255,255,255,0.08)',
      paddingBottom: 'env(safe-area-inset-bottom)',
    }"
  >
    <button
      v-for="item in items"
      :key="item.key"
      class="flex min-h-14 flex-1 flex-col items-center justify-center gap-1 py-2 transition active:bg-white/5"
      :style="{ color: isActive(item) ? '#60A5FA' : 'rgba(255,255,255,0.64)' }"
      @click="go(item)"
    >
      <span class="relative grid size-6 place-items-center">
        <component :is="item.icon" class="size-6" />
        <span
          v-if="item.badge"
          class="absolute -right-1.5 -top-1.5 min-w-4 rounded-full px-1 text-center text-[10px] font-semibold leading-4 text-white"
          style="background-color: #2563eb"
        >
          {{ item.badge > 9 ? "9+" : item.badge }}
        </span>
      </span>
      <span class="text-xs font-medium leading-none">{{ item.label }}</span>
    </button>
  </nav>
</template>

<script setup lang="ts">
import { useView } from "@/composables/useView";
import { useNotificationStore } from "@/stores/notification";
import { mobileSidebarOpened as sidebarOpened } from "@/composables/mobile";
import { __ } from "@/translation";
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import LucideLayoutDashboard from "~icons/lucide/layout-dashboard";
import LucideHeadset from "~icons/lucide/headset";
import LucideScanBarcode from "~icons/lucide/scan-barcode";
import LucideMenu from "~icons/lucide/menu";
import LucideMegaphone from "~icons/lucide/megaphone";
import LucideUser from "~icons/lucide/user";

const route = useRoute();
const router = useRouter();
const notificationStore = useNotificationStore();
const { publicViews } = useView();

// Resolve a saved HD View id from its label (POS Tickets / IT Tickets / Open
// Wrike Tickets), so those tabs open the exact queues. Falls back to the plain
// ticket list.
function viewId(label: string): string | undefined {
  return (publicViews.value || []).find((v: any) => v.label === label)?.name;
}

type Item = {
  key: string;
  label: string;
  icon: any;
  route?: string;
  view?: string;
  badge?: number;
  action?: () => void;
};

const items = computed<Item[]>(() => [
  {
    // The branded IT dashboard is PyekHome (route "Home") — greeting, metric
    // cards, charts, saved-view launchers. (The bare "/dashboard" analytics page
    // is a separate, desktop-oriented view.)
    key: "dashboard",
    label: __("Home"),
    icon: LucideLayoutDashboard,
    route: "Home",
  },
  { key: "pos", label: __("POS"), icon: LucideScanBarcode, view: "POS Tickets" },
  { key: "it", label: __("IT"), icon: LucideHeadset, view: "IT Tickets" },
  // Open marketing/Wrike tickets awaiting POS action.
  {
    key: "wrike",
    label: __("Wrike"),
    icon: LucideMegaphone,
    view: "Open Wrike Tickets",
  },
  // The agent's own queue. Same saved view the dashboard's "My open tickets" row
  // opens, so the count they tap on the dashboard and this tab are the same list.
  {
    key: "mine",
    label: __("Mine"),
    icon: LucideUser,
    view: "My Open Tickets",
  },
  // Opens the nav drawer (all saved views, notifications, availability, log
  // out). The unread badge lives here now that the standalone Alerts tab is
  // gone — Notifications is reachable inside the drawer.
  {
    key: "menu",
    label: __("Menu"),
    icon: LucideMenu,
    action: () => (sidebarOpened.value = true),
    badge: notificationStore.unread,
  },
]);

function isActive(item: Item): boolean {
  if (item.action) return false;
  if (item.view) {
    return (
      route.name === "TicketsAgent" && route.query.view === viewId(item.view)
    );
  }
  return route.name === item.route;
}

function go(item: Item) {
  if (item.action) {
    item.action();
  } else if (item.view) {
    const vn = viewId(item.view);
    router.push({ name: "TicketsAgent", query: vn ? { view: vn } : {} });
  } else if (route.name !== item.route) {
    router.push({ name: item.route as string });
  }
}
</script>
