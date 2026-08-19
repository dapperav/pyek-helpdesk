<template>
  <!-- The peek: Echo silently surfacing over the top edge of something that
       needs eyes. No splash, no bubble, no words (Mark, 2026-08-19). He
       rises all the way out so his flippers OVERLAP the edge he's gripping
       — the clip window extends `overlap`px down over the host element for
       the dimensional look. Host element must be position:relative.
       Round 2: he leaves with the "caught!" quick duck (fast drop), and
       hovering him while he's up ducks him instantly — he sheepishly rises
       back a beat later. Scheduling (one sighting at a time, shared budget)
       lives in composables/echoEggs.ts. -->
  <span class="epeek" :class="{ go: active }" :style="clipStyle" aria-hidden="true">
    <img
      :src="ECHO_POSES.peek"
      :class="{ ducked: hoverDucked }"
      :style="{ width: width + 'px' }"
      alt=""
      @mouseenter="onHover"
    />
  </span>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
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

// hover = caught: instant duck, sheepish rise a beat later
const hoverDucked = ref(false);
let duckTimer: number | undefined;
function onHover() {
  if (!props.active) return;
  hoverDucked.value = true;
  clearTimeout(duckTimer);
  duckTimer = window.setTimeout(() => (hoverDucked.value = false), 1_200);
}
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
  /* exit = the "caught!" quick duck: fast ease-in drop. The slow rise
     lives on the .go state so entrances stay calm. */
  transition: transform 0.3s ease-in;
  filter: drop-shadow(0 2px 5px rgba(4, 26, 46, 0.25));
  pointer-events: auto;
}
.epeek.go img {
  transform: translateY(2%);
  transition: transform 0.9s cubic-bezier(0.25, 0.9, 0.35, 1);
}
.epeek.go img.ducked {
  transform: translateY(103%);
  transition: transform 0.26s ease-in;
}
@media (prefers-reduced-motion: reduce) {
  .epeek img,
  .epeek.go img,
  .epeek.go img.ducked {
    transition: opacity 0.3s ease !important;
    transform: translateY(2%) !important;
    opacity: 0;
  }
  .epeek.go img {
    opacity: 1;
  }
  .epeek.go img.ducked {
    opacity: 0;
  }
}
</style>
