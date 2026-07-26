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
    <span class="text-base font-semibold tracking-wide text-white">
      PYEKMAIL
    </span>
    <!-- Right-aligned zone for the page's primary action (e.g. Create),
         teleported here on mobile so it sits in the navy bar. -->
    <div id="mobile-header-action" class="ms-auto flex items-center"></div>
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
import CallUI from "../telephony/CallUI.vue";
import { useAuthStore } from "@/stores/auth";
import { useTelephonyStore } from "@/stores/telephony";
import { onMounted } from "vue";

const { user } = useAuthStore();

const telephonyStore = useTelephonyStore();

onMounted(() => {
  telephonyStore.fetchCallIntegrationStatus();
});
</script>
