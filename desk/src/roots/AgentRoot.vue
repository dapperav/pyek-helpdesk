<template>
  <Layout class="isolate">
    <!-- Every page historically got overflow-auto here, making each page its
         own scroller NESTED inside MobileLayout's — on an iPhone, Home could
         strand one scroller mid-scroll with no gesture able to chain back up
         (Mark, 2026-08-15). On the phone's Home the page now GROWS instead,
         so the layout scroller (the one pull-to-refresh listens to) is the
         single scroller. List/detail keep their proven inner-scroller layout.
         Class flip only — same component instance, no remount (shell rule). -->
    <router-view
      :class="
        isMobileView && route.name === 'Home'
          ? 'flex min-h-full flex-col'
          : 'flex flex-1 flex-col overflow-auto'
      "
    />
  </Layout>
</template>

<script setup lang="ts">
import { useAuthStore } from "@/stores/auth";
import { computed, defineAsyncComponent, onBeforeMount } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useScreenSize } from "@/composables/screen";
const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();

const { isMobileView } = useScreenSize();

const MobileLayout = defineAsyncComponent(
  () => import("@/components/layouts/MobileLayout.vue")
);
const DesktopLayout = defineAsyncComponent(
  () => import("@/components/layouts/DesktopLayout.vue")
);

const Layout = computed(() => {
  if (isMobileView.value) {
    return MobileLayout;
  } else {
    return DesktopLayout;
  }
});

onBeforeMount(() => {
  if (!authStore.hasDeskAccess) {
    router.replace({ name: "TicketsCustomer" });
  }
});
</script>
