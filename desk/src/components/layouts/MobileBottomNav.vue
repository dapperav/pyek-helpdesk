<template>
  <!-- PYEK / AP: persistent bottom tab bar for phones. Rendered only inside
       MobileLayout, so desktop is untouched. Big touch targets. Home = the AP
       dashboard; Inbox = the "All open" queue; Mine = "My queue"; Menu opens
       the drawer (all saved views, profile, settings, logout, search).
       Notifications live in the header bell now that Alerts isn't a tab. -->

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
import { mobileSidebarOpened as sidebarOpened } from "@/composables/mobile";
import { __ } from "@/translation";
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import LucideHome from "~icons/lucide/home";
import LucideInbox from "~icons/lucide/inbox";
import LucideUser from "~icons/lucide/user";
import LucideMenu from "~icons/lucide/menu";

const route = useRoute();
const router = useRouter();
const { publicViews } = useView();

// Resolve a saved HD View id from its label (e.g. "All Open", "My queue"), so a
// tab opens that exact AP queue. Falls back to the plain ticket list if a view
// with that label doesn't exist yet.
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
  { key: "home", label: __("Home"), icon: LucideHome, route: "Home" },
  { key: "inbox", label: __("Inbox"), icon: LucideInbox, view: "All Open" },
  { key: "mine", label: __("Mine"), icon: LucideUser, view: "My queue" },
  // Opens the nav drawer (Dashboard, all saved views, availability, log out) —
  // relocated here from the old top-left hamburger.
  {
    key: "menu",
    label: __("Menu"),
    icon: LucideMenu,
    action: () => (sidebarOpened.value = true),
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
