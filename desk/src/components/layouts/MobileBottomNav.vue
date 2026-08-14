<template>
  <!-- PYEK: persistent bottom tab bar for phones. Rendered only inside
       MobileLayout, so desktop is untouched. Big touch targets. Home opens the
       branded dashboard; POS / IT / Wrike / Mine jump straight to those saved
       ticket queues; Menu opens the nav drawer (all views, notifications,
       profile, logout). Order: Home · POS · IT · Wrike · Mine · Menu.

       "Mine" was added because the agent's OWN queue — the one queue that is
       personally theirs — was the only one not on the bar, so it took two taps
       through the drawer while three shared queues sat one tap away.

       Slimmed to THREE tabs 2026-08-14 (Mark's pick): Home is the ROUTER —
       the queue boxes (POS / IT / Wrike) live on it as navy cards, so they
       left the bar; Mine stays because the agent's own queue is the one they
       hit most; Menu opens the branded bottom sheet (all queues,
       notifications, settings). -->
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
import LucideHouse from "~icons/lucide/house";
import LucideMenu from "~icons/lucide/menu";
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
    icon: LucideHouse,
    route: "Home",
  },
  // The agent's own queue. Same saved view Home's "My tickets" card opens, so
  // the count they tap on Home and this tab are the same list.
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
