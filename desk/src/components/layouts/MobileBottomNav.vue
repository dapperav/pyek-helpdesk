<template>
  <!-- PYEK: persistent bottom tab bar for phones. Rendered only inside
       MobileLayout, so desktop is untouched. The hamburger drawer stays for
       everything else (saved views, profile, settings, logout, search). -->
  <nav
    class="flex shrink-0 items-stretch border-t border-outline-gray-2 bg-surface-white"
    :style="{ paddingBottom: 'env(safe-area-inset-bottom)' }"
  >
    <button
      v-for="item in items"
      :key="item.to"
      class="flex flex-1 flex-col items-center justify-center gap-0.5 py-1.5"
      :class="isActive(item.to) ? 'text-ink-blue-5' : 'text-ink-gray-5'"
      @click="go(item.to)"
    >
      <span class="relative grid size-5 place-items-center">
        <component :is="item.icon" class="size-5" />
        <span
          v-if="item.badge"
          class="absolute -right-1 -top-1 min-w-3 rounded-full bg-surface-blue-5 px-1 text-center text-[9px] font-medium leading-3 text-white"
        >
          {{ item.badge > 9 ? "9+" : item.badge }}
        </span>
      </span>
      <span class="text-[10px] font-medium leading-none">{{
        __(item.label)
      }}</span>
    </button>
  </nav>
</template>

<script setup lang="ts">
import { useNotificationStore } from "@/stores/notification";
import { useTelephonyStore } from "@/stores/telephony";
import { __ } from "@/translation";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import LucideBell from "~icons/lucide/bell";
import { agentPortalSidebarOptions } from "./layoutSettings";

const route = useRoute();
const router = useRouter();
const { isCallingEnabled } = storeToRefs(useTelephonyStore());
const notificationStore = useNotificationStore();

// Primary destinations from the shared nav config (kept in sync with the
// sidebar) plus Notifications, which on mobile is its own page.
const items = computed(() => {
  const nav = agentPortalSidebarOptions
    .filter((i) => isCallingEnabled.value || i.label !== __("Call Logs"))
    .map((i) => ({ label: i.label, icon: i.icon, to: i.to, badge: 0 }));
  return [
    ...nav,
    {
      label: __("Alerts"),
      icon: LucideBell,
      to: "Notifications",
      badge: notificationStore.unread,
    },
  ];
});

function isActive(name: string) {
  return route.name === name;
}
function go(name: string) {
  if (route.name !== name) router.push({ name });
}
</script>
