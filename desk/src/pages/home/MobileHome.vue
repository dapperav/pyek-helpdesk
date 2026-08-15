<template>
  <!-- PYEK IT: phone-first home, "Sunset Shift" (Mark's pick, 2026-08-15).
       One structure, four scenes swapped by the local clock: Dawn Patrol
       (5-9a), High Sun (9a-5p), Golden Hour (5-8:30p), Night Swim (8:30p-5a).
       Scene = a token set (gradients, water, ink) + three content nuances:
       dawn renames the inbox to "Overnight arrivals", night flips the greeting
       and notes quiet hours. Structure is locked from the mockup rounds:
       hero + glass chips (the ONLY numbers), three clean pools (name / count /
       waterline — deliberately NO per-queue waiting indicator), "Just came in".
       ?scene=dawn|day|golden|night overrides the clock for testing. -->
  <div
    class="scene-root flex h-full flex-col"
    :class="`scene-${sceneKey}`"
    :style="sceneVars"
  >
    <PullToRefreshIndicator
      :pull="pull"
      :refreshing="refreshing"
      :threshold="threshold"
    />
    <LayoutHeader>
      <template #left-header>
        <div class="text-lg-medium text-ink-gray-9">{{ __("Home") }}</div>
      </template>
      <template #right-header>
        <Button
          :label="__('Refresh')"
          variant="subtle"
          icon-left="lucide-refresh-ccw"
          :loading="tickets.loading"
          @click="refreshAll"
        />
      </template>
    </LayoutHeader>

    <div class="min-h-0 flex-1 overflow-y-auto" style="background: var(--page-bg)">
      <!-- HERO -->
      <div class="hero">
        <!-- scene decor -->
        <div v-if="sceneKey === 'dawn'" class="sun-dawn" aria-hidden="true" />
        <div v-if="sceneKey === 'golden'" class="sun-golden" aria-hidden="true" />
        <template v-if="sceneKey === 'night'">
          <div class="moon" aria-hidden="true" />
          <span class="star" style="left: 9%; top: 18px" aria-hidden="true" />
          <span class="star" style="left: 26%; top: 44px; opacity: 0.45" aria-hidden="true" />
          <span class="star" style="right: 30%; top: 30px; opacity: 0.55" aria-hidden="true" />
          <span class="star" style="left: 52%; top: 12px; opacity: 0.4" aria-hidden="true" />
        </template>

        <div class="relative px-[18px] pt-3">
          <h1 class="text-[22px] font-normal text-white">
            {{ greeting }}, <b class="font-bold">{{ firstName }}</b>
          </h1>
          <p class="mt-0.5 text-xs" style="color: rgba(255, 255, 255, 0.55)">
            {{ todayLabel }}<template v-if="scene.dateSuffix"> &middot; {{ scene.dateSuffix }}</template>
          </p>
          <div class="mb-1 mt-3.5 flex gap-2">
            <button class="chip" @click="openView('Awaiting first reply')">
              <span class="chip-l" :style="{ color: scene.chipWarn }">{{ __("Treading water") }}</span>
              <span class="chip-v" :style="scene.glowWarn ? { textShadow: scene.glowWarn } : {}">
                {{ homeStats.data?.awaiting_first_reply ?? 0 }}
              </span>
            </button>
            <button class="chip" @click="openView('My Open Tickets')">
              <span class="chip-l" :style="{ color: scene.chipMe }">{{ __("My open") }}</span>
              <span class="chip-v">{{ homeStats.data?.my_open ?? 0 }}</span>
            </button>
            <div class="chip">
              <span class="chip-l" :style="{ color: scene.chipDone }">{{ __("Resolved today") }}</span>
              <span class="chip-v" :style="scene.glowDone ? { textShadow: scene.glowDone } : {}">
                {{ homeStats.data?.resolved_today ?? 0 }}
              </span>
            </div>
          </div>
        </div>

        <!-- the break: wave into the page (light scenes) / lane rope (night) -->
        <div v-if="sceneKey !== 'night'" class="overflow-hidden">
          <svg class="waveedge" viewBox="0 0 750 44" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <path
              d="M0 26 Q 47 8 94 22 T 188 20 T 282 24 T 375 16 T 470 22 T 564 18 T 658 24 T 750 16 L 750 44 L 0 44 Z"
              :fill="scene.waveHighlight"
            />
            <path
              d="M0 34 Q 47 18 94 30 T 188 28 T 282 32 T 375 26 T 470 32 T 564 28 T 658 32 T 750 26 L 750 44 L 0 44 Z"
              :fill="scene.pageBg"
            />
          </svg>
        </div>
        <div v-else class="flex justify-center gap-1 pb-3 pt-1" aria-hidden="true">
          <span
            v-for="i in 7"
            :key="i"
            class="h-1.5 w-3.5 rounded"
            :style="{ background: i % 2 ? '#ef4444' : '#e8f2ff' }"
          />
        </div>
      </div>

      <!-- BODY -->
      <div class="flex flex-col gap-4 p-4">
        <div>
          <p class="seclabel">{{ __("Queues") }}</p>
          <div class="grid grid-cols-3 gap-2.5">
            <button
              v-for="q in queuePools"
              :key="q.key"
              class="pool"
              @click="openView(q.view)"
            >
              <span class="water" :style="{ height: q.level }" />
              <span class="meta">
                <span class="pool-name">{{ q.label }}</span>
                <span class="pool-count num">{{ q.value }}</span>
              </span>
            </button>
          </div>
        </div>

        <div v-if="latest.length">
          <p class="seclabel">{{ scene.inboxLabel || __("Just came in") }}</p>
          <div class="flex flex-col gap-2">
            <button
              v-for="t in latest"
              :key="t.name"
              class="jcard"
              @click="openTicket(t.name)"
            >
              <span class="who">{{ initials(t.raised_by) }}</span>
              <span class="min-w-0 flex-1 text-left">
                <span class="flex items-baseline justify-between gap-2">
                  <span class="truncate text-sm font-semibold" style="color: var(--ink-strong)">
                    {{ t.subject }}
                  </span>
                  <span class="shrink-0 text-[11px]" style="color: var(--ink-faint)">
                    {{ prettyDate(t.creation) }}
                  </span>
                </span>
                <span
                  v-if="t.pyek_summary"
                  class="summary mt-0.5 text-xs leading-relaxed"
                  style="color: var(--ink-soft)"
                >
                  {{ t.pyek_summary }}
                </span>
                <span v-if="queueTag(t)" class="mt-1.5 block">
                  <span class="qtag" :class="queueTag(t).cls">{{ queueTag(t).label }}</span>
                </span>
              </span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- SOS life ring: surfaces (bobbing) only when the site is objectively
         slammed — awaiting-first-reply at/above the server's threshold and no
         cooldown running. Fixed above the glass nav. -->
    <button
      v-if="showBuoy"
      class="sos"
      :aria-label="__('Send SOS to the team')"
      @click="showSosConfirm = true"
    >
      <svg width="40" height="40" viewBox="0 0 40 40" aria-hidden="true">
        <circle cx="20" cy="20" r="16" fill="none" stroke="#dc2626" stroke-width="9" />
        <circle
          cx="20" cy="20" r="16" fill="none" stroke="#ffffff" stroke-width="9"
          stroke-dasharray="12.56 12.56" stroke-dashoffset="6.28"
        />
        <circle cx="20" cy="20" r="16" fill="none" stroke="#94a3b8" stroke-width="1" />
        <circle cx="20" cy="20" r="7.5" fill="#fff" stroke="#94a3b8" stroke-width="1" />
      </svg>
    </button>

    <!-- SOS confirm: glass card, shows the exact push before it goes out. -->
    <div v-if="showSosConfirm" class="sos-confirm" @click.self="showSosConfirm = false">
      <div class="sos-card">
        <h3 class="mb-1 mt-2 text-[17px] font-bold text-ink-gray-9">
          {{ __("All hands?") }}
        </h3>
        <p class="mb-3 text-xs leading-relaxed text-ink-gray-6">
          {{ __("Every agent gets a push right now, quiet hours included. One SOS per 30 minutes.") }}
        </p>
        <div class="mb-3.5 rounded-[10px] bg-surface-gray-2 px-3 py-2 text-left text-xs text-ink-gray-8">
          <b class="block">🚨 {{ __("SOS from") }} {{ firstName }}</b>
          {{ homeStats.data?.awaiting_first_reply ?? 0 }}
          {{ __("tickets waiting on a first reply — queues are overflowing. Jump in if you can.") }}
        </div>
        <div class="flex gap-2">
          <Button class="flex-1" :label="__('Not yet')" @click="showSosConfirm = false" />
          <Button
            class="flex-1"
            variant="solid"
            theme="red"
            :label="__('Send SOS')"
            :loading="sosSending"
            @click="fireSos"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { LayoutHeader } from "@/components";
import PullToRefreshIndicator from "@/components/PullToRefreshIndicator.vue";
import { usePullToRefresh } from "@/composables/pullToRefresh";
import { useView } from "@/composables/useView";
import { useAuthStore } from "@/stores/auth";
import { __ } from "@/translation";
import { prettyDate } from "@/utils";
import { Button, createResource, dayjs, toast, usePageMeta } from "frappe-ui";
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

usePageMeta(() => ({ title: __("Home") }));

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();

// ---------------------------------------------------------------- scenes ----
// Each scene is a pure token set; the template never branches on colors.
// Windows (site-local): dawn 5-9, day 9-17, golden 17-20:30, night 20:30-5.
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
  },
};

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
}));

const firstName = computed(
  () => (auth.userName || "there").toString().split(" ")[0]
);
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
const todayLabel = computed(() => dayjs().format("dddd, MMMM D"));

// ------------------------------------------------------------------ data ----
const homeStats = createResource({
  url: "helpdesk.api.pyek_home.get_home_stats",
  auto: true,
});

const tickets = createResource({
  url: "frappe.client.get_list",
  makeParams: () => ({
    doctype: "HD Ticket",
    fields: [
      "name",
      "status_category",
      "agent_group",
      "email_account",
      "raised_by",
      "_assign",
    ],
    limit_page_length: 0,
  }),
  auto: true,
});
const rows = computed<any[]>(() => tickets.data || []);

// Separate small fetch: summaries are long text, so pulling them for EVERY
// ticket would bloat the count query for four rendered rows.
const recent = createResource({
  url: "frappe.client.get_list",
  makeParams: () => ({
    doctype: "HD Ticket",
    fields: [
      "name",
      "subject",
      "pyek_summary",
      "raised_by",
      "creation",
      "first_responded_on",
      "agent_group",
      "email_account",
    ],
    filters: { status_category: ["in", ["Open", "Paused"]] },
    order_by: "creation desc",
    limit_page_length: 30,
  }),
  auto: true,
});

const latest = computed(() => {
  const bots = new Set(homeStats.data?.bot_senders || []);
  return (recent.data || [])
    .filter(
      (t: any) =>
        !bots.has((t.raised_by || "").toLowerCase()) && !t.first_responded_on
    )
    .slice(0, 4);
});

function refreshAll() {
  homeStats.reload();
  recent.reload();
  return tickets.reload();
}
const { pull, refreshing, threshold } = usePullToRefresh(refreshAll);

const notResolved = (t: any) => t.status_category !== "Resolved";
function assignedToMe(t: any): boolean {
  try {
    return (JSON.parse(t._assign || "[]") as string[]).includes(auth.user);
  } catch {
    return false;
  }
}

const counts = computed(() => {
  const r = rows.value.filter(notResolved);
  return {
    pos: r.filter((t) => t.agent_group === "POS Support").length,
    it: r.filter((t) => t.email_account === "IT Support").length,
    mine: r.filter(assignedToMe).length,
  };
});

// Pool depth = queue depth: count/10 of the card, capped. Wrike is off Home
// (everything Wrike lands in the POS box; the saved view stays in the menu).
function level(n: number): string {
  return n > 0 ? Math.min(95, Math.max(10, n * 10)) + "%" : "0%";
}
const queuePools = computed(() => [
  { key: "pos", label: __("POS"), value: counts.value.pos, level: level(counts.value.pos), view: "POS Tickets" },
  { key: "it", label: __("IT"), value: counts.value.it, level: level(counts.value.it), view: "IT Tickets" },
  { key: "mine", label: __("Mine"), value: counts.value.mine, level: level(counts.value.mine), view: "My Open Tickets" },
]);

function initials(email: string): string {
  return (email || "?")
    .split("@")[0]
    .split(/[._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}

function queueTag(t: any): { label: string; cls: string } | null {
  if (t.agent_group === "POS Support") return { label: "POS", cls: "qtag-pos" };
  if (t.email_account === "IT Support") return { label: "IT", cls: "qtag-it" };
  return null;
}

// ------------------------------------------------------------------- SOS ----
const sosState = createResource({
  url: "helpdesk.api.pyek_sos.get_sos_state",
  auto: true,
});
const showSosConfirm = ref(false);
const sosSending = ref(false);

const showBuoy = computed(() => {
  const waiting = homeStats.data?.awaiting_first_reply ?? 0;
  const threshold = sosState.data?.threshold ?? 999;
  const cooling = (sosState.data?.cooldown_remaining ?? 0) > 0;
  return waiting >= threshold && !cooling;
});

const sosSend = createResource({ url: "helpdesk.api.pyek_sos.send_sos" });
async function fireSos() {
  if (sosSending.value) return;
  sosSending.value = true;
  try {
    const r = await sosSend.submit();
    toast.success(
      __("🚨 SOS sent — push delivered to {0} agents", String(r.sent_to))
    );
    showSosConfirm.value = false;
    sosState.reload();
  } catch (e: any) {
    const msg = e?.messages?.join(", ") || e?.message || __("SOS failed");
    toast.error(msg);
  } finally {
    sosSending.value = false;
  }
}

const { publicViews } = useView();
function openView(label: string) {
  const v = (publicViews.value || []).find((x: any) => x.label === label);
  router.push({ name: "TicketsAgent", query: v ? { view: v.name } : {} });
}
function openTicket(name: string) {
  router.push({ name: "TicketAgent", params: { ticketId: name } });
}
</script>

<style scoped>
.hero {
  position: relative;
  overflow: hidden;
  background: var(--hero-bg);
}

/* --- scene decor --- */
.sun-dawn {
  position: absolute;
  left: 22%;
  bottom: -12px;
  width: 54px;
  height: 54px;
  border-radius: 50%;
  background: radial-gradient(
    circle,
    rgba(255, 244, 214, 0.95) 0%,
    rgba(255, 236, 180, 0.55) 55%,
    rgba(255, 236, 180, 0) 100%
  );
}
.sun-golden {
  position: absolute;
  left: 50%;
  bottom: -14px;
  width: 76px;
  height: 76px;
  margin-left: -38px;
  border-radius: 50%;
  background: radial-gradient(
    circle,
    #ffe9b0 0%,
    #ffcf7a 60%,
    rgba(255, 207, 122, 0) 100%
  );
}
.moon {
  position: absolute;
  right: 44px;
  top: 8px;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  box-shadow: 7px -3px 0 0 #e8f2ff;
  transform: rotate(20deg);
}
.star {
  position: absolute;
  width: 2px;
  height: 2px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.7);
}

/* --- glass chips (Apple material: blur + saturate) --- */
.chip {
  -webkit-backdrop-filter: blur(14px) saturate(1.7);
  backdrop-filter: blur(14px) saturate(1.7);
  background: rgba(255, 255, 255, 0.13);
  border: 1px solid rgba(255, 255, 255, 0.22);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.28);
  border-radius: 14px;
  padding: 10px 13px;
  flex: 1;
  min-width: 0;
  text-align: left;
}
.chip-l {
  display: block;
  font-size: 11.5px;
  line-height: 1.3;
}
.chip-v {
  display: block;
  margin-top: 1px;
  font-size: 24px;
  font-weight: 700;
  color: #fff;
  font-variant-numeric: tabular-nums;
}

.waveedge {
  display: block;
  margin-bottom: -1px;
  width: 200%;
  animation: drift 9s ease-in-out infinite alternate;
}
@keyframes drift {
  from {
    transform: translateX(0);
  }
  to {
    transform: translateX(-12%);
  }
}

.seclabel {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--seclabel);
}
.seclabel::before {
  content: "";
  width: 14px;
  height: 3px;
  border-radius: 2px;
  background: currentColor;
  opacity: 0.7;
}

/* --- pools --- */
.pool {
  position: relative;
  overflow: hidden;
  border-radius: 16px;
  height: 96px;
  background: var(--pool-bg);
  border: var(--pool-border);
  box-shadow: var(--pool-shadow);
  text-align: left;
}
.pool:active {
  opacity: 0.8;
}
.water {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(180deg, var(--water-a), var(--water-b));
  box-shadow: var(--water-glow);
  transition: height 1.1s cubic-bezier(0.22, 1, 0.36, 1);
}
.water::before {
  /* sun glint on the surface */
  content: "";
  position: absolute;
  top: 3px;
  left: 10%;
  right: 45%;
  height: 2px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.75);
}
.meta {
  position: absolute;
  inset: 10px 11px;
  display: flex;
  flex-direction: column;
}
.pool-name {
  font-size: 13px;
  font-weight: 650;
  color: var(--ink-name);
}
.pool-count {
  font-size: 25px;
  font-weight: 750;
  color: var(--ink-count);
  text-shadow: var(--count-glow);
}
.num {
  font-variant-numeric: tabular-nums;
}

/* --- just came in --- */
.jcard {
  display: flex;
  gap: 10px;
  border-radius: 14px;
  padding: 11px 13px;
  background: var(--card-bg);
  border: var(--card-border);
  box-shadow: var(--pool-shadow);
}
.jcard:active {
  opacity: 0.8;
}
.who {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 700;
  background: var(--who-bg);
  color: var(--who-ink);
}
.summary {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.qtag {
  display: inline-block;
  border-radius: 5px;
  padding: 1.5px 6px;
  font-size: 9.5px;
  font-weight: 750;
  letter-spacing: 0.04em;
}
.qtag-pos {
  background: #e0edff;
  color: #1d4ed8;
}
.qtag-it {
  background: #d9f5ee;
  color: #047857;
}
.scene-night .qtag-pos {
  background: rgba(96, 165, 250, 0.2);
  color: #93c5fd;
}
.scene-night .qtag-it {
  background: rgba(52, 211, 153, 0.18);
  color: #6ee7b7;
}

/* --- SOS life ring --- */
.sos {
  position: fixed;
  right: 14px;
  bottom: calc(var(--pyek-nav-h, 62px) + 14px);
  z-index: 30;
  width: 56px;
  height: 56px;
  border-radius: 9999px;
  background: #fff;
  box-shadow: 0 8px 22px rgba(185, 28, 28, 0.35);
  display: grid;
  place-items: center;
  animation: bob 2.6s ease-in-out infinite;
}
@keyframes bob {
  0%,
  100% {
    transform: translateY(0) rotate(-4deg);
  }
  50% {
    transform: translateY(-7px) rotate(4deg);
  }
}
.sos-confirm {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: grid;
  place-items: center;
  background: rgba(8, 16, 34, 0.4);
  -webkit-backdrop-filter: blur(6px);
  backdrop-filter: blur(6px);
}
.sos-card {
  width: 82%;
  max-width: 340px;
  border-radius: 20px;
  padding: 18px;
  text-align: center;
  background: rgba(255, 255, 255, 0.9);
  -webkit-backdrop-filter: blur(20px) saturate(1.6);
  backdrop-filter: blur(20px) saturate(1.6);
  border: 1px solid rgba(255, 255, 255, 0.7);
  box-shadow: 0 18px 50px rgba(8, 16, 34, 0.35);
}

@media (prefers-reduced-motion: reduce) {
  .waveedge {
    animation: none;
  }
  .water {
    transition-duration: 0.01s;
  }
  .sos {
    animation: none;
  }
}
</style>
