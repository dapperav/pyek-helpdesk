<template>
  <div class="flex flex-col h-full">
    <LayoutHeader>
      <template #left-header>
        <div class="text-lg-medium text-ink-gray-9">{{ __("Home") }}</div>
      </template>
      <template #right-header>
        <Button
          :label="__('Refresh')"
          variant="subtle"
          icon-left="lucide-refresh-ccw"
          :loading="tickets.loading || homeStats.loading"
          @click="refreshAll"
        />
      </template>
    </LayoutHeader>

    <!-- Sunset Shift, desktop edition (Mark's picks, 2026-08-18): the wave
         world on top at full width, the dashboard's analytics surviving as a
         quieter section below. Scene tokens + clock come from
         composables/sunsetScene.ts, shared with MobileHome. -->
    <div
      class="flex-1 overflow-y-auto"
      :class="`scene-${sceneKey}`"
      :style="[sceneVars, { background: 'var(--page-bg)' }]"
    >
      <!-- HERO -->
      <div class="hero">
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

        <!-- Wave into the page (light scenes) / lane rope (night). Desktop
             trap: at 200% of a wide pane the SVG's proportional height blows
             up to ~130px, so the height is pinned and the aspect unlocked. -->
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
        <div>
          <p class="seclabel">{{ __("Queues") }}</p>
          <div class="grid grid-cols-3 gap-4">
            <button
              v-for="q in queuePools"
              :key="q.key"
              class="pool"
              @click="openViewByLabel(q.view)"
            >
              <span class="water" :style="{ height: q.level }" />
              <span class="meta">
                <span class="pool-name">{{ q.label }}</span>
                <span class="pool-count num">{{ q.value }}</span>
              </span>
            </button>
          </div>
        </div>

        <div class="grid grid-cols-1 gap-6 xl:grid-cols-[460px_1fr]">
          <div v-if="latest.length">
            <p class="seclabel">{{ scene.inboxLabel || __("Just came in") }}</p>
            <div class="flex flex-col gap-2.5">
              <button
                v-for="t in latest"
                :key="t.name"
                class="jcard"
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

          <div>
            <p class="seclabel">{{ __("Analytics") }}</p>
            <!-- Charts stay on white cards in every scene on purpose: ECharts
                 paints its own axis/label inks for a light ground and can't
                 be re-inked from CSS (canvas) — at night they read as lit
                 panels, which suits Night Swim better than unreadable text. -->
            <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div class="chart-card min-h-[300px]">
                <DonutChart :config="openByAgeChart" />
              </div>
              <div class="chart-card min-h-[300px]">
                <DonutChart :config="teamChart" />
              </div>
              <div class="chart-card min-h-[300px]">
                <DonutChart :config="parkChart" />
              </div>
              <div class="chart-card min-h-[300px]">
                <AxisChart :config="trendChart" />
              </div>
            </div>

            <div v-if="viewCards.length" class="mt-6">
              <p class="seclabel">{{ __("Views") }}</p>
              <div class="grid grid-cols-2 gap-3 lg:grid-cols-3 2xl:grid-cols-4">
                <button
                  v-for="view in viewCards"
                  :key="view.name"
                  class="view-btn group"
                  @click="view.onClick"
                >
                  <span class="view-ic">
                    <component :is="view.icon" class="size-4" />
                  </span>
                  <span class="min-w-0 flex-1 truncate text-base-medium" style="color: var(--ink-strong)">
                    {{ view.label }}
                  </span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- SOS life ring: same trigger, cooldown, and confirm as the phone
           (rings = people in the water, one vocabulary everywhere). -->
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
  </div>
</template>

<script setup lang="ts">
import { LayoutHeader } from "@/components";
import { useSunsetScene } from "@/composables/sunsetScene";
import { useView } from "@/composables/useView";
import { useAuthStore } from "@/stores/auth";
import { useUserStore } from "@/stores/user";
import { __ } from "@/translation";
import { prettyDate } from "@/utils";
import { AxisChart, Button, createResource, dayjs, DonutChart, toast, usePageMeta } from "frappe-ui";
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { parkColor, parkLabel } from "@/config/parks";

usePageMeta(() => ({ title: __("Home") }));

const auth = useAuthStore();
const firstName = computed(
  () => (auth.userName || "there").toString().split(" ")[0]
);

// Scene = token set + clock + greeting, shared with MobileHome.
const { sceneKey, scene, sceneVars, greeting } = useSunsetScene();
const todayLabel = computed(() => dayjs().format("dddd, MMMM D"));

// Saved views (public + private) as launcher cards. useView() with no doctype
// loads every view; each item is already { label, name, icon, route_name,
// onClick } with onClick doing the router.push (see composables/useView.ts).
const { publicViews, pinnedViews } = useView();
const viewCards = computed(() => [
  ...(publicViews.value || []),
  ...(pinnedViews.value || []),
]);

// Charts still derive from one client-side fetch; the hero chips come from
// get_home_stats, which draws the human/bot line server-side with the same
// test the ack suppression and AI skip use. (The old metric-card row is gone —
// the chips carry Treading water / My open / Resolved, the pools carry the
// queue depths, and Silenced today lives on in the Camera-drops view.)
const tickets = createResource({
  url: "frappe.client.get_list",
  makeParams: () => ({
    doctype: "HD Ticket",
    fields: [
      "name",
      "status",
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

const homeStats = createResource({
  url: "helpdesk.api.pyek_home.get_home_stats",
  auto: true,
});

// Rows from senders the backend judged automated (plus auto-closed camera
// drops) are dropped from the people-facing charts — 60%+ of raw volume is
// bots, and "By Park: Unspecified 44%" was mostly that traffic.
const botSenders = computed(
  () => new Set<string>(homeStats.data?.bot_senders || [])
);
const humanRows = computed(() =>
  rows.value.filter((t) => !botSenders.value.has((t.raised_by || "").toLowerCase()))
);

const router = useRouter();
function openViewByLabel(label: string) {
  const all = [...(publicViews.value || []), ...(pinnedViews.value || [])];
  const v = all.find((x: any) => x.label === label);
  router.push({ name: "TicketsAgent", query: v ? { view: v.name } : {} });
}
function openTicket(name: string) {
  router.push({ name: "TicketAgent", params: { ticketId: name } });
}

// ---- Queue pools (waterline = depth, same math as the phone) -------------
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
function level(n: number): string {
  return n > 0 ? Math.min(95, Math.max(10, n * 10)) + "%" : "0%";
}
const queuePools = computed(() => [
  { key: "pos", label: __("POS"), value: counts.value.pos, level: level(counts.value.pos), view: "POS Tickets" },
  { key: "it", label: __("IT"), value: counts.value.it, level: level(counts.value.it), view: "IT Tickets" },
  { key: "mine", label: __("Mine"), value: counts.value.mine, level: level(counts.value.mine), view: "My Open Tickets" },
]);

// ---- Just came in (newest unanswered human tickets, w/ AI summaries) -----
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
      "contact",
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

// Sender photo, same two sources as the ticket LIST cards: the ticket
// contact's image first, else a matching User's user_image.
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
  () => recent.data,
  (recRows: any[]) => {
    const names = [
      ...new Set((recRows || []).map((t: any) => t.contact).filter(Boolean)),
    ];
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

// ---- Grouping helper ----------------------------------------------------
function countBy(list: any[], key: (t: any) => string) {
  const m = new Map<string, number>();
  for (const t of list) {
    const k = key(t);
    m.set(k, (m.get(k) || 0) + 1);
  }
  return m;
}

// ---- Open by age (donut) -------------------------------------------------
// Replaces "By Status": a cumulative status donut always reads ~98% Closed
// and says nothing. Age of what's still open is the number an agent triages by.
const AGE_BUCKETS = [
  { label: __("Under 1 day"), maxDays: 1, color: "#2563EB" },
  { label: __("1–3 days"), maxDays: 3, color: "#D97706" },
  { label: __("3–7 days"), maxDays: 7, color: "#EA580C" },
  { label: __("Over 7 days"), maxDays: Infinity, color: "#DC2626" },
];
const openByAgeChart = computed(() => {
  const now = dayjs();
  const open = humanRows.value.filter(
    (t) => t.status_category === "Open" || t.status_category === "Paused"
  );
  const data = AGE_BUCKETS.map((b) => ({ label: b.label, value: 0 }));
  for (const t of open) {
    const days = now.diff(dayjs(t.creation), "day", true);
    const i = AGE_BUCKETS.findIndex((b) => days < b.maxDays);
    data[i >= 0 ? i : AGE_BUCKETS.length - 1].value += 1;
  }
  return {
    title: __("Open by age (human)"),
    data: data.filter((d) => d.value > 0),
    categoryColumn: "label",
    valueColumn: "value",
    colors: data
      .map((d, i) => ({ d, c: AGE_BUCKETS[i].color }))
      .filter(({ d }) => d.value > 0)
      .map(({ c }) => c),
    maxSliceCount: 4,
  };
});

// ---- By Team (donut, human tickets) --------------------------------------
const TEAM_COLORS: Record<string, string> = {
  "POS Support": "#2563EB",
  "IT Support": "#0891B2",
  Unassigned: "#94A3B8",
};
const teamChart = computed(() => {
  const m = countBy(humanRows.value, (t) => t.agent_group || "Unassigned");
  const data = [...m.entries()].map(([label, value]) => ({ label, value }));
  return {
    title: __("By Team (human)"),
    data,
    categoryColumn: "label",
    valueColumn: "value",
    colors: data.map((d) => TEAM_COLORS[d.label] || "#94A3B8"),
    maxSliceCount: 12,
  };
});

// ---- By Park (donut, brand colors, human tickets) -------------------------
const parkChart = computed(() => {
  const m = countBy(humanRows.value, (t) => parkLabel(t.pyek_property));
  const data = [...m.entries()].map(([label, value]) => ({ label, value }));
  return {
    title: __("By Park (human)"),
    data,
    categoryColumn: "label",
    valueColumn: "value",
    colors: data.map((d) => parkColor(d.label)),
    maxSliceCount: 12,
  };
});

// ---- Trend: created vs resolved, last 6 weeks (line) --------------------
const trendChart = computed(() => {
  const weeks = 6;
  const start = dayjs().startOf("week").subtract(weeks - 1, "week");
  const buckets = Array.from({ length: weeks }, (_, i) => {
    const from = start.add(i, "week");
    return { from, to: from.add(1, "week"), date: from.format("MMM D"), Created: 0, Resolved: 0 };
  });
  const bucketFor = (d: any) => {
    if (!d) return -1;
    const t = dayjs(d);
    for (let i = 0; i < buckets.length; i++) {
      if (t.isAfter(buckets[i].from.subtract(1, "millisecond")) && t.isBefore(buckets[i].to)) return i;
    }
    return -1;
  };
  for (const t of rows.value) {
    const ci = bucketFor(t.creation);
    if (ci >= 0) buckets[ci].Created += 1;
    const ri = bucketFor(t.resolution_date);
    if (ri >= 0) buckets[ri].Resolved += 1;
  }
  return {
    title: __("Created vs Resolved (6 weeks)"),
    data: buckets.map(({ date, Created, Resolved }) => ({ date, Created, Resolved })),
    xAxis: { key: "date", type: "category" as const },
    yAxis: {},
    series: [
      { name: "Created", type: "line" as const },
      { name: "Resolved", type: "line" as const },
    ],
    colors: ["#2563EB", "#16A34A"],
  };
});
</script>

<style scoped>
.hero {
  position: relative;
  overflow: hidden;
  background: var(--hero-bg);
}

/* --- scene decor (same marks as MobileHome, desktop-sized) --- */
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

/* Desktop wave: height pinned + aspect unlocked (at 200% of a wide pane the
   proportional height balloons to ~130px and swallows the hero). */
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

/* --- pools --- */
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
  content: "";
  position: absolute;
  top: 3px;
  left: 10%;
  right: 45%;
  height: 2px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.75);
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

/* --- just-came-in cards --- */
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
.qtag-pos {
  background: rgba(103, 232, 249, 0.25);
  color: var(--ink-count);
}
.qtag-it {
  background: rgba(165, 180, 252, 0.3);
  color: var(--ink-name);
}

/* --- analytics + views --- */
.chart-card {
  border-radius: 16px;
  padding: 4px;
  background: #ffffff;
  border: var(--pool-border);
  box-shadow: var(--pool-shadow);
}
.view-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  border-radius: 12px;
  padding: 10px 12px;
  background: var(--card-bg);
  border: var(--card-border);
  box-shadow: var(--pool-shadow);
  text-align: left;
}
.view-btn:hover {
  filter: brightness(1.02);
}
.view-ic {
  width: 30px;
  height: 30px;
  flex: 0 0 auto;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: var(--who-bg);
  color: var(--who-ink);
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
