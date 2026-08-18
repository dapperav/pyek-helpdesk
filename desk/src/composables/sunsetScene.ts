// Sunset Shift: one component look, four token sets picked by the local
// clock (Mark's R5 pick, 2026-08-15; desktop joined 2026-08-18). This is THE
// home of the palettes — MobileHome and PyekHome both read them from here so
// a palette tweak can never leave the two screens on different skies.
// Windows (site-local): dawn 5-9, day 9-17, golden 17-20:30, night 20:30-5.
// ?scene=dawn|day|golden|night overrides the clock for testing (and is the
// hook for the future manual override in the menu).
import { __ } from "@/translation";
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute } from "vue-router";

const SCENES: Record<string, any> = {
  dawn: {
    pageBg: "#fcfbf8",
    heroBg:
      "linear-gradient(175deg, #1d2c52 0%, #46598f 42%, #a9a3c4 72%, #f2d7a4 100%)",
    waveHighlight: "rgba(255,244,214,0.5)",
    waterA: "#d3e6f5",
    waterB: "#a3c4e3",
    poolBg: "#ffffff",
    poolBorder: "1px solid #e5e4ef",
    poolShadow: "0 4px 14px rgba(60,70,120,0.07)",
    inkStrong: "#2c3352",
    inkName: "#333c5e",
    inkCount: "#4a5f96",
    inkSoft: "#6a7194",
    inkFaint: "#9aa1c0",
    seclabel: "#8087a8",
    whoBg: "linear-gradient(180deg, #e8ecfa, #d4dcf2)",
    whoInk: "#4a5f96",
    chipWarn: "#ffd9de",
    chipMe: "#cfe3ff",
    chipDone: "#d8f5c9",
    dateSuffix: __("first light"),
    inboxLabel: __("Overnight arrivals"),
    deep: "#2e3f66",
  },
  day: {
    pageBg: "#fbfdff",
    heroBg:
      "radial-gradient(120% 90% at 85% -10%, rgba(103,232,249,0.28) 0%, rgba(103,232,249,0) 55%), linear-gradient(175deg, #0c1830 0%, #123a66 58%, #0f6a94 100%)",
    waveHighlight: "rgba(255,255,255,0.35)",
    waterA: "#a8e9f7",
    waterB: "#55cdec",
    poolBg: "#ffffff",
    poolBorder: "1px solid #dbe7f0",
    poolShadow: "0 4px 14px rgba(18,54,94,0.07)",
    inkStrong: "#12365e",
    inkName: "#12365e",
    inkCount: "#0b6e8f",
    inkSoft: "#48708f",
    inkFaint: "#7d9ab5",
    seclabel: "#6889a8",
    whoBg: "linear-gradient(180deg, #e0f6ff, #bfeefb)",
    whoInk: "#0b6e8f",
    chipWarn: "#fda4af",
    chipMe: "#a5f3fc",
    chipDone: "#86efac",
    glowWarn: "0 2px 16px rgba(253,164,175,0.55)",
    glowDone: "0 2px 16px rgba(134,239,172,0.4)",
    deep: "#073a52",
  },
  golden: {
    pageBg: "#fdfbf7",
    heroBg:
      "linear-gradient(175deg, #2b1c4e 0%, #7a2d52 45%, #d96f4e 78%, #f2a65a 100%)",
    waveHighlight: "rgba(255,220,160,0.45)",
    waterA: "#ffd9a8",
    waterB: "#f79e63",
    poolBg: "#ffffff",
    poolBorder: "1px solid #f0e2cf",
    poolShadow: "0 4px 14px rgba(120,70,30,0.08)",
    inkStrong: "#4a3320",
    inkName: "#5c3a24",
    inkCount: "#b25b2e",
    inkSoft: "#8a6a45",
    inkFaint: "#b39267",
    seclabel: "#a1794f",
    whoBg: "linear-gradient(180deg, #ffe9cf, #ffd4a3)",
    whoInk: "#a15c2e",
    chipWarn: "#ffd0c2",
    chipMe: "#ffe4b8",
    chipDone: "#d8f5c9",
    dateSuffix: __("golden hour"),
    deep: "#8a4517",
  },
  night: {
    pageBg: "linear-gradient(180deg, #081226 0%, #0b1e3c 50%, #0c2c4e 100%)",
    heroBg: "transparent",
    waterA: "rgba(103,232,249,0.35)",
    waterB: "rgba(44,180,221,0.6)",
    waterGlow: "0 -6px 24px rgba(103,232,249,0.35)",
    poolBg: "rgba(255,255,255,0.04)",
    poolBorder: "1px solid rgba(103,232,249,0.22)",
    poolShadow: "none",
    inkStrong: "#eaf6ff",
    inkName: "#e6fbff",
    inkCount: "#67e8f9",
    countGlow: "0 0 16px rgba(103,232,249,0.7)",
    inkSoft: "rgba(255,255,255,0.6)",
    inkFaint: "rgba(255,255,255,0.4)",
    seclabel: "rgba(255,255,255,0.4)",
    whoBg: "rgba(103,232,249,0.18)",
    whoInk: "#67e8f9",
    cardBg: "rgba(255,255,255,0.05)",
    cardBorder: "1px solid rgba(255,255,255,0.12)",
    chipWarn: "#fda4af",
    chipMe: "#a5f3fc",
    chipDone: "#86efac",
    glowWarn: "0 0 18px rgba(251,113,133,0.8)",
    glowDone: "0 0 18px rgba(134,239,172,0.6)",
    dateSuffix: __("quiet hours on · urgent only"),
    deep: "#02101f",
  },
};

export { SCENES };

export function useSunsetScene() {
  const route = useRoute();

  // Re-evaluate every minute so an open screen crosses scene boundaries live.
  const now = ref(new Date());
  let clock: ReturnType<typeof setInterval> | null = null;
  onMounted(() => {
    clock = setInterval(() => (now.value = new Date()), 60_000);
  });
  onUnmounted(() => {
    if (clock) clearInterval(clock);
  });

  const sceneKey = computed<string>(() => {
    const forced = route.query.scene as string;
    if (forced && SCENES[forced]) return forced;
    const h = now.value.getHours() + now.value.getMinutes() / 60;
    if (h >= 5 && h < 9) return "dawn";
    if (h >= 9 && h < 17) return "day";
    if (h >= 17 && h < 20.5) return "golden";
    return "night";
  });
  const scene = computed(() => SCENES[sceneKey.value]);

  const sceneVars = computed(() => ({
    "--page-bg": scene.value.pageBg,
    "--hero-bg": scene.value.heroBg,
    "--water-a": scene.value.waterA,
    "--water-b": scene.value.waterB,
    "--water-glow": scene.value.waterGlow || "none",
    "--pool-bg": scene.value.poolBg,
    "--pool-border": scene.value.poolBorder,
    "--pool-shadow": scene.value.poolShadow,
    "--ink-strong": scene.value.inkStrong,
    "--ink-name": scene.value.inkName,
    "--ink-count": scene.value.inkCount,
    "--count-glow": scene.value.countGlow || "none",
    "--ink-soft": scene.value.inkSoft,
    "--ink-faint": scene.value.inkFaint,
    "--seclabel": scene.value.seclabel,
    "--who-bg": scene.value.whoBg,
    "--who-ink": scene.value.whoInk,
    "--card-bg": scene.value.cardBg || scene.value.poolBg,
    "--card-border": scene.value.cardBorder || scene.value.poolBorder,
    // What deep water fades to (depth-darkening pools, Mark 2026-08-18)
    "--deep": scene.value.deep || "#073a52",
  }));

  const greeting = computed(() => {
    switch (sceneKey.value) {
      case "dawn":
        return __("Good morning");
      case "day":
        return now.value.getHours() < 12
          ? __("Good morning")
          : __("Good afternoon");
      case "golden":
        return __("Good evening");
      default:
        return __("Good night");
    }
  });

  return { sceneKey, scene, sceneVars, greeting };
}
