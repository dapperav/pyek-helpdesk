<template>
  <!-- Navy brand bar — bookends the navy footer. It extends up behind the
       status bar (padding-top = the notch/status inset, needed since the
       viewport is viewport-fit=cover); status text is white via
       apple-mobile-web-app-status-bar-style=black-translucent. Brand + menu
       only — the page controls live on the white row below, so nothing here
       needs light-on-navy restyling. -->
  <div
    class="flex items-center gap-2 px-3"
    style="
      background-color: #1b2a4a;
      height: calc(3rem + env(safe-area-inset-top));
      padding-top: env(safe-area-inset-top);
    "
  >
    <button
      type="button"
      class="grid size-8 shrink-0 place-items-center rounded text-white/90 transition active:bg-white/10"
      aria-label="Open menu"
      @click="sidebarOpened = !sidebarOpened"
    >
      <FeatherIcon name="menu" class="size-5" />
    </button>
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
  <!-- White controls row: the page title / breadcrumb / view switcher /
       Create button teleport into #app-header here, on white as designed. -->
  <div class="flex h-12 items-center border-b border-outline-gray-2 pl-1 pr-2">
    <header id="app-header" class="w-full min-w-0"></header>
  </div>
  <CallUI class="mr-3 mt-2" :userEmail="user" />
</template>

<script setup>
import { mobileSidebarOpened as sidebarOpened } from "@/composables/mobile";
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
