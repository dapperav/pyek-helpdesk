<template>
  <!-- The peek: Echo silently surfacing over the top edge of something that
       needs eyes. No splash, no bubble, no words (Mark, 2026-08-19). He
       rises all the way out so his flippers OVERLAP the edge he's gripping
       — the clip window extends `overlap`px down over the host element for
       the dimensional look. Host element must be position:relative.
       Scheduling (one peek at a time, 30-min re-peek) lives in
       composables/echoEggs.ts — this component just renders `active`. -->
  <span class="epeek" :class="{ go: active }" :style="clipStyle" aria-hidden="true">
    <img :src="ECHO_POSES.peek" :style="{ width: width + 'px' }" alt="" />
  </span>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { ECHO_POSES } from "./echoAssets";

const props = withDefaults(
  defineProps<{
    active: boolean;
    width?: number;
    /** how far the clip window (and his flippers) reach down over the edge */
    overlap?: number;
    /** distance from the host's left edge; use `right` instead if set */
    left?: string;
    right?: string;
  }>(),
  { width: 62, overlap: 14, left: "20px", right: "" }
);

const clipStyle = computed(() => ({
  ...(props.right ? { right: props.right } : { left: props.left }),
  bottom: `calc(100% - ${props.overlap}px)`,
  width: props.width + "px",
  height: Math.round(props.width * 0.92) + props.overlap + "px",
}));
</script>

<style scoped>
.epeek {
  position: absolute;
  overflow: hidden;
  pointer-events: none;
  z-index: 3;
}
.epeek img {
  display: block;
  height: auto;
  transform: translateY(103%);
  transition: transform 0.9s cubic-bezier(0.25, 0.9, 0.35, 1);
  filter: drop-shadow(0 2px 5px rgba(4, 26, 46, 0.25));
}
.epeek.go img {
  transform: translateY(2%);
}
@media (prefers-reduced-motion: reduce) {
  .epeek img {
    transition: opacity 0.3s ease !important;
    transform: translateY(2%) !important;
    opacity: 0;
  }
  .epeek.go img {
    opacity: 1;
  }
}
</style>
