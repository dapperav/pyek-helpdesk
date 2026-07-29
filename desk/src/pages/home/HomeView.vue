<template>
  <div class="flex flex-col h-full">
    <!-- TEMP DIAGNOSTIC (green) — confirms the eager fix. Remove after verified. -->
    <div
      style="background:#c7f9cc;color:#054;font-size:11px;line-height:1.4;padding:3px 8px;font-family:monospace"
    >
      HV · child={{ isMobileView ? "MobileHome" : "PyekHome" }} ·
      err={{ err || "none" }}
    </div>
    <MobileHome v-if="isMobileView" class="min-h-0 flex-1" />
    <component v-else :is="PyekHome" class="min-h-0 flex-1" />
  </div>
</template>

<script setup lang="ts">
// PYEK: /home wrapper. Picks MobileHome (phone) vs PyekHome (desktop) via a
// LIVE, component-scoped useScreenSize.
// FIX: MobileHome is now a STATIC import (bundled into the eager app code, no
// lazy chunk). In the installed iOS PWA, fetching a not-yet-loaded lazy chunk on
// a Dashboard tap silently failed, so /home fell back to the ticket list. Eager
// import means tapping Dashboard needs no new network fetch. PyekHome (desktop,
// chart-heavy) stays lazy — the desktop path was never affected.
import { defineAsyncComponent, onErrorCaptured, ref } from "vue";
import { useScreenSize } from "@/composables/screen";
import MobileHome from "@/pages/home/MobileHome.vue";

const PyekHome = defineAsyncComponent(() => import("@/pages/home/PyekHome.vue"));

const { isMobileView } = useScreenSize();
const err = ref("");
onErrorCaptured((e: any) => {
  err.value = String((e && e.message) || e).slice(0, 90);
  return false;
});
</script>
