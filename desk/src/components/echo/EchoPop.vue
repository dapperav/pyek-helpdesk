<template>
  <!-- Echo pop-in: full pose sticker + one bubble line, splash entrance
       (water swirl + droplets + springy overshoot — one shot, then still;
       Mark approved the splash on the echo-eggs mock, calm-seas rule 24
       still applies: nothing loops). Parent positions this component
       (absolute/fixed wrapper) and drives `show`; timing lives in
       composables/echoEggs.ts. pointer-events stay off — Echo never blocks
       a click. -->
  <div
    class="epop"
    :class="['epop--' + layout, { go: show }]"
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
    <div class="epop-break">
      <div class="epop-bubble">{{ text }}</div>
      <img
        class="epop-img"
        :src="ECHO_POSES[pose]"
        :style="{ width: size + 'px' }"
        alt=""
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ECHO_POSES, type EchoPose } from "./echoAssets";

withDefaults(
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
}
.epop-img {
  filter: drop-shadow(0 5px 12px rgba(4, 26, 46, 0.35));
  margin-right: 6px;
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
  animation: epop-swirl 0.5s ease-out both;
}
.epop.go .epop-ring {
  animation: epop-ring 0.55s ease-out 0.22s both;
}
.epop.go .epop-drop {
  animation: epop-drop 0.62s ease-out 0.26s both;
}
@keyframes epop-swirl {
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
@keyframes epop-ring {
  0% {
    transform: scale(0.3);
    opacity: 0.85;
  }
  100% {
    transform: scale(1.7);
    opacity: 0;
  }
}
@keyframes epop-drop {
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
@media (prefers-reduced-motion: reduce) {
  .epop-break,
  .epop.go .epop-break {
    animation: none !important;
    transform: none !important;
    transition: opacity 0.3s ease !important;
  }
  .epop.go .epop-break {
    opacity: 1;
  }
  .epop-bubble {
    transform: none !important;
  }
  .epop-swirl,
  .epop-ring,
  .epop-drop {
    display: none;
  }
}
</style>
