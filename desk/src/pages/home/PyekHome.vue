<template>
  <!-- The ocean Home (Mark's round-2 picks, 2026-08-18, mocked through ten
       rounds): no header bar — the wave hero is the top of the page; the
       triage board (POS | IT | Mine columns) IS the navigation; analytics
       are rolling swells; Echo pops in as an easter egg. Scene tokens +
       clock shared with MobileHome via composables/sunsetScene.ts. -->
  <div
    class="flex h-full flex-col overflow-y-auto"
    :class="`scene-${sceneKey}`"
    :style="[sceneVars, { background: 'var(--page-bg)' }]"
  >
    <!-- HERO -->
    <div class="hero shrink-0">
      <div v-if="sceneKey === 'dawn'" class="sun-dawn" aria-hidden="true" />
      <div v-if="sceneKey === 'golden'" class="sun-golden" aria-hidden="true" />
      <template v-if="sceneKey === 'night'">
        <div class="moon" aria-hidden="true" />
        <span class="star" style="left: 9%; top: 22px" aria-hidden="true" />
        <span class="star" style="left: 26%; top: 52px; opacity: 0.45" aria-hidden="true" />
        <span class="star" style="right: 30%; top: 36px; opacity: 0.55" aria-hidden="true" />
        <span class="star" style="left: 52%; top: 16px; opacity: 0.4" aria-hidden="true" />
        <span class="star" style="right: 12%; top: 60px; opacity: 0.5" aria-hidden="true" />
      </template>

      <div class="relative mx-auto flex w-full max-w-[1500px] items-start gap-6 px-6 pb-2 pt-6">
        <div>
          <h1 class="text-[26px] font-normal text-white">
            {{ greeting }}, <b class="font-bold">{{ firstName }}</b>
          </h1>
          <p class="mt-0.5 text-xs" style="color: rgba(255, 255, 255, 0.55)">
            {{ todayLabel }}<template v-if="scene.dateSuffix"> &middot; {{ scene.dateSuffix }}</template>
            <span class="surfword">{{ surfWord }}</span>
          </p>
        </div>
        <div class="ms-auto flex gap-3">
          <button class="chip" @click="openViewByLabel('Awaiting first reply')">
            <span class="chip-l" :style="{ color: scene.chipWarn }">{{ __("Treading water") }}</span>
            <span class="chip-v" :style="scene.glowWarn ? { textShadow: scene.glowWarn } : {}">
              {{ homeStats.data?.awaiting_first_reply ?? 0 }}
            </span>
          </button>
          <button class="chip" @click="openViewByLabel('My Open Tickets')">
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

      <!-- Echo, the easter egg: rises from behind the wave crest a few times
           a shift, says something encouraging, slips back under. Never
           persistent, never over the chips. -->
      <div class="echo-break" :class="{ show: echoShown }" aria-live="polite">
        <div class="echo-bubble">{{ echoText }}</div>
        <img class="echo-avatar" :src="'/files/echo-finley.png'" alt="Echo" />
      </div>

      <div v-if="sceneKey !== 'night'" class="overflow-hidden">
        <svg class="waveedge" viewBox="0 0 750 44" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
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
    <div class="mx-auto flex w-full max-w-[1500px] flex-col gap-6 p-6">
      <!-- THE TRIAGE BOARD: one symmetric bucket per queue -->
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-3 lg:items-start">
        <div v-for="col in boardColumns" :key="col.key" class="flex flex-col gap-3">
          <button
            class="pool"
            :class="{ dropready: col.key === 'mine' && dragOverMine }"
            @click="openViewByLabel(col.view)"
            @dragover.prevent="col.key === 'mine' && (dragOverMine = true)"
            @dragleave="col.key === 'mine' && (dragOverMine = false)"
            @drop.prevent="col.key === 'mine' && onDropClaim($event)"
          >
            <span class="water" :style="waterStyle(col.count)">
              <svg class="surf" viewBox="0 0 300 12" preserveAspectRatio="none" aria-hidden="true">
                <path :d="SURF_PATH" fill="var(--water-a)" />
                <path :d="SURF_CREST" fill="none" stroke="rgba(255,255,255,0.75)" stroke-width="1.6" />
              </svg>
            </span>
            <span
              v-for="r in ripples[col.key]"
              :key="r"
              class="ripple"
              :style="{ top: `calc(100% - ${Math.min(95, Math.max(10, col.count * 10))}%)` }"
            />
            <!-- All-clear pop: fires once when the pool drains to zero, then
                 the empty pool rests quietly with its 0. -->
            <span class="clearmsg" :class="{ show: clearShown === col.key }">
              <img class="size-[30px] rounded-full border border-white/90 object-cover shadow" :src="'/files/echo-finley.png'" alt="Echo" />
              <span class="echo-bubble !m-0 text-[11px]">{{ __("All clear — nothing in the water.") }}</span>
            </span>
            <span class="meta">
              <span class="pool-name">{{ col.label }}</span>
              <span class="pool-count">{{ col.count }}</span>
            </span>
          </button>

          <div>
            <div class="flex items-baseline justify-between">
              <p class="seclabel">{{ scene.inboxLabel || __("Just came in") }}</p>
              <button class="viewall" @click="openViewByLabel(col.view)">
                {{ __("view all") }} &rarr;
              </button>
            </div>
            <div class="flex flex-col gap-2.5">
              <button
                v-for="t in col.items"
                :key="t.name"
                class="jcard"
                :draggable="col.key !== 'mine'"
                @dragstart="onDragStart($event, t)"
                @dragend="draggingTicket = null"
                @click="openTicket(t.name)"
              >
                <img
                  v-if="senderPhoto(t)"
                  :src="senderPhoto(t)"
                  class="who shrink-0 object-cover"
                  alt=""
                />
                <span v-else class="who">{{ initials(t.raised_by) }}</span>
                <span class="min-w-0 flex-1 text-left">
                  <span class="flex items-baseline justify-between gap-2">
                    <span class="truncate text-sm font-semibold" style="color: var(--ink-strong)">
                      {{ t.subject }}
                    </span>
                    <span class="shrink-0 text-[11px]" style="color: var(--ink-faint)">
                      {{ prettyDate(t.last_arrival || t.creation) }}
                    </span>
                  </span>
                  <span
                    v-if="t.pyek_summary"
                    class="summary mt-0.5 text-xs leading-relaxed"
                    style="color: var(--ink-soft)"
                  >
                    {{ t.pyek_summary }}
                  </span>
                  <span v-if="col.key === 'mine' && t.assigned_at" class="mt-1.5 block">
                    <span class="qtag qtag-it">{{ __("assigned to you") }}</span>
                  </span>
                </span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- MORE VIEWS: everything else, one click away, calm by default -->
      <div>
        <button class="more-toggle" @click="moreOpen = !moreOpen">
          <span class="chev" :class="{ open: moreOpen }">&#8250;</span>
          {{ __("More views") }}
        </button>
        <div v-if="moreOpen" class="mt-3 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <button
            v-for="v in moreViewCards"
            :key="v.name"
            class="pool sm"
            @click="v.onClick"
          >
            <span v-if="v.level" class="water" :style="waterStyle(v.count)">
              <svg class="surf" viewBox="0 0 300 12" preserveAspectRatio="none" aria-hidden="true">
                <path :d="SURF_PATH" fill="var(--water-a)" />
                <path :d="SURF_CREST" fill="none" stroke="rgba(255,255,255,0.75)" stroke-width="1.6" />
              </svg>
            </span>
            <span class="meta">
              <span class="pool-name">{{ v.label }}</span>
              <span class="pool-count" :class="!v.level && 'dry'">
                {{ v.count ?? "" }}
              </span>
              <span v-if="v.sub" class="text-[10px]" style="color: var(--ink-faint)">{{ v.sub }}</span>
            </span>
          </button>
        </div>
      </div>

      <!-- ANALYTICS: six weeks of swell -->
      <div>
        <p class="seclabel">{{ __("Analytics — six weeks of swell") }}</p>
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-4">
          <div v-for="ch in waveCharts" :key="ch.title" class="chart-card">
            <h3 class="mb-1.5 text-[12.5px] font-semibold" style="color: var(--ink-name)">
              {{ ch.title }}
            </h3>
            <WaveChart :series="ch.series" :labels="weekLabels" :night="sceneKey === 'night'" />
          </div>
        </div>
      </div>
    </div>

    <!-- SOS life ring (unchanged behavior; rings = people in the water) -->
    <button
      v-if="showBuoy"
      class="sos"
      :aria-label="__('Send SOS to the team')"
      @click="showSosConfirm = true"
    >
      <svg width="44" height="44" viewBox="0 0 40 40" aria-hidden="true">
        <circle cx="20" cy="20" r="16" fill="none" stroke="#dc2626" stroke-width="9" />
        <circle
          cx="20" cy="20" r="16" fill="none" stroke="#ffffff" stroke-width="9"
          stroke-dasharray="12.56 12.56" stroke-dashoffset="6.28"
        />
        <circle cx="20" cy="20" r="16" fill="none" stroke="#94a3b8" stroke-width="1" />
        <circle cx="20" cy="20" r="7.5" fill="#fff" stroke="#94a3b8" stroke-width="1" />
      </svg>
    </button>

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
import WaveChart from "@/components/home/WaveChart.vue";
import { selfAssignTicket } from "@/composables/selfAssign";
import { useSunsetScene } from "@/composables/sunsetScene";
import { useView } from "@/composables/useView";
import { useAuthStore } from "@/stores/auth";
import { useUserStore } from "@/stores/user";
import { __ } from "@/translation";
import { prettyDate } from "@/utils";
import { Button, createResource, dayjs, toast, usePageMeta } from "frappe-ui";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

usePageMeta(() => ({ title: __("Home") }));

const auth = useAuthStore();
const firstName = computed(
  () => (auth.userName || "there").toString().split(" ")[0]
);

const { sceneKey, scene, sceneVars, greeting } = useSunsetScene();
const todayLabel = computed(() => dayjs().format("dddd, MMMM D"));

// Two identical humps per 150 units → the ribbon loops seamlessly at -50%.
const SURF_PATH =
  "M0 9 Q 18.75 3 37.5 9 T 75 9 T 112.5 9 T 150 9 T 187.5 9 T 225 9 T 262.5 9 T 300 9 L 300 12 L 0 12 Z";
const SURF_CREST =
  "M0 9 Q 18.75 3 37.5 9 T 75 9 T 112.5 9 T 150 9 T 187.5 9 T 225 9 T 262.5 9 T 300 9";

// ------------------------------------------------------------------ data ----
const homeStats = createResource({
  url: "helpdesk.api.pyek_home.get_home_stats",
  auto: true,
});
const board = createResource({
  url: "helpdesk.api.pyek_home.get_home_board",
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
      "pyek_property",
      "raised_by",
      "resolution_date",
      "creation",
      "_assign",
    ],
    limit_page_length: 0,
  }),
  auto: true,
});
const rows = computed<any[]>(() => tickets.data || []);

// No header bar, no Refresh button (Mark, 2026-08-18): the numbers stay right
// on their own — reload whenever the window comes back into focus, plus a
// slow heartbeat while it stays open.
function refreshAll() {
  homeStats.reload();
  board.reload();
  tickets.reload();
}
let heartbeat: ReturnType<typeof setInterval> | null = null;
function onVisible() {
  if (!document.hidden) refreshAll();
}
onMounted(() => {
  document.addEventListener("visibilitychange", onVisible);
  heartbeat = setInterval(refreshAll, 180_000);
});
onBeforeUnmount(() => {
  document.removeEventListener("visibilitychange", onVisible);
  if (heartbeat) clearInterval(heartbeat);
  if (echoTimer) clearTimeout(echoTimer);
  if (echoHide) clearTimeout(echoHide);
  if (clearTimer) clearTimeout(clearTimer);
});

const botSenders = computed(
  () => new Set<string>(homeStats.data?.bot_senders || [])
);
const humanRows = computed(() =>
  rows.value.filter((t) => !botSenders.value.has((t.raised_by || "").toLowerCase()))
);

const router = useRouter();
const { publicViews, pinnedViews } = useView();
function openViewByLabel(label: string) {
  const all = [...(publicViews.value || []), ...(pinnedViews.value || [])];
  const v = all.find((x: any) => x.label === label);
  router.push({ name: "TicketsAgent", query: v ? { view: v.name } : {} });
}
function openTicket(name: string) {
  router.push({ name: "TicketAgent", params: { ticketId: name } });
}

// ---- Queue counts (same math as the phone pools) --------------------------
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

// Depth = darkness: the fuller the pool, the further its bottom fades toward
// the scene's abyss; thin water stays a little see-through.
function waterStyle(count: number) {
  const h = count > 0 ? Math.min(95, Math.max(10, count * 10)) : 0;
  const deep = Math.round(Math.min(80, h * 0.85));
  return {
    height: h + "%",
    background: `linear-gradient(180deg, var(--water-a), color-mix(in oklab, var(--water-b) ${100 - deep}%, var(--deep)))`,
    opacity: h <= 35 && h > 0 ? "0.8" : "1",
  };
}

// ---- The board columns -----------------------------------------------------
const boardColumns = computed(() => [
  {
    key: "pos",
    label: __("POS"),
    view: "POS Tickets",
    count: counts.value.pos,
    items: board.data?.pos || [],
  },
  {
    key: "it",
    label: __("IT"),
    view: "IT Tickets",
    count: counts.value.it,
    items: board.data?.it || [],
  },
  {
    key: "mine",
    label: __("Mine"),
    view: "My Open Tickets",
    count: counts.value.mine,
    items: board.data?.mine || [],
  },
]);

// ---- More views: everything else as small pools ---------------------------
// Counts only where the client can compute them honestly from the list rows;
// a view whose filter lives server-side renders calm with just its name.
const moreViewCards = computed(() => {
  const HERO = new Set(["POS Tickets", "IT Tickets", "My Open Tickets"]);
  const open = rows.value.filter(
    (t) => t.status_category === "Open" || t.status_category === "Paused"
  );
  const resolvers: Record<string, () => { count: number; level: boolean; sub?: string }> = {
    "Open Tickets": () => ({ count: open.length, level: true }),
    "Awaiting first reply": () => ({
      count: homeStats.data?.awaiting_first_reply ?? 0,
      level: true,
    }),
    "All Tickets": () => ({ count: rows.value.length, level: false }),
  };
  const cards = (publicViews.value || [])
    .filter((v: any) => !HERO.has(v.label))
    .map((v: any) => {
      const r = resolvers[v.label]?.();
      return {
        name: v.name,
        label: v.label,
        onClick: v.onClick,
        count: r?.count,
        level: !!r?.level && (r?.count ?? 0) > 0,
        sub: r?.sub,
      };
    });
  cards.push({
    name: "kb",
    label: __("Knowledge Base"),
    onClick: () => router.push({ name: "AgentKnowledgeBase" }),
    count: board.data?.kb_articles,
    level: false,
    sub: __("articles"),
  });
  return cards;
});
const moreOpen = ref(false);

// ---- Surf report -----------------------------------------------------------
const surfWord = computed(() => {
  const treading = homeStats.data?.awaiting_first_reply ?? 0;
  return treading >= 8 ? "HEAVY" : treading >= 3 ? "CHOPPY" : "GLASSY";
});

// ---- Sender photos (contact image first, else User image) ------------------
const { getUser } = useUserStore();
const contactImages = ref<Record<string, string>>({});
const contactImgFetch = createResource({
  url: "frappe.client.get_list",
  onSuccess(imgRows: any[]) {
    const map: Record<string, string> = {};
    for (const r of imgRows || []) if (r.image) map[r.name] = r.image;
    contactImages.value = map;
  },
});
watch(
  () => board.data,
  (data: any) => {
    const all = [...(data?.pos || []), ...(data?.it || []), ...(data?.mine || [])];
    const names = [...new Set(all.map((t: any) => t.contact).filter(Boolean))];
    if (!names.length) return;
    contactImgFetch.submit({
      doctype: "Contact",
      filters: { name: ["in", names] },
      fields: ["name", "image"],
      limit_page_length: 0,
    });
  }
);
function senderPhoto(t: any): string {
  return (
    contactImages.value[t.contact] || getUser(t.raised_by)?.user_image || ""
  );
}
function initials(email: string): string {
  return (email || "?")
    .split("@")[0]
    .split(/[._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}

// ---- Splash: a pool ripples when its queue grows ---------------------------
// Driven by data diffs rather than a socket, so it also fires on the focus
// refresh and the heartbeat — anything that raises a count makes waves.
const ripples = ref<Record<string, number[]>>({ pos: [], it: [], mine: [] });
function splash(key: string) {
  const stamp = performance.now();
  ripples.value[key] = [...(ripples.value[key] || []), stamp];
  setTimeout(() => {
    ripples.value[key] = ripples.value[key].filter((r) => r !== stamp);
  }, 950);
}

// ---- All-clear + splash triggers off count transitions ---------------------
const clearShown = ref<string | null>(null);
let clearTimer: ReturnType<typeof setTimeout> | null = null;
watch(counts, (now, prev) => {
  if (!prev) return;
  for (const key of ["pos", "it", "mine"] as const) {
    if (now[key] > prev[key]) splash(key);
    // Echo congratulates ONCE, on the moment a pool empties, then the pool
    // rests quietly with its 0 (Mark: no permanent mascot).
    if (now[key] === 0 && prev[key] > 0) {
      clearShown.value = key;
      if (clearTimer) clearTimeout(clearTimer);
      clearTimer = setTimeout(() => (clearShown.value = null), 9000);
    }
  }
});

// ---- Drag a card onto Mine to claim it ------------------------------------
const draggingTicket = ref<any>(null);
const dragOverMine = ref(false);
function onDragStart(e: DragEvent, t: any) {
  draggingTicket.value = t;
  e.dataTransfer && (e.dataTransfer.effectAllowed = "move");
}
async function onDropClaim(_e: DragEvent) {
  dragOverMine.value = false;
  const t = draggingTicket.value;
  draggingTicket.value = null;
  if (!t) return;
  try {
    await selfAssignTicket(String(t.name));
    splash("mine");
    toast.success(__("Ticket {0} is yours", t.name));
    refreshAll();
  } catch {
    toast.error(__("Could not claim the ticket."));
  }
}

// ---- Echo, the easter egg ---------------------------------------------------
// A few times a shift (random 45–90 min), Echo surfaces with a line drawn
// from the scene's pool, seasoned with live numbers. First appearance lands
// 20–60s after the page opens so a fresh session gets one early delight.
const echoShown = ref(false);
const echoText = ref("");
let echoTimer: ReturnType<typeof setTimeout> | null = null;
let echoHide: ReturnType<typeof setTimeout> | null = null;
let echoIdx = 0;

function echoLines(): string[] {
  const s = homeStats.data || {};
  const resolved = s.resolved_today ?? 0;
  const treading = s.awaiting_first_reply ?? 0;
  const pools: Record<string, string[]> = {
    dawn: [
      __("Morning — {0} came in overnight.", [String(s.open_human ?? 0)]),
      __("Early bird gets the empty queue."),
    ],
    day: [
      resolved
        ? __("Nice work — {0} resolved already today.", [String(resolved)])
        : __("Fresh water. Let's make some waves."),
      treading
        ? __("{0} treading water. A quick reply gets them ashore.", [String(treading)])
        : __("Nobody's treading water. Smooth sailing."),
      __("Halfway through the shift and the water is calm."),
    ],
    golden: [
      treading
        ? __("Home stretch — {0} still treading water.", [String(treading)])
        : __("Golden hour and a clear horizon."),
      __("Golden hour. Finish strong."),
    ],
    night: [__("Quiet hours on. I'll keep watch."), __("Nothing stirring. Rest easy.")],
  };
  return pools[sceneKey.value] || pools.day;
}
function echoPop() {
  const lines = echoLines();
  echoText.value = lines[echoIdx++ % lines.length];
  echoShown.value = true;
  if (echoHide) clearTimeout(echoHide);
  echoHide = setTimeout(() => (echoShown.value = false), 8500);
  scheduleEcho(45 * 60_000, 90 * 60_000);
}
function scheduleEcho(minMs: number, maxMs: number) {
  if (echoTimer) clearTimeout(echoTimer);
  echoTimer = setTimeout(echoPop, minMs + Math.random() * (maxMs - minMs));
}
onMounted(() => scheduleEcho(20_000, 60_000));

// ---- Wave charts: six weeks of swell, computed from real ticket dates ------
const weekStarts = computed(() => {
  const start = dayjs().startOf("week").subtract(5, "week");
  return Array.from({ length: 6 }, (_, i) => start.add(i, "week"));
});
const weekLabels = computed(() =>
  weekStarts.value.map((w) => w.format("MMM D"))
);

function weeklyCounts(pred: (t: any) => any): number[] {
  return weekStarts.value.map((from) => {
    const to = from.add(1, "week");
    return humanRows.value.filter((t) => {
      const d = pred(t);
      if (!d) return false;
      const m = dayjs(d);
      return m.isAfter(from.subtract(1, "millisecond")) && m.isBefore(to);
    }).length;
  });
}
// Open stock at each week's end: created by then and not yet resolved by then.
function openAtWeekEnd(extra: (t: any) => boolean): number[] {
  return weekStarts.value.map((from) => {
    const end = from.add(1, "week");
    return humanRows.value.filter((t) => {
      if (!dayjs(t.creation).isBefore(end)) return false;
      if (t.resolution_date && dayjs(t.resolution_date).isBefore(end)) return false;
      return extra(t);
    }).length;
  });
}
const waveCharts = computed(() => [
  {
    title: __("Created vs Resolved"),
    series: [
      { name: __("Created"), colorIndex: 0, values: weeklyCounts((t) => t.creation) },
      { name: __("Resolved"), colorIndex: 2, values: weeklyCounts((t) => t.resolution_date) },
    ],
  },
  {
    title: __("Open by team"),
    series: [
      { name: "POS", colorIndex: 0, values: openAtWeekEnd((t) => t.agent_group === "POS Support") },
      { name: "IT", colorIndex: 1, values: openAtWeekEnd((t) => t.email_account === "IT Support") },
    ],
  },
  {
    title: __("Open by age"),
    series: [
      {
        name: __("< 1 week"),
        colorIndex: 0,
        values: weekStarts.value.map((from) => {
          const end = from.add(1, "week");
          return humanRows.value.filter(
            (t) =>
              dayjs(t.creation).isBefore(end) &&
              !(t.resolution_date && dayjs(t.resolution_date).isBefore(end)) &&
              end.diff(dayjs(t.creation), "day") < 7
          ).length;
        }),
      },
      {
        name: __("1–4 weeks"),
        colorIndex: 2,
        values: weekStarts.value.map((from) => {
          const end = from.add(1, "week");
          return humanRows.value.filter((t) => {
            if (!dayjs(t.creation).isBefore(end)) return false;
            if (t.resolution_date && dayjs(t.resolution_date).isBefore(end)) return false;
            const days = end.diff(dayjs(t.creation), "day");
            return days >= 7 && days < 28;
          }).length;
        }),
      },
      {
        name: __("Older"),
        colorIndex: 1,
        values: weekStarts.value.map((from) => {
          const end = from.add(1, "week");
          return humanRows.value.filter((t) => {
            if (!dayjs(t.creation).isBefore(end)) return false;
            if (t.resolution_date && dayjs(t.resolution_date).isBefore(end)) return false;
            return end.diff(dayjs(t.creation), "day") >= 28;
          }).length;
        }),
      },
    ],
  },
  {
    title: __("Arrivals by queue"),
    series: [
      {
        name: "POS",
        colorIndex: 0,
        values: weekStarts.value.map((from) => {
          const to = from.add(1, "week");
          return humanRows.value.filter((t) => {
            const m = dayjs(t.creation);
            return (
              t.agent_group === "POS Support" &&
              m.isAfter(from.subtract(1, "millisecond")) &&
              m.isBefore(to)
            );
          }).length;
        }),
      },
      {
        name: "IT",
        colorIndex: 1,
        values: weekStarts.value.map((from) => {
          const to = from.add(1, "week");
          return humanRows.value.filter((t) => {
            const m = dayjs(t.creation);
            return (
              t.email_account === "IT Support" &&
              m.isAfter(from.subtract(1, "millisecond")) &&
              m.isBefore(to)
            );
          }).length;
        }),
      },
    ],
  },
]);

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
  bottom: -14px;
  width: 64px;
  height: 64px;
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
  bottom: -16px;
  width: 88px;
  height: 88px;
  margin-left: -44px;
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
  right: 64px;
  top: 14px;
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

/* --- glass chips --- */
.chip {
  -webkit-backdrop-filter: blur(14px) saturate(1.7);
  backdrop-filter: blur(14px) saturate(1.7);
  background: rgba(255, 255, 255, 0.13);
  border: 1px solid rgba(255, 255, 255, 0.22);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.28);
  border-radius: 14px;
  padding: 10px 18px;
  min-width: 150px;
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
  font-size: 26px;
  font-weight: 700;
  color: #fff;
  font-variant-numeric: tabular-nums;
}
.surfword {
  margin-left: 8px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: 999px;
  padding: 1px 8px;
  vertical-align: 1px;
}

/* --- Echo, hidden beneath the wave until he pops --- */
.echo-break {
  position: absolute;
  right: 4%;
  bottom: -4px;
  z-index: 2;
  display: flex;
  align-items: flex-end;
  gap: 8px;
  pointer-events: none;
  opacity: 0;
  transform: translateY(115%);
  transition: transform 0.7s cubic-bezier(0.34, 1.3, 0.5, 1), opacity 0.5s ease;
}
.echo-break.show {
  transform: translateY(0);
  opacity: 1;
}
.echo-break .echo-bubble {
  opacity: 0;
  transform: translateY(4px);
  transition: opacity 0.4s ease 0.45s, transform 0.4s ease 0.45s;
}
.echo-break.show .echo-bubble {
  opacity: 1;
  transform: none;
}
.echo-avatar {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.85);
  object-fit: cover;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
  background: #fff;
  margin-bottom: 2px;
}
.echo-bubble {
  background: rgba(255, 255, 255, 0.92);
  color: #1b2a4a;
  font-size: 11.5px;
  font-weight: 600;
  border-radius: 12px 12px 3px 12px;
  padding: 6px 10px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.18);
  max-width: 240px;
  margin-bottom: 18px;
}
.scene-night .echo-bubble {
  background: rgba(20, 34, 58, 0.92);
  color: #e8f4fa;
}
@media (prefers-reduced-motion: reduce) {
  .echo-break {
    transition: opacity 0.3s ease;
  }
  .echo-break.show {
    transform: translateY(0);
  }
}

/* --- wave edge (height pinned: at 200% of a wide pane the proportional
       height balloons to ~130px and swallows the hero) --- */
.waveedge {
  display: block;
  margin-bottom: -1px;
  width: 200%;
  height: 44px;
}
@media (prefers-reduced-motion: no-preference) {
  .waveedge {
    animation: drift 9s ease-in-out infinite alternate;
  }
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
  margin: 0 0 10px;
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
.viewall {
  font-size: 11px;
  font-weight: 600;
  color: var(--ink-count);
}

/* --- pools: living waterline, depth-dark bottoms --- */
.pool {
  position: relative;
  overflow: hidden;
  border-radius: 16px;
  height: 110px;
  background: var(--pool-bg);
  border: var(--pool-border);
  box-shadow: var(--pool-shadow);
  text-align: left;
}
.pool:hover {
  filter: brightness(1.02);
}
.pool.sm {
  height: 78px;
}
.pool.sm .meta {
  padding: 10px 14px;
}
.pool.sm .pool-name {
  font-size: 12px;
}
.pool.sm .pool-count {
  font-size: 22px;
}
.pool.dropready {
  outline: 2px dashed var(--ink-count);
  outline-offset: 3px;
}
.water {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  box-shadow: var(--water-glow);
  transition: height 1.1s cubic-bezier(0.22, 1, 0.36, 1);
}
.surf {
  position: absolute;
  left: 0;
  top: -9px;
  width: 200%;
  height: 12px;
  pointer-events: none;
}
@media (prefers-reduced-motion: no-preference) {
  .surf {
    animation: surfdrift 26s linear infinite;
  }
}
@keyframes surfdrift {
  from {
    transform: translateX(0);
  }
  to {
    transform: translateX(-50%);
  }
}
.ripple {
  position: absolute;
  left: 50%;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.85);
  border-radius: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
  animation: rip 0.9s ease-out forwards;
}
@keyframes rip {
  from {
    opacity: 0.9;
    width: 10px;
    height: 10px;
  }
  to {
    opacity: 0;
    width: 120px;
    height: 44px;
  }
}
.clearmsg {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  pointer-events: none;
  opacity: 0;
  transform: translateY(70%);
  transition: transform 0.6s cubic-bezier(0.34, 1.3, 0.5, 1), opacity 0.45s ease;
}
.clearmsg.show {
  transform: none;
  opacity: 1;
}
@media (prefers-reduced-motion: reduce) {
  .clearmsg {
    transition: opacity 0.3s ease;
  }
  .clearmsg.show {
    transform: none;
  }
}
.pool .meta {
  position: absolute;
  inset: 0;
  padding: 14px 18px;
  display: flex;
  flex-direction: column;
}
.pool-name {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--ink-name);
}
.pool-count {
  margin-top: auto;
  font-size: 30px;
  font-weight: 700;
  color: var(--ink-count);
  text-shadow: var(--count-glow);
  font-variant-numeric: tabular-nums;
}
.pool-count.dry {
  color: var(--ink-soft);
}

.more-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: none;
  font-size: 12px;
  font-weight: 600;
  color: var(--seclabel);
}
.more-toggle .chev {
  display: inline-block;
  font-size: 14px;
  transition: transform 0.18s;
}
.more-toggle .chev.open {
  transform: rotate(90deg);
}

/* --- board cards --- */
.jcard {
  display: flex;
  gap: 12px;
  border-radius: 14px;
  padding: 12px 14px;
  background: var(--card-bg);
  border: var(--card-border);
  box-shadow: var(--pool-shadow);
  text-align: left;
}
.jcard:hover {
  filter: brightness(1.02);
}
.jcard[draggable="true"] {
  cursor: grab;
}
.who {
  width: 36px;
  height: 36px;
  flex: 0 0 auto;
  border-radius: 50%;
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
  border-radius: 999px;
  padding: 1px 9px;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.03em;
}
.qtag-it {
  background: rgba(165, 180, 252, 0.3);
  color: var(--ink-name);
}

/* --- analytics --- */
.chart-card {
  border-radius: 16px;
  padding: 14px 16px;
  background: var(--card-bg);
  border: var(--card-border);
  box-shadow: var(--pool-shadow);
}

/* --- SOS --- */
.sos {
  position: fixed;
  right: 34px;
  bottom: 30px;
  z-index: 40;
  border: 0;
  background: none;
  cursor: pointer;
  filter: drop-shadow(0 6px 14px rgba(220, 38, 38, 0.35));
}
@media (prefers-reduced-motion: no-preference) {
  .sos {
    animation: bob 2.6s ease-in-out infinite;
  }
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
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(8, 15, 30, 0.5);
}
.sos-card {
  width: 380px;
  max-width: 92vw;
  border-radius: 18px;
  padding: 18px 20px;
  text-align: center;
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(20px) saturate(1.6);
  backdrop-filter: blur(20px) saturate(1.6);
  border: 1px solid rgba(255, 255, 255, 0.6);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.3);
}
</style>
