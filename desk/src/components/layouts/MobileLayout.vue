<template>
  <!-- position:fixed + inset:0 pins the shell to the VISUAL viewport — no vh
       unit involved, so there is nothing for iOS's collapsing toolbar or the
       keyboard to desynchronize. Paired with html.pyek-mobile-shell (added in
       onMounted, rules in index.css), which forbids the document itself from
       scrolling: previously any page whose content overflowed this column grew
       the body, and the bottom nav rendered below the fold until you scrolled.
       The inner .min-h-0 container is the ONLY scroller on a phone. -->
  <!-- --pyek-nav-h: the glass nav is an OVERLAY now (content scrolls beneath
       it, the tide menu rises behind it), so everything that must clear it —
       the scroller's bottom padding, the ticket screen's sticky composer, the
       list's bulk bar — reads this one variable. 0px when the nav is hidden. -->
  <div
    class="relative flex"
    style="position: fixed; inset: 0"
    :style="{
      '--pyek-nav-h': showBottomNav
        ? 'calc(62px + env(safe-area-inset-bottom))'
        : '0px',
    }"
  >
    <MobileMenuSheet />
    <div class="flex h-full min-w-0 flex-1 flex-col">
      <MobileAppHeader />
      <!-- Scrollable content between the header and the glass bottom nav. This
           is the only scrolling element on a phone, so it's shared with pages
           that want a pull-to-refresh gesture — they can't listen on their own
           root, which doesn't scroll. Bottom padding keeps the last row
           readable above the frosted nav. -->
      <div
        ref="scrollEl"
        class="min-h-0 flex-1 overflow-auto"
        :style="{ paddingBottom: 'var(--pyek-nav-h)' }"
      >
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
      <!-- Safe-area underlay: on a real iPhone the nav's translucent
           home-indicator padding zone has nothing white behind it to blur
           (the OS underlay shows through), so it rendered as a solid navy
           slab and the nav read as floating above a dead band. This paints
           the page surface behind exactly that zone so the frosted nav looks
           continuous. Invisible wherever env() is 0 (desktop, dev Chrome).
           z-30: above page content, below the tide sheet (40) and nav (50). -->
      <div
        v-show="showBottomNav"
        aria-hidden="true"
        class="pointer-events-none absolute inset-x-0 bottom-0 z-30"
        style="
          height: env(safe-area-inset-bottom);
          background: var(--surface-base);
        "
      />
      <MobileBottomNav v-show="showBottomNav" />
    </div>
  </div>
</template>
<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute } from "vue-router";
import MobileMenuSheet from "./MobileMenuSheet.vue";
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

// Scoped to this layout's lifetime so a window resized back to desktop (which
// swaps the layout component) returns the document to normal scrolling.
onMounted(() => document.documentElement.classList.add("pyek-mobile-shell"));
onUnmounted(() =>
  document.documentElement.classList.remove("pyek-mobile-shell")
);
</script>
