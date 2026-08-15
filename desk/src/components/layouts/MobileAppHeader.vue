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
    <!-- Brand mark first, then the view-switcher teleport target. On the
         tickets list the switcher renders the view name as the page title
         ("POS Tickets ▾") and the wordmark steps aside (v-show — same rule as
         the Create button below: its condition flips on the list <-> detail
         transition, so it must never mount/unmount next to the teleport).
         Every other page shows mark + wordmark as before. -->
    <PyekMark class="h-5 w-auto shrink-0" />
    <div id="mobile-header-view" class="flex min-w-0 shrink items-center"></div>
    <span v-show="!showCreate" class="text-base tracking-tight">
      <span class="font-bold text-white">PYEK</span
      ><span class="font-medium" style="color: #67e8f9">MAIL</span>
    </span>
    <!-- Create lives here on the tickets list (route-aware, reliable — no
         teleport). White-on-navy for contrast.
         v-show rather than v-if for the same reason as #app-header below: this
         sits in the same shell as the teleport target and its condition flips on
         the exact list <-> detail transition, so mounting/unmounting it is churn
         next to a teleport mid-patch. display:none reclaims the space identically. -->
    <RouterLink
      v-show="showCreate"
      :to="{ name: 'TicketAgentNew' }"
      class="ms-auto inline-flex items-center gap-1.5 rounded-lg bg-white px-3 py-1.5 text-sm font-medium active:opacity-80"
      style="color: #1b2a4a"
    >
      <FeatherIcon name="plus" class="size-4" />
      {{ __("Create") }}
    </RouterLink>
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
  <!-- Hidden on the tickets list (switcher lives in the navy bar) AND on Home
       (Mark, 2026-08-15: "Home" + Refresh was dead weight — the navy bar
       already brands the page and pull-to-refresh covers refreshing).
       Still v-show, never v-if — the teleport-target rule below. -->
  <div
    v-show="route.name !== 'TicketsAgent' && route.name !== 'Home'"
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
import { computed, onMounted } from "vue";
import { useRoute } from "vue-router";

const { user } = useAuthStore();

// Show Create in the navy bar only on the tickets list (its create route).
const route = useRoute();
const showCreate = computed(() => route.name === "TicketsAgent");

const telephonyStore = useTelephonyStore();

onMounted(() => {
  telephonyStore.fetchCallIntegrationStatus();
});
</script>
