<template>
  <div class="flex flex-col h-full">
    <LayoutHeader>
      <template #left-header>
        <div class="text-lg-medium text-ink-gray-9">{{ __("Dashboard") }}</div>
      </template>
      <template #right-header>
        <Button
          :label="__('Refresh')"
          variant="subtle"
          icon-left="lucide-refresh-ccw"
          :loading="tickets.loading || homeStats.loading"
          @click="
            () => {
              tickets.reload();
              homeStats.reload();
            }
          "
        />
      </template>
    </LayoutHeader>

    <div class="flex-1 overflow-y-auto">
      <div class="mx-auto w-full max-w-[1500px] p-5 flex flex-col gap-6">
        <!-- Greeting -->
        <div>
          <h1 class="text-2xl font-semibold text-ink-gray-9">
            {{ greeting }}, {{ firstName }}
          </h1>
          <p class="mt-1 text-p-base text-ink-gray-6">{{ todayLabel }}</p>
        </div>

        <!-- Metric cards — each one is something an agent can act on, and
             clicking it lands on the queue that pays it off. Human/bot line
             comes from the backend (same test as ack suppression / AI skip). -->
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          <button
            v-for="card in metricCards"
            :key="card.title"
            type="button"
            class="text-left rounded-lg border border-outline-gray-2 transition hover:border-outline-blue-4 hover:shadow-sm"
            :title="card.tooltip"
            @click="card.onClick && card.onClick()"
          >
            <NumberChart class="min-h-[110px]" :config="card" />
          </button>
        </div>

        <!-- Saved-view launchers -->
        <div v-if="viewCards.length">
          <h2 class="mb-2 text-lg-medium text-ink-gray-8">{{ __("Views") }}</h2>
          <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            <button
              v-for="view in viewCards"
              :key="view.name"
              class="group flex items-center gap-3 rounded-lg border border-outline-gray-2 bg-surface-base px-3.5 py-3 text-left transition hover:border-outline-blue-4 hover:shadow-sm"
              @click="view.onClick"
            >
              <span
                class="grid size-8 shrink-0 place-items-center rounded-md bg-surface-gray-2 text-ink-gray-7 transition group-hover:bg-surface-blue-2 group-hover:text-ink-blue-5"
              >
                <component :is="view.icon" class="size-4" />
              </span>
              <span class="min-w-0 flex-1 truncate text-base-medium text-ink-gray-8">
                {{ view.label }}
              </span>
            </button>
          </div>
        </div>

        <!-- Charts -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div class="border rounded-lg p-1 min-h-[320px]">
            <DonutChart :config="openByAgeChart" />
          </div>
          <div class="border rounded-lg p-1 min-h-[320px]">
            <DonutChart :config="teamChart" />
          </div>
          <div class="border rounded-lg p-1 min-h-[320px]">
            <DonutChart :config="parkChart" />
          </div>
          <div class="border rounded-lg p-1 min-h-[320px]">
            <AxisChart :config="trendChart" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { LayoutHeader } from "@/components";
import { useView } from "@/composables/useView";
import { useAuthStore } from "@/stores/auth";
import { __ } from "@/translation";
import { AxisChart, Button, createResource, dayjs, DonutChart, NumberChart, usePageMeta } from "frappe-ui";
import { computed } from "vue";
import { useRouter } from "vue-router";
import { parkColor, parkLabel } from "@/config/parks";

usePageMeta(() => ({ title: __("Dashboard") }));

const auth = useAuthStore();
const firstName = computed(
  () => (auth.userName || "there").toString().split(" ")[0]
);
const greeting = computed(() => {
  const h = new Date().getHours();
  if (h < 12) return __("Good morning");
  if (h < 18) return __("Good afternoon");
  return __("Good evening");
});
const todayLabel = computed(() =>
  dayjs().format("dddd, MMMM D, YYYY")
);

// Saved views (public + private) as launcher cards. useView() with no doctype
// loads every view; each item is already { label, name, icon, route_name,
// onClick } with onClick doing the router.push (see composables/useView.ts).
const { publicViews, pinnedViews } = useView();
const viewCards = computed(() => [
  ...(publicViews.value || []),
  ...(pinnedViews.value || []),
]);

// Charts still derive from one client-side fetch; the TILES come from
// get_home_stats, which draws the human/bot line server-side with the same
// test the ack suppression and AI skip use. The old tiles counted raw totals —
// "SLA breached / at risk: 125" was historical machine failures next to
// "Open: 6", the biggest number on the page and one nobody could act on.
const tickets = createResource({
  url: "frappe.client.get_list",
  makeParams: () => ({
    doctype: "HD Ticket",
    fields: [
      "name",
      "status",
      "status_category",
      "agent_group",
      "pyek_property",
      "raised_by",
      "resolution_date",
      "creation",
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

// ---- Metric cards -------------------------------------------------------
// Each card routes to the saved view that answers it (matched by label so a
// renamed/missing view degrades to the plain list, never an error).
// Reuses the publicViews/pinnedViews already loaded for the launcher cards.
const router = useRouter();
function openViewByLabel(label: string) {
  const all = [...(publicViews.value || []), ...(pinnedViews.value || [])];
  const v = all.find((x: any) => x.label === label);
  router.push({ name: "TicketsAgent", query: v ? { view: v.name } : {} });
}

const metricCards = computed(() => {
  const s = homeStats.data || {};
  return [
    {
      title: __("My open tickets"),
      value: s.my_open ?? 0,
      tooltip: __("Open tickets assigned to you"),
      onClick: () => openViewByLabel("My Open Tickets"),
    },
    {
      title: __("Open (human)"),
      value: s.open_human ?? 0,
      tooltip: __("Open tickets from real people — bot traffic excluded"),
      onClick: () => openViewByLabel("Open Tickets"),
    },
    {
      title: __("Awaiting first reply"),
      value: s.awaiting_first_reply ?? 0,
      tooltip: __("Human tickets nobody has answered yet — oldest first"),
      onClick: () => openViewByLabel("Awaiting first reply"),
    },
    {
      title: __("Resolved today"),
      value: s.resolved_today ?? 0,
      tooltip: __("Tickets resolved since midnight"),
    },
    {
      title: __("Silenced today"),
      value: s.silenced_today ?? 0,
      tooltip: __(
        `${s.silenced_today_camera ?? 0} camera drops auto-closed; the rest is bot mail kept out of the queue`
      ),
      onClick: () => openViewByLabel("Camera drops (auto-closed)"),
    },
  ];
});

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
// Unscoped this read "Unspecified 44%" — camera alerts and refund work orders
// carry no park. Humans do.
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
