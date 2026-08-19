<template>
  <div class="flex h-screen w-screen">
    <Sidebar />
    <div class="flex-1 flex flex-col h-full overflow-auto relative">
      <AppHeader />
      <slot />
    </div>
    <Notifications />
    <CommandPalette />
    <!-- Echo easter-egg layer: event pops (streaks, SLA saves, night lines,
         the hidden trigger) surface bottom-right on whatever agent screen is
         open. Agent desktop only — customers never meet the easter eggs.
         Scarcity rules live in composables/echoEggs.ts. -->
    <div v-if="!isCustomerPortal" class="pyek-echo-layer">
      <EchoPop
        :show="globalPop.show"
        :pose="globalPop.pose"
        :text="globalPop.text"
      />
    </div>
  </div>
</template>
<script setup>
import { onMounted } from "vue";
import { Notifications, CommandPalette } from "@/components";
import EchoPop from "@/components/echo/EchoPop.vue";
import { globalPop, startEchoEggs } from "@/composables/echoEggs";
import { isCustomerPortal } from "@/utils";
import AppHeader from "./AppHeader.vue";
import Sidebar from "./Sidebar.vue";

onMounted(() => {
  if (!isCustomerPortal.value) startEchoEggs();
});
</script>
<style scoped>
.pyek-echo-layer {
  position: fixed;
  right: 18px;
  bottom: 10px;
  width: 270px;
  height: 200px;
  pointer-events: none;
  z-index: 45;
}
</style>
