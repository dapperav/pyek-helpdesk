<template>
  <component :is="isMobileView ? MobileHome : PyekHome" />
</template>

<script setup lang="ts">
// PYEK: /home wrapper. Picks MobileHome (phone) vs PyekHome (desktop) using a
// LIVE, component-scoped useScreenSize. The router previously chose the /home
// component via a MODULE-scope useScreenSize whose onMounted resize listener
// never attached, so its isMobileView was frozen at page-load width and could
// resolve wrong on a device — landing the mobile "Dashboard" tab on the wrong
// page. Deciding here (inside a real component) keeps the check live + correct.
import { defineAsyncComponent } from "vue";
import { useScreenSize } from "@/composables/screen";

const { isMobileView } = useScreenSize();
const MobileHome = defineAsyncComponent(() => import("@/pages/home/MobileHome.vue"));
const PyekHome = defineAsyncComponent(() => import("@/pages/home/PyekHome.vue"));
</script>
