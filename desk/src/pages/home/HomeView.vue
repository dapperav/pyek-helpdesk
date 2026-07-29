<template>
  <div class="flex flex-col h-full">
    <!-- TEMP DIAGNOSTIC (green) — proves HomeView is rendering in the router-view
         slot, and surfaces the child's load/mount state. Remove after debugging. -->
    <div
      style="background:#c7f9cc;color:#054;font-size:11px;line-height:1.4;padding:3px 8px;font-family:monospace"
    >
      HV · child={{ isMobileView ? "MobileHome" : "PyekHome" }} ·
      err={{ err || "none" }}
    </div>
    <component :is="isMobileView ? MobileHome : PyekHome" class="min-h-0 flex-1" />
  </div>
</template>

<script setup lang="ts">
// PYEK: /home wrapper. Picks MobileHome (phone) vs PyekHome (desktop) via a
// LIVE, component-scoped useScreenSize. (Temp diagnostic build: green marker +
// explicit loading/error components for the lazy child + error capture, to see
// what happens in the standalone PWA where /home showed the ticket list.)
import { defineAsyncComponent, h, onErrorCaptured, ref } from "vue";
import { useScreenSize } from "@/composables/screen";

const { isMobileView } = useScreenSize();
const err = ref("");
onErrorCaptured((e: any) => {
  err.value = String((e && e.message) || e).slice(0, 90);
  return false;
});

const loadingComponent = {
  render: () =>
    h(
      "div",
      { style: "padding:8px;font:12px monospace;color:#b45309" },
      "loading child chunk…"
    ),
};
const errorComponent = {
  render: () =>
    h(
      "div",
      { style: "padding:8px;font:12px monospace;color:#b00020" },
      "CHILD CHUNK FAILED TO LOAD"
    ),
};

const MobileHome = defineAsyncComponent({
  loader: () => import("@/pages/home/MobileHome.vue"),
  loadingComponent,
  errorComponent,
  timeout: 8000,
});
const PyekHome = defineAsyncComponent({
  loader: () => import("@/pages/home/PyekHome.vue"),
  loadingComponent,
  errorComponent,
  timeout: 8000,
});
</script>
