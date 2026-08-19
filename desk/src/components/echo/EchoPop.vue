<template>
  <!-- Echo pop-in: full pose sticker + one bubble line, splash entrance
       (water swirl + droplets + springy overshoot — one shot, then still;
       calm-seas rule 24 applies: nothing loops). Round 2 (Mark, 2026-08-19):
       he leaves with the SPLASH-BACK — tips nose-down and dives, the water
       erupting IN FRONT of him as he sinks behind the foam; plus two alive
       touches: a one-shot settle head-tilt after landing, and hover-=-caught
       (point at him and he ducks, then sheepishly resurfaces). Parent
       positions this component and drives `show`; timing lives in
       composables/echoEggs.ts. Only the sticker itself takes pointer events
       (for the hover duck) — the layer never blocks a click. -->
  <div
    class="epop"
    :class="['epop--' + layout, { go: show, bye: leaving }]"
    aria-live="polite"
  >
    <div class="epop-swirl"></div>
    <div class="epop-ring"></div>
    <span
      v-for="i in 7"
      :key="i"
      class="epop-drop"
      :style="dropStyle(i - 1)"
    ></span>
    <div class="epop-break" :class="{ ducked: hoverDucked }">
      <div class="epop-bubble">{{ text }}</div>
      <img
        class="epop-img"
        :src="ECHO_POSES[pose]"
        :style="{ width: size + 'px' }"
        alt=""
        @mouseenter="onHover"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { ECHO_POSES, type EchoPose } from "./echoAssets";

const props = withDefaults(
  defineProps<{
    show: boolean;
    pose: EchoPose;
    text: string;
    size?: number;
    /** column = bubble above the sticker (corner layer); row = bubble
     *  beside him (tight spots like the Home crest, where a stacked bubble
     *  would ride up into the hero chips) */
    layout?: "column" | "row";
  }>(),
  { size: 84, layout: "column" }
);

function dropStyle(i: number) {
  // deterministic fan — no Math.random so replays look identical
  const tx = (i - 3) * 15 + (i % 2 ? 6 : -4);
  const ty = -(32 + ((i * 13) % 24));
  return {
    "--tx": tx + "px",
    "--ty": ty + "px",
    animationDelay: 0.26 + (i % 3) * 0.04 + "s",
  };
}

// splash-back exit: when the parent hides him, play the dive before the
// element goes back to its resting hidden state
const leaving = ref(false);
let leaveTimer: number | undefined;
watch(
  () => props.show,
  (now, was) => {
    if (was && !now) {
      leaving.value = true;
      clearTimeout(leaveTimer);
      leaveTimer = window.setTimeout(() => (leaving.value = false), 1_300);
    } else if (now) {
      leaving.value = false;
      clearTimeout(leaveTimer);
    }
  }
);

// hover = caught: instant duck, sheepish rise a beat later
const hoverDucked = ref(false);
let duckTimer: number | undefined;
function onHover() {
  if (!props.show) return;
  hoverDucked.value = true;
  clearTimeout(duckTimer);
  duckTimer = window.setTimeout(() => (hoverDucked.value = false), 1_200);
}
</script>

<style scoped>
.epop {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.epop-break {
  position: absolute;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  width: 100%;
  transform: translateY(115%);
  opacity: 0;
  transition:
    transform 0.6s ease-in 0.05s,
    opacity 0.5s ease;
  /* dive pivot sits where he stands, or the rotation swings him out
     through the corner before the splash starts */
  transform-origin: 78% 82%;
}
.epop-img {
  filter: drop-shadow(0 5px 12px rgba(4, 26, 46, 0.35));
  margin-right: 6px;
  pointer-events: auto;
  transition: transform 0.9s cubic-bezier(0.25, 0.9, 0.35, 1);
}
.epop--row .epop-break {
  flex-direction: row;
  align-items: flex-end;
  justify-content: flex-end;
  gap: 8px;
}
.epop--row .epop-bubble {
  margin-bottom: 10px;
}
.epop-bubble {
  background: #fff;
  color: #22324f;
  border-radius: 13px;
  border-bottom-right-radius: 4px;
  padding: 8px 12px;
  font-size: 13px;
  line-height: 1.45;
  max-width: 230px;
  box-shadow: 0 6px 18px rgba(4, 26, 46, 0.25);
  opacity: 0;
  transform: translateY(5px);
  transition:
    opacity 0.35s ease,
    transform 0.35s ease;
}
.epop.go .epop-break {
  animation: epop-rise 0.68s cubic-bezier(0.3, 1.42, 0.58, 1) 0.32s both;
}
.epop.go .epop-bubble {
  opacity: 1;
  transform: translateY(0);
  transition-delay: 0.9s;
}
/* alive touch: one gentle head-tilt as he settles — one shot, then still */
.epop.go .epop-img {
  animation: epop-settle 0.9s ease-in-out 1.05s both;
}
/* alive touch: caught! instant duck, slow sheepish rise (transition on the
   base class handles the rise; the .ducked drop is fast) */
.epop.go .epop-break.ducked .epop-img {
  transform: translateY(92%);
  transition: transform 0.26s ease-in;
  animation: none;
}
@keyframes epop-settle {
  0%,
  100% {
    transform: rotate(0deg);
  }
  45% {
    transform: rotate(4.5deg);
  }
}
@keyframes epop-rise {
  0% {
    transform: translateY(95%) scale(0.35);
    opacity: 0;
  }
  55% {
    transform: translateY(-6%) scale(1.06);
    opacity: 1;
  }
  100% {
    transform: translateY(0) scale(1);
    opacity: 1;
  }
}
.epop-swirl,
.epop-ring {
  position: absolute;
  right: 14px;
  bottom: -10px;
  width: 88px;
  height: 88px;
  border-radius: 50%;
  opacity: 0;
}
.epop-swirl {
  background: conic-gradient(
    from 40deg,
    rgba(34, 211, 238, 0),
    rgba(34, 211, 238, 0.85),
    rgba(14, 116, 144, 0.9),
    rgba(165, 232, 245, 0.7),
    rgba(34, 211, 238, 0)
  );
  filter: blur(1.5px);
}
.epop-ring {
  border: 2.5px solid rgba(255, 255, 255, 0.75);
}
.epop-drop {
  position: absolute;
  right: 52px;
  bottom: 6px;
  width: 9px;
  height: 9px;
  border-radius: 50% 50% 50% 0;
  background: linear-gradient(180deg, #a5e8f5, #22d3ee);
  opacity: 0;
  transform: rotate(-45deg);
}
.epop.go .epop-swirl {
  animation: epop-swirlgrow 0.5s ease-out both;
}
.epop.go .epop-ring {
  animation: epop-ringout 0.55s ease-out 0.22s both;
}
.epop.go .epop-drop {
  animation: epop-dropfly 0.62s ease-out 0.26s both;
}
@keyframes epop-swirlgrow {
  0% {
    transform: scale(0.15) rotate(0deg);
    opacity: 0;
  }
  35% {
    opacity: 0.9;
  }
  100% {
    transform: scale(1.05) rotate(210deg);
    opacity: 0;
  }
}
@keyframes epop-ringout {
  0% {
    transform: scale(0.3);
    opacity: 0.85;
  }
  100% {
    transform: scale(1.7);
    opacity: 0;
  }
}
@keyframes epop-dropfly {
  0% {
    transform: translate(0, 0) rotate(-45deg) scale(1);
    opacity: 0;
  }
  18% {
    opacity: 0.95;
  }
  60% {
    transform: translate(var(--tx), var(--ty)) rotate(-45deg) scale(0.85);
    opacity: 0.85;
  }
  100% {
    transform: translate(calc(var(--tx) * 1.35), 8px) rotate(-45deg)
      scale(0.45);
    opacity: 0;
  }
}

/* ---- the splash-back exit ------------------------------------------------
   Timing tuned in the mock (echo-eggs-v7): the eruption fires at ~.3s as his
   nose crosses, the foam plume + droplets render IN FRONT of him (z 3/4) so
   he visibly sinks behind the foam, and his tail clears at ~.75s. Opacity is
   pinned to 1 in every frame: replacing the entrance animation drops its
   fill, and without the pins the base opacity:0 transition fades him out
   mid-dive — the "he vanishes before the splash" bug. */
.epop.bye .epop-break {
  animation: epop-dive 1.05s cubic-bezier(0.42, 0.06, 0.6, 0.45) both;
}
@keyframes epop-dive {
  0% {
    transform: translateY(0) rotate(0deg);
    opacity: 1;
  }
  15% {
    transform: translateY(-8%) rotate(-14deg);
    opacity: 1;
  }
  40% {
    transform: translateY(12%) rotate(34deg);
    opacity: 1;
  }
  70% {
    transform: translateY(48%) rotate(48deg);
    opacity: 1;
  }
  100% {
    transform: translateY(155%) rotate(55deg);
    opacity: 1;
  }
}
.epop.bye .epop-bubble {
  animation: epop-bubblepop 0.18s ease-in both;
  transition: none;
}
@keyframes epop-bubblepop {
  to {
    transform: scale(0.55) translateY(6px);
    opacity: 0;
  }
}
.epop.bye .epop-ring {
  animation: epop-ringout 0.8s ease-out 0.28s both;
}
.epop.bye .epop-drop {
  z-index: 4;
  animation: epop-dropsplash 0.85s ease-out 0.3s both;
}
@keyframes epop-dropsplash {
  0% {
    transform: translate(0, 6px) rotate(-45deg) scale(1.15);
    opacity: 0;
  }
  14% {
    opacity: 1;
  }
  55% {
    transform: translate(var(--tx), calc(var(--ty) * 1.9)) rotate(-45deg)
      scale(0.9);
    opacity: 0.95;
  }
  100% {
    transform: translate(calc(var(--tx) * 1.5), 16px) rotate(-45deg)
      scale(0.4);
    opacity: 0;
  }
}
.epop.bye .epop-swirl {
  background: radial-gradient(
    ellipse at center,
    rgba(255, 255, 255, 0.95) 0%,
    rgba(220, 245, 252, 0.75) 45%,
    rgba(255, 255, 255, 0) 75%
  );
  filter: blur(1px);
  z-index: 3;
  bottom: -24px; /* foam hugs the waterline — he stays visible above it */
  animation: epop-plumeup 0.85s ease-out 0.32s both;
}
@keyframes epop-plumeup {
  0% {
    transform: scale(0.3, 0.12) translateY(10px);
    opacity: 0;
  }
  28% {
    opacity: 0.85;
  }
  100% {
    transform: scale(1.4, 0.55) translateY(-10px);
    opacity: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .epop-break,
  .epop.go .epop-break,
  .epop.bye .epop-break {
    animation: none !important;
    transform: none !important;
    transition: opacity 0.3s ease !important;
  }
  .epop.go .epop-break {
    opacity: 1;
  }
  .epop.bye .epop-break {
    opacity: 0;
  }
  .epop-bubble {
    transform: none !important;
  }
  .epop.go .epop-img,
  .epop.go .epop-break.ducked .epop-img {
    animation: none;
    transform: none;
  }
  .epop-swirl,
  .epop-ring,
  .epop-drop {
    display: none;
  }
}
</style>
