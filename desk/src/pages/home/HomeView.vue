<template>
  <!-- Mobile grows with its content (the layout scroller scrolls it);
       desktop stays a fixed-height column (PyekHome scrolls itself). -->
  <div class="flex flex-col" :class="isMobileView ? 'min-h-full' : 'h-full'">
    <component :is="isMobileView ? MobileHome : PyekHome" class="min-h-0 flex-1" />
  </div>
</template>

<script setup lang="ts">
// PYEK: /home wrapper. Picks MobileHome (phone) vs PyekHome (desktop) via a
// LIVE, component-scoped useScreenSize — the router's module-scope isMobileView
// is frozen at load and unreliable here.
import { defineAsyncComponent } from "vue";
import { useScreenSize } from "@/composables/screen";
import { isStaleChunkError, recoverFromStaleChunk } from "@/staleChunk";

const { isMobileView } = useScreenSize();

// Both children are lazy, so /home needs TWO chunks to land and carries the
// stale-chunk risk twice over — it was the worst-hit screen in the installed
// PWA. Retry once (covers a flaky mobile connection), then reload to pick up
// fresh chunk URLs. See staleChunk.ts.
function homeChunk(loader: () => Promise<any>) {
  return defineAsyncComponent({
    loader,
    timeout: 15000,
    onError(error, retry, fail, attempts) {
      if (attempts <= 1) return retry();
      if (
        isStaleChunkError(error) &&
        recoverFromStaleChunk(window.location.pathname + window.location.search)
      ) {
        return;
      }
      fail();
    },
  });
}

const MobileHome = homeChunk(() => import("@/pages/home/MobileHome.vue"));
const PyekHome = homeChunk(() => import("@/pages/home/PyekHome.vue"));
</script>
