<template>
  <div class="flex flex-col h-full">
    <!-- TEMP DIAGNOSTIC STRIP (remove once the mobile dashboard is confirmed). -->
    <div
      style="background:#fde68a;color:#111;font-size:11px;line-height:1.3;padding:4px 8px;font-family:monospace"
    >
      home · route={{ route.name }} · w={{ width }} · mobile={{ isMobileView }} ·
      cmp={{ isMobileView ? "MobileHome" : "PyekHome" }}<span v-if="err"> · ERR: {{ err }}</span>
    </div>
    <component :is="isMobileView ? MobileHome : PyekHome" class="flex-1 min-h-0" />
  </div>
</template>

<script setup lang="ts">
// PYEK: /home wrapper. Decides MobileHome vs PyekHome with a LIVE, component-scoped
// useScreenSize (the router used a module-scope useScreenSize whose resize listener
// never attached, so its isMobileView was frozen at page-load width). Also carries a
// temporary on-screen debug strip + error capture so a device screenshot reveals what
// actually renders.
import { defineAsyncComponent, onErrorCaptured, ref, computed } from "vue";
import { useRoute } from "vue-router";
import { useScreenSize } from "@/composables/screen";

const route = useRoute();
const { isMobileView, size } = useScreenSize();
const width = computed(() => size.width);
const err = ref("");
onErrorCaptured((e: any) => {
  err.value = String((e && e.message) || e);
  return false;
});

const MobileHome = defineAsyncComponent(() => import("@/pages/home/MobileHome.vue"));
const PyekHome = defineAsyncComponent(() => import("@/pages/home/PyekHome.vue"));
</script>
