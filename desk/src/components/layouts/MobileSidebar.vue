<template>
  <TransitionRoot :show="sidebarOpened">
    <Dialog as="div" @close="sidebarOpened = false" class="fixed inset-0">
      <TransitionChild
        as="template"
        enter="transition ease-in-out duration-200 transform"
        enter-from="-translate-x-full"
        enter-to="translate-x-0"
        leave="transition ease-in-out duration-200 transform"
        leave-from="translate-x-0"
        leave-to="-translate-x-full"
      >
        <!-- Full-width layer over the overlay; @click.self closes when the
             empty area beside the drawer is tapped (the drawer itself and the
             close button are children, so they don't trigger it). -->
        <div class="relative z-10 h-full" @click.self="sidebarOpened = false">
          <AppSidebar mobile :profile-settings="profileSettings" />
          <!-- Explicit close (the collapse toggle is hidden on mobile, and the
               drawer can cover the overlay — without this you can get stuck).
               Pushed below the status-bar inset so it clears the notch. -->
          <button
            type="button"
            class="absolute right-2 z-20 grid size-9 place-items-center rounded-lg text-ink-gray-7 active:bg-surface-gray-3"
            style="top: calc(0.5rem + env(safe-area-inset-top))"
            aria-label="Close menu"
            @click="sidebarOpened = false"
          >
            <LucideX class="size-5" />
          </button>
        </div>
      </TransitionChild>
      <TransitionChild
        as="template"
        enter="transition-opacity ease-linear duration-200"
        enter-from="opacity-0"
        enter-to="opacity-100"
        leave="transition-opacity ease-linear duration-200"
        leave-from="opacity-100"
        leave-to="opacity-0"
      >
        <DialogOverlay class="fixed inset-0 bg-black-overlay-500" />
      </TransitionChild>
    </Dialog>
  </TransitionRoot>
</template>

<script setup lang="ts">
import {
  Dialog,
  DialogOverlay,
  TransitionChild,
  TransitionRoot,
} from "@headlessui/vue";
import { computed, markRaw, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  pushState,
  refreshPushState,
  togglePush,
} from "@/composables/webPush";

import { useAuthStore } from "@/stores/auth";
import { isCustomerPortal } from "@/utils";
import { useTheme } from "frappe-ui";
import LucideMoon from "~icons/lucide/moon";
import LucideSun from "~icons/lucide/sun";
import LucideX from "~icons/lucide/x";

import { mobileSidebarOpened as sidebarOpened } from "@/composables/mobile";
import { useApps } from "@/composables/useApps";
import { __ } from "@/translation";
import AppSidebar from "./AppSidebar.vue";
import AvailabilityMenuMobile from "../AvailabilityMenuMobile.vue";

const { currentTheme, toggleTheme } = useTheme();
const { appsMenuOption } = useApps();
const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

// Names the state rather than the action for "denied", because there is nothing
// tapping can do about it — the browser won't re-prompt once refused.
const pushLabel = computed(() => {
  switch (pushState.value) {
    case "on":
      return __("Notifications on");
    case "working":
      return __("Just a moment…");
    case "denied":
      return __("Notifications blocked");
    default:
      return __("Notify me on this device");
  }
});

// Read-only: reflects whether this device already has a subscription. Never
// prompts.
onMounted(refreshPushState);

const themeMenuItem = computed(() => ({
  label: __("Toggle theme"),
  icon: currentTheme.value === "dark" ? LucideSun : LucideMoon,
  onClick: () => toggleTheme(),
}));

const customerPortalDropdown = computed(() => [
  themeMenuItem.value,
  {
    label: __("Log out"),
    icon: "lucide-log-out",
    onClick: () => authStore.logout(),
  },
]);

const agentPortalDropdown = computed(() => [
  // PYEK: Notifications lives here now that the bottom bar dropped its standalone
  // Alerts tab (see MobileBottomNav). The unread count still shows on the Menu tab.
  {
    label: __("Notifications"),
    icon: "lucide-bell",
    onClick: () => router.push({ name: "Notifications" }),
  },
  // PYEK: push opt-in. Lives behind an explicit tap because a permission prompt
  // on load is the fastest route to a permanent denial — and on iOS a denial can
  // only be reversed in system Settings, so one bad prompt kills the feature for
  // that install. Hidden where the browser can't do push at all.
  ...(pushState.value !== "unsupported"
    ? [
        {
          label: pushLabel.value,
          icon: pushState.value === "on" ? "lucide-bell-ring" : "lucide-bell-plus",
          onClick: () => togglePush(),
        },
      ]
    : []),
  // Per-source switches (assignments / mentions / team tickets / replies),
  // stored on the agent so they follow you across devices.
  {
    label: __("Notification settings"),
    icon: "lucide-sliders-horizontal",
    onClick: () => router.push({ name: "NotificationSettings" }),
  },
  appsMenuOption.value,
  ...(authStore.hasAgentRecord
    ? [
        {
          component: markRaw(AvailabilityMenuMobile),
        },
      ]
    : []),
  {
    label: __("Customer portal"),
    icon: "lucide-users",
    onClick: () => {
      const path = router.resolve({ name: "TicketsCustomer" });
      window.open(path.href);
    },
  },
  {
    icon: "lucide-life-buoy",
    label: __("Support"),
    onClick: () => window.open("https://t.me/frappedesk"),
  },
  {
    icon: "lucide-book-open",
    label: __("Docs"),
    onClick: () => window.open("https://docs.frappe.io/helpdesk"),
  },
  themeMenuItem.value,
  {
    label: __("Log out"),
    icon: "lucide-log-out",
    onClick: () => authStore.logout(),
  },
]);

const profileSettings = computed(() => {
  return isCustomerPortal.value
    ? customerPortalDropdown.value
    : agentPortalDropdown.value;
});

watch(
  () => route.fullPath,
  () => (sidebarOpened.value = false)
);
</script>
