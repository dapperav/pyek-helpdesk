<template>
  <div class="flex h-screen w-screen">
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
