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
    <!-- Create lives here on the tickets list (route-aware, reliable — no
         teleport). White-on-navy for contrast. -->
    <RouterLink
      v-if="showCreate"
      :to="{ name: 'TicketAgentNew' }"
      class="ms-auto inline-flex items-center gap-1.5 rounded-lg bg-white px-3 py-1.5 text-sm font-medium active:opacity-80"
      style="color: #1b2a4a"
    >
      <FeatherIcon name="plus" class="size-4" />
      {{ __("Create") }}
    </RouterLink>
  </div>
  <!-- TEMP PWA DIAGNOSTIC (always visible on mobile; remove after debugging). -->
  <div
    style="background:#fde68a;color:#111;font-size:11px;line-height:1.4;padding:3px 8px;font-family:monospace"
  >
    dbg · route={{ route.name }} · w={{ width }} · pwa={{ standalone }} ·
    m={{ isMobileView }}<span v-if="lastError"> · {{ lastError }}</span>
  </div>
  <!-- White controls row: other pages teleport their title / breadcrumb into
       #app-header here (on white as designed). Hidden on the tickets list,
       where the view switcher now lives in the navy bar above — reclaiming a
       full row of screen space.
       IMPORTANT: use v-show, NOT v-if. #app-header is a Teleport target for
       LayoutHeader (e.g. the ticket detail teleports its breadcrumb + status
       dropdown here, and PyekHome/Dashboard teleport their titles). With v-if
       the target is created/destroyed across the list <-> detail/home route
       change, and a LayoutHeader teleporting into a target that's churning
       mid-transition crashes Vue's patcher ("Cannot read properties of null
       (reading 'emitsOptions')") — which left the page blank and the bottom nav
       vanished (and blocked ticket clicks). v-show keeps the target permanently
       in the DOM (display:none reclaims the row's space on the list just like
       v-if did), so the teleport is always stable. -->
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
import { useTelephonyStore } from "@/stores/telephony";
import { useScreenSize } from "@/composables/screen";
import { lastError } from "@/lastError";
import { computed, onMounted } from "vue";
import { useRoute } from "vue-router";

const { user } = useAuthStore();

// Show Create in the navy bar only on the tickets list (its create route).
const route = useRoute();
const showCreate = computed(() => route.name === "TicketsAgent");

// TEMP diagnostic bindings (remove after debugging the PWA dashboard issue).
const { isMobileView, size } = useScreenSize();
const width = computed(() => size.width);
const standalone =
  typeof window !== "undefined" &&
  ((window.matchMedia &&
    window.matchMedia("(display-mode: standalone)").matches) ||
    window.navigator.standalone === true)
    ? 1
    : 0;

const telephonyStore = useTelephonyStore();

onMounted(() => {
  telephonyStore.fetchCallIntegrationStatus();
});
</script>
