<template>
  <!-- Use dynamic viewport height (100dvh), not 100vh. With viewport-fit=cover,
       100vh on iOS extends past the visible area and pushes the bottom nav
       (labels + safe-area padding) off-screen. 100dvh matches what's actually
       visible; the vh line is the fallback for browsers without dvh. -->
  <div class="flex w-screen" style="height: 100vh; height: 100dvh">
    <MobileSidebar />
    <div class="flex h-full min-w-0 flex-1 flex-col">
      <MobileAppHeader />
      <!-- Scrollable content between the header and the pinned bottom nav. -->
      <div class="min-h-0 flex-1 overflow-auto">
        <slot />
      </div>
      <!-- Hidden on the ticket detail screen, which has its own sticky reply
           box pinned to the bottom. -->
      <MobileBottomNav v-if="showBottomNav" />
    </div>
  </div>
</template>
<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import MobileSidebar from "./MobileSidebar.vue";
import MobileAppHeader from "./MobileAppHeader.vue";
import MobileBottomNav from "./MobileBottomNav.vue";

const route = useRoute();
const showBottomNav = computed(() => route.name !== "TicketAgent");
</script>
