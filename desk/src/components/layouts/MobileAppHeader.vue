<template>
  <!-- Navy brand bar — bookends the navy footer. It extends up behind the
       status bar (padding-top = the notch/status inset, needed since the
       viewport is viewport-fit=cover); status text is white via
       apple-mobile-web-app-status-bar-style=black-translucent.
       Left = the view switcher (teleported in by the tickets list on mobile,
       so we drop the separate white "List" row + the old menu hamburger — the
       nav drawer now opens from the "Menu" tab in the bottom bar). -->
  <div
    class="flex items-center gap-2 px-3"
    style="
      background-color: #1b2a4a;
      height: calc(3rem + env(safe-area-inset-top));
      padding-top: env(safe-area-inset-top);
    "
  >
    <!-- View-switcher teleport target (light-on-navy). Empty on non-list
         pages, which just show the brand. -->
    <div id="mobile-header-view" class="flex min-w-0 shrink items-center"></div>
    <PyekMark class="h-5 w-auto shrink-0" />
    <span class="text-base tracking-tight">
      <span class="font-bold text-white">PYEK</span
      ><span class="font-medium" style="color: #67e8f9">MAIL</span>
    </span>
    <!-- Right cluster: the notification bell (unread badge) + Create. The bell
         lives here because AP mobile has no Alerts tab in the bottom bar, so
         this keeps unread notifications one tap away and visible. -->
    <div class="ms-auto flex items-center gap-1.5">
      <RouterLink
        :to="{ name: 'Notifications' }"
        class="relative inline-grid size-9 place-items-center rounded-lg text-white active:opacity-70"
        :aria-label="__('Notifications')"
      >
        <FeatherIcon name="bell" class="size-5" />
        <span
          v-if="unreadCount"
          class="absolute right-1 top-1 min-w-4 rounded-full px-1 text-center text-[10px] font-semibold leading-4 text-white"
          style="background-color: #2563eb"
        >
          {{ unreadCount > 9 ? "9+" : unreadCount }}
        </span>
      </RouterLink>
      <!-- Create is route-aware (only on the tickets list). White-on-navy. -->
      <RouterLink
        v-if="showCreate"
        :to="{ name: 'TicketAgentNew' }"
        class="inline-flex items-center gap-1.5 rounded-lg bg-white px-3 py-1.5 text-sm font-medium active:opacity-80"
        style="color: #1b2a4a"
      >
        <FeatherIcon name="plus" class="size-4" />
        {{ __("Create") }}
      </RouterLink>
    </div>
  </div>
  <!-- White controls row: other pages teleport their title / breadcrumb into
       #app-header here (on white as designed). Hidden on the tickets list,
       where the view switcher now lives in the navy bar above — reclaiming a
       full row of screen space.
       IMPORTANT: use v-show, NOT v-if. #app-header is a Teleport target for
       LayoutHeader (e.g. the mobile ticket detail teleports its breadcrumb +
       status dropdown here). With v-if the target is created/destroyed across
       the list -> detail route change, and LayoutHeader teleporting into a
       target that's churning mid-transition crashes Vue's patcher
       ("Cannot read properties of null (reading 'emitsOptions')") — which left
       the mobile ticket detail blank (list stayed, nav bar vanished). v-show
       keeps the target permanently in the DOM (display:none reclaims the row's
       space on the list just like v-if did), so the teleport is always stable. -->
  <div
    v-show="route.name !== 'TicketsAgent'"
    class="flex h-12 items-center border-b border-outline-gray-2 pl-1 pr-2"
  >
    <header id="app-header" class="w-full min-w-0"></header>
  </div>
  <CallUI class="mr-3 mt-2" :userEmail="user" />
</template>

<script setup>
import PyekMark from "@/components/PyekMark.vue";
import { __ } from "@/translation";
import CallUI from "../telephony/CallUI.vue";
import { useAuthStore } from "@/stores/auth";
import { useNotificationStore } from "@/stores/notification";
import { useTelephonyStore } from "@/stores/telephony";
import { computed, onMounted } from "vue";
import { useRoute } from "vue-router";

const { user } = useAuthStore();

// Show Create in the navy bar only on the tickets list (its create route).
const route = useRoute();
const showCreate = computed(() => route.name === "TicketsAgent");

// Unread badge on the header bell (AP mobile has no Alerts tab).
const notificationStore = useNotificationStore();
const unreadCount = computed(() => notificationStore.unread || 0);

const telephonyStore = useTelephonyStore();

onMounted(() => {
  telephonyStore.fetchCallIntegrationStatus();
});
</script>
