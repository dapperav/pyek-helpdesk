<template>
  <!-- Use dynamic viewport height (100dvh), not 100vh. With viewport-fit=cover,
       100vh on iOS extends past the visible area and pushes the bottom nav
       (labels + safe-area padding) off-screen. 100dvh matches what's actually
       visible; the vh line is the fallback for browsers without dvh. -->
  <div class="flex w-screen" style="height: 100vh; height: 100dvh">
    <MobileSidebar />
    <div class="flex h-full min-w-0 flex-1 flex-col">
      <MobileAppHeader />
      <!-- Scrollable content between the header and the pinned bottom nav. This
           is the only scrolling element on a phone, so it's shared with pages
           that want a pull-to-refresh gesture — they can't listen on their own
           root, which doesn't scroll. -->
      <div ref="scrollEl" class="min-h-0 flex-1 overflow-auto">
        <slot />
      </div>
      <!-- Hidden on the ticket detail screen, which has its own sticky reply box
           pinned to the bottom — EXCEPT when the app was cold-launched straight
           onto that ticket, which is what a push notification does. Arriving
           that way there is no history behind you, so hiding the nav left no way
           out of the screen at all and the app had to be force-quit. Tapping in
           from a list still gets the roomier no-nav layout, since breadcrumb and
           swipe-back both work there. -->
      <!-- v-show, NOT v-if — the same rule MobileAppHeader's #app-header follows,
           and for the same reason. Mounting/unmounting anything in this shell
           during a list <-> detail transition churns the tree while LayoutHeader
           is teleporting into #app-header, and Vue's patcher dies with
           "Cannot read properties of null (reading 'emitsOptions')". The visible
           symptom is not an error message: the ticket screen silently fails to
           render and TICKET TAPS STOP WORKING.
           This was a v-if before, which mostly got away with it because the value
           flipped exactly once per navigation. Making it depend on
           canGoBackInApp (which updates in the router's afterEach) added a second
           flip mid-transition and reproduced the crash. v-show removes the whole
           class of problem — the nav element always exists and only its display
           changes, which reclaims the row just as v-if did. -->
      <MobileBottomNav v-show="showBottomNav" />
    </div>
  </div>
</template>
<script setup>
import { computed, ref } from "vue";
import { useRoute } from "vue-router";
import MobileSidebar from "./MobileSidebar.vue";
import MobileAppHeader from "./MobileAppHeader.vue";
import MobileBottomNav from "./MobileBottomNav.vue";
import { provideMobileScrollEl } from "@/composables/pullToRefresh";
import { canGoBackInApp } from "@/composables/mobile";

const route = useRoute();
const showBottomNav = computed(
  () => route.name !== "TicketAgent" || !canGoBackInApp.value
);

const scrollEl = ref(null);
provideMobileScrollEl(scrollEl);
</script>
