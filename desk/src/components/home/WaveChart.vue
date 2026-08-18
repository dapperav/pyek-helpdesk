<template>
  <!-- An honest area chart wearing an ocean skin (Mark, 2026-08-18): the
       crest line rides the real weekly trend; the slow sine undulation is
       texture, tuned to long rollers after "too squiggly" and "sea sick"
       feedback — amp ~2.4px, wavelength 110px+, quarter-speed phase. Colors
       are the dataviz-validated trio (light #0891b2/#e11d48/#7c3aed, night
       swaps violet to #8b5cf6); identity is never color-alone — the legend
       carries name + latest value, and hover gives exact numbers. -->
  <div ref="mount" class="wave-mount relative" @mousemove="onMove" @mouseleave="onLeave">
    <svg ref="svg" :viewBox="`0 0 ${W} ${H}`" preserveAspectRatio="none" class="block w-full overflow-visible" style="height: 120px">
      <line :x1="0" :x2="W" :y1="H / 2" :y2="H / 2" stroke="currentColor" opacity="0.08" />
      <g v-for="(sr, si) in series" :key="sr.name">
        <path :d="paths[si]?.area" :fill="color(si)" opacity="0.3" />
        <path :d="paths[si]?.crest" fill="none" :stroke="color(si)" stroke-width="2" />
        <path
          :d="paths[si]?.crest"
          fill="none"
          stroke="#ffffff"
          stroke-width="1"
          opacity="0.55"
          transform="translate(0,-2.5)"
        />
      </g>
      <line
        v-if="hoverIdx !== null"
        :x1="hoverX"
        :x2="hoverX"
        :y1="6"
        :y2="H - PADB"
        stroke="currentColor"
        opacity="0.3"
        stroke-dasharray="3 3"
      />
    </svg>
    <div
      v-if="hoverIdx !== null"
      class="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-lg px-2.5 py-1.5 text-xs leading-relaxed text-white"
      style="background: rgba(15, 23, 42, 0.88); top: 4px"
      :style="{ left: tipLeft + 'px' }"
    >
      <b>{{ labels[hoverIdx] }}</b>
      <template v-for="(sr, si) in series" :key="sr.name">
        <br />
        <span :style="{ color: color(si) }">■</span>
        {{ sr.name }} — <b>{{ sr.values[hoverIdx] }}</b>
      </template>
    </div>
    <div class="mt-1.5 flex gap-3 text-[11px]" style="color: var(--ink-soft)">
      <span v-for="(sr, si) in series" :key="sr.name">
        <i
          class="me-1 inline-block size-[9px] rounded-[3px] align-[-1px]"
          :style="{ background: color(si) }"
        />{{ sr.name }} · {{ sr.values[sr.values.length - 1] }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

const props = defineProps<{
  // Fixed-order palette indices per series (dataviz rule: color follows the
  // entity, never its rank), values = one number per label.
  series: { name: string; colorIndex: number; values: number[] }[];
  labels: string[];
  night?: boolean;
}>();

const W = 260;
const H = 120;
const PADB = 10;

// Validated against both surfaces (six-checks script): the night violet is a
// step lighter so it clears the dark surface's contrast floor.
const PALETTE_LIGHT = ["#0891b2", "#e11d48", "#7c3aed"];
const PALETTE_NIGHT = ["#0891b2", "#e11d48", "#8b5cf6"];
const color = (si: number) => {
  const pal = props.night ? PALETTE_NIGHT : PALETTE_LIGHT;
  return pal[props.series[si].colorIndex % pal.length];
};

const maxV = computed(
  () => Math.max(1, ...props.series.flatMap((s) => s.values)) * 1.2
);

// Catmull-Rom sample of the weekly trend at fx ∈ [0,1].
function trendY(vals: number[], fx: number): number {
  const n = vals.length - 1;
  if (n < 1) return H - PADB;
  const x = fx * n;
  const i = Math.max(0, Math.min(n - 1, Math.floor(x)));
  const t = x - i;
  const p0 = vals[Math.max(0, i - 1)];
  const p1 = vals[i];
  const p2 = vals[i + 1];
  const p3 = vals[Math.min(n, i + 2)];
  const v =
    0.5 *
    (2 * p1 +
      (-p0 + p2) * t +
      (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
      (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t);
  return H - PADB - (v / maxV.value) * (H - 26);
}

const paths = ref<{ area: string; crest: string }[]>([]);

function draw(phase: number) {
  paths.value = props.series.map((sr, si) => {
    const amp = 2.4 + si * 0.5;
    const lam = 110 + si * 30;
    const speed = 1 + si * 0.15;
    let d = "";
    for (let px = 0; px <= W; px += 4) {
      const y =
        trendY(sr.values, px / W) +
        amp * Math.sin((px / lam) * 2 * Math.PI - phase * speed);
      d += (px ? " L" : "M") + px + " " + y.toFixed(1);
    }
    return { area: d + ` L ${W} ${H} L 0 ${H} Z`, crest: d };
  });
}

// One slow ambient roll (ts/3800 ≈ a phase turn per ~24s). No explicit
// hidden-tab pause: Chrome already stops rAF in hidden tabs, and gating the
// draw on document.hidden left the FIRST frame blank when a page mounted
// unfocused. Reduced-motion gets a single becalmed frame.
const REDUCED =
  typeof matchMedia !== "undefined" &&
  matchMedia("(prefers-reduced-motion: reduce)").matches;
let raf = 0;
function tide(ts: number) {
  draw(ts / 3800);
  raf = requestAnimationFrame(tide);
}
onMounted(() => {
  draw(1.3);
  if (!REDUCED) raf = requestAnimationFrame(tide);
});
onBeforeUnmount(() => cancelAnimationFrame(raf));

// Crosshair + tooltip: nearest week under the cursor.
const mount = ref<HTMLElement | null>(null);
const svg = ref<SVGSVGElement | null>(null);
const hoverIdx = ref<number | null>(null);
const tipLeft = ref(0);
const hoverX = computed(() =>
  hoverIdx.value === null
    ? 0
    : (hoverIdx.value / (props.labels.length - 1)) * W
);
function onMove(e: MouseEvent) {
  const r = svg.value?.getBoundingClientRect();
  if (!r || r.width === 0) return;
  const fx = (e.clientX - r.left) / r.width;
  const wi = Math.max(
    0,
    Math.min(props.labels.length - 1, Math.round(fx * (props.labels.length - 1)))
  );
  hoverIdx.value = wi;
  tipLeft.value = (wi / (props.labels.length - 1)) * r.width;
}
function onLeave() {
  hoverIdx.value = null;
}
</script>
