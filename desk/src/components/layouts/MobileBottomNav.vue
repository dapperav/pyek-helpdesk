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
  <!-- Frosted glass overlay (Apple material: blur + saturate). Positioned by
       MobileLayout as an absolute layer over the scroller, so page content
       scrolls beneath it and the tide menu rises BEHIND it (sheet z-40, this
       z-50). paddingBottom carries the iOS home-indicator safe-area inset.
       The active accent is brand cyan; Mine is the user's own avatar. -->
  <!-- Slimmed 2026-08-15 (Mark: "a true nav bar instead of that massive
       chunk"): bigger icons, tighter row, and the content sits LOWER — we
       reclaim 10px of the home-indicator inset (the pill still clears) so
       the bar + iOS's letterbox below read as one compact nav. max() keeps
       the padding at 0 where env() is 0 (desktop, dev). -->
  <nav
    class="glassnav absolute inset-x-0 bottom-0 z-50 flex items-stretch"
    :style="{
      paddingBottom: 'max(env(safe-area-inset-bottom) - 10px, 0px)',
    }"
  >
    <button
      v-for="item in items"
      :key="item.key"
      class="flex min-h-12 flex-1 flex-col items-center justify-center gap-0.5 pb-1 pt-1.5 transition active:bg-white/5"
      :style="{ color: isActive(item) ? '#67E8F9' : 'rgba(255,255,255,0.66)' }"
      @click="go(item)"
    >
      <span class="relative grid size-7 place-items-center">
        <!-- Mine = you: photo when the account has one, initials otherwise. -->
        <template v-if="item.key === 'mine'">
          <img
            v-if="meImage"
            :src="meImage"
            class="me-avatar object-cover"
            :class="isActive(item) && 'me-avatar-active'"
            alt=""
          />
          <span
            v-else
            class="me-avatar grid place-items-center text-[9.5px] font-extrabold"
            :class="isActive(item) && 'me-avatar-active'"
            style="background-color: #67e8f9; color: #10202e"
          >
            {{ meInitials }}
          </span>
        </template>
        <component :is="item.icon" v-else class="size-7" />
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
import { useAuthStore } from "@/stores/auth";
import { useUserStore } from "@/stores/user";
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

const { userId } = useAuthStore();
const { getUser } = useUserStore();
const meImage = computed(() => getUser(userId)?.user_image || "");
const meInitials = computed(() =>
  (getUser(userId)?.full_name || userId || "?")
    .split(/[\s.@_-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p: string) => p[0]?.toUpperCase())
    .join("")
);

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
  // The agent's own queue. Same saved view Home's "Mine" pool opens, so the
  // count they tap on Home and this tab are the same list. The icon slot is
  // the user's avatar (special-cased in the template); LucideUser is only the
  // typed fallback and never renders for this key.
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
    // Toggle, not open: tapping Menu while the tide is up sends it back out
    // (Mark's spec — "when you hit it while menu is open it comes down").
    action: () => (sidebarOpened.value = !sidebarOpened.value),
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

<style scoped>
.glassnav {
  background: rgba(27, 42, 74, 0.72);
  -webkit-backdrop-filter: blur(18px) saturate(1.5);
  backdrop-filter: blur(18px) saturate(1.5);
  border-top: 1px solid rgba(255, 255, 255, 0.12);
}
.me-avatar {
  width: 25px;
  height: 25px;
  border-radius: 9999px;
  border: 1.5px solid rgba(255, 255, 255, 0.7);
}
.me-avatar-active {
  border-color: #67e8f9;
}
</style>
