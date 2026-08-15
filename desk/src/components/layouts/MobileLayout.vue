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
  <!-- Own surface ground: the document behind is navy (letterbox absorb,
       see index.css), so the shell must paint the app's white itself. -->
  <div
    class="relative flex"
    style="position: fixed; inset: 0; background: var(--surface-base)"
    :style="{
      // Matches the slimmed nav: ~54px of content row plus its reduced
      // home-indicator padding (see MobileBottomNav). The drop (below) is
      // subtracted because that part of the nav hangs below the viewport.
      '--pyek-nav-h': showBottomNav
        ? `calc(54px + max(env(safe-area-inset-bottom) - 10px, 0px) - ${navDrop}px)`
        : '0px',
      // iOS letterbox drop: on Mark's iPhone the standalone viewport is
      // top-anchored and ends ~59pt above the physical screen bottom (the
      // navy letterbox). The render canvas continues below the viewport
      // edge (the document background paints there), so the nav shifts
      // DOWN by that dead gap to hug the physical edge like a native tab
      // bar. Zero on healthy phones (no gap), Safari (not standalone),
      // landscape, and bottom-anchored viewports (envT ~0).
      '--pyek-nav-drop': `${navDrop}px`,
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
      <!-- Safe-area underlay: on a real iPhone, iOS does not reliably paint
           the frosted nav's own background across its home-indicator PADDING
           zone (backdrop-filter quirk), so whatever sits behind shows there.
           Round 1 that was the OS underlay (dark slab); painting it white
           (PR 130) just made a white band. Painting it the nav's navy makes
           the zone read as the nav continuing to the screen edge — which is
           the design intent. Invisible wherever env() is 0 (desktop, dev).
           z-30: above page content, below the tide sheet (40) and nav (50). -->
      <div
        v-show="showBottomNav"
        aria-hidden="true"
        class="pointer-events-none absolute inset-x-0 z-30"
        style="
          bottom: calc(-1 * var(--pyek-nav-drop, 0px));
          height: calc(env(safe-area-inset-bottom) + var(--pyek-nav-drop, 0px));
          background: #1b2a4a;
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
import { installViewportHeal } from "@/composables/viewportHeal";
import { canGoBackInApp } from "@/composables/mobile";

const route = useRoute();
const showBottomNav = computed(
  () => route.name !== "TicketAgent" || !canGoBackInApp.value
);

// --- iOS letterbox drop (see the --pyek-nav-drop comment in the template).
// Conditions, all measured live: installed standalone app, portrait, the
// viewport is short of the screen by a status-bar-ish amount (8..80),
// AND env(safe-area-inset-top) is real (>20) — that combination is the
// top-anchored letterboxed state; a bottom-anchored viewport (envT 0)
// must NOT drop or the nav would slide off the physical screen.
const navDrop = ref(0);
function computeNavDrop() {
  try {
    const standalone =
      window.matchMedia?.("(display-mode: standalone)")?.matches ||
      navigator.standalone === true;
    const portrait = window.innerWidth < window.innerHeight;
    const gap = window.screen.height - window.innerHeight;
    let envTop = 0;
    if (standalone && portrait && gap > 8 && gap < 80) {
      const probe = document.createElement("div");
      probe.style.cssText =
        "position:fixed;top:0;left:0;width:1px;visibility:hidden;height:env(safe-area-inset-top)";
      document.body.appendChild(probe);
      envTop = probe.getBoundingClientRect().height;
      probe.remove();
    }
    navDrop.value =
      standalone && portrait && gap > 8 && gap < 80 && envTop > 20 ? gap : 0;
  } catch {
    navDrop.value = 0;
  }
}

const scrollEl = ref(null);
provideMobileScrollEl(scrollEl);

// Scoped to this layout's lifetime so a window resized back to desktop (which
// swaps the layout component) returns the document to normal scrolling.
let teardownHeal = null;
onMounted(() => {
  document.documentElement.classList.add("pyek-mobile-shell");
  // iOS standalone keyboard bug: the viewport shrinks by the status-bar
  // inset the first time the keyboard opens and never recovers — see
  // composables/viewportHeal.ts for the whole story.
  teardownHeal = installViewportHeal(() => scrollEl.value);
  computeNavDrop();
  window.addEventListener("resize", computeNavDrop);
});
onUnmounted(() => {
  document.documentElement.classList.remove("pyek-mobile-shell");
  teardownHeal?.();
  window.removeEventListener("resize", computeNavDrop);
});
</script>
