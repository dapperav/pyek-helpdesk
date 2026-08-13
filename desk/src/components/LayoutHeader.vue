<template>
  <Teleport to="#app-header" v-if="showHeader">
    <slot>
      <header
        class="flex h-10.5 items-center justify-between mx-4 md:mx-5 md:mr-0"
      >
        <div class="flex items-center gap-2 min-w-0 flex-1">
          <slot name="left-header" />
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <slot name="right-header" class="flex items-center gap-2" />
        </div>
      </header>
    </slot>
  </Teleport>
</template>
<script setup>
import { nextTick, onUnmounted, ref } from "vue";

// This delayed reveal is LOAD-BEARING: on a cold mount the app tree is built
// detached, so the #app-header target is not in the document yet during this
// component's own mount — an immediate Teleport would silently fail to
// resolve it and mount nothing (and the next unmount of those never-mounted
// children crashes the patcher). Waiting one tick mounts the teleport via an
// update, after the tree is attached. Same class of bug as the mobile
// #mobile-header-view teleport fixed with `defer` in Tickets.vue.
//
// The guard matters too: this nextTick is not tied to any lifecycle hook, so
// without it a component unmounted in the same tick (fast route double-swap)
// would have state set on a dead instance mid-transition.
const showHeader = ref(false);
let alive = true;
onUnmounted(() => {
  alive = false;
});

nextTick(() => {
  if (alive) showHeader.value = true;
});
</script>
