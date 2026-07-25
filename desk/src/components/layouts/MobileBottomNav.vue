<template>
  <!-- PYEK: persistent bottom tab bar for phones. Rendered only inside
       MobileLayout, so desktop is untouched. Big touch targets; POS / IT jump
       straight to those saved ticket queues. The hamburger drawer stays for
       everything else (all tickets, views, profile, settings, logout, search). -->
  <nav
    class="flex shrink-0 items-stretch border-t border-outline-gray-2 bg-surface-white"
    :style="{ paddingBottom: 'env(safe-area-inset-bottom)' }"
  >
    <button
      v-for="item in items"
      :key="item.key"
      class="flex min-h-14 flex-1 flex-col items-center justify-center gap-1 py-2 active:bg-surface-gray-2"
      :class="isActive(item) ? 'text-ink-blue-5' : 'text-ink-gray-6'"
      @click="go(item)"
    >
      <span class="relative grid size-6 place-items-center">
        <component :is="item.icon" class="size-6" />
        <span
          v-if="item.badge"
          class="absolute -right-1.5 -top-1.5 min-w-4 rounded-full bg-surface-blue-5 px-1 text-center text-[10px] font-semibold leading-4 text-white"
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
import { __ } from "@/translation";
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import LucideBell from "~icons/lucide/bell";
import LucideHome from "~icons/lucide/home";
import LucideMonitor from "~icons/lucide/monitor";
import LucideStore from "~icons/lucide/store";

const route = useRoute();
const router = useRouter();
const notificationStore = useNotificationStore();
const { publicViews } = useView();

// Resolve a saved HD View id from its label (POS Tickets / IT Tickets), so the
// POS/IT tabs open those exact queues. Falls back to the plain ticket list.
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
};

const items = computed<Item[]>(() => [
  { key: "home", label: __("Home"), icon: LucideHome, route: "Home" },
  { key: "pos", label: __("POS"), icon: LucideStore, view: "POS Tickets" },
  { key: "it", label: __("IT"), icon: LucideMonitor, view: "IT Tickets" },
  {
    key: "alerts",
    label: __("Alerts"),
    icon: LucideBell,
    route: "Notifications",
    badge: notificationStore.unread,
  },
]);

function isActive(item: Item): boolean {
  if (item.view) {
    return (
      route.name === "TicketsAgent" && route.query.view === viewId(item.view)
    );
  }
  return route.name === item.route;
}

function go(item: Item) {
  if (item.view) {
    const vn = viewId(item.view);
    router.push({ name: "TicketsAgent", query: vn ? { view: vn } : {} });
  } else if (route.name !== item.route) {
    router.push({ name: item.route as string });
  }
}
</script>
