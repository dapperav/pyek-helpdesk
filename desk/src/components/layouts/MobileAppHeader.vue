<template>
  <div class="flex border-b h-12 items-center">
    <div class="z-20 -mr-4 ml-1 flex items-center justify-center">
      <Button variant="ghosted" @click="sidebarOpened = !sidebarOpened">
        <FeatherIcon name="menu" class="size-4" />
      </Button>
    </div>
    <!-- PYEK: brand lockup so the PYEKMAIL identity shows on mobile / the
         installed PWA — the navy sidebar that carries the brand on desktop is
         drawer-only on mobile, so without this the top bar is unbranded. -->
    <div class="flex shrink-0 items-center gap-1.5 pl-5 pr-2">
      <PyekMark class="h-5 w-auto shrink-0" />
      <span class="text-base font-semibold tracking-wide text-ink-gray-9">
        PYEKMAIL
      </span>
    </div>
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
