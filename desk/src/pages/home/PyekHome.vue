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
          :loading="tickets.loading"
          @click="tickets.reload()"
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

        <!-- Metric cards -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <NumberChart
            v-for="card in metricCards"
            :key="card.title"
            class="border rounded-lg min-h-[110px]"
            :config="card"
          />
        </div>

        <!-- Saved-view launchers -->
        <div v-if="viewCards.length">
          <h2 class="mb-2 text-lg-medium text-ink-gray-8">{{ __("Views") }}</h2>
          <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            <button
              v-for="view in viewCards"
              :key="view.name"
              class="group flex items-center gap-3 rounded-lg border border-outline-gray-2 bg-surface-white px-3.5 py-3 text-left transition hover:border-outline-blue-4 hover:shadow-sm"
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
            <DonutChart :config="statusChart" />
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

// One fetch of all tickets; every metric + chart is derived client-side. The
// dataset is small (~50), so this is far simpler than N server group-by calls.
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
      "agreement_status",
      "resolution_date",
      "creation",
    ],
    limit_page_length: 0,
  }),
  auto: true,
});
const rows = computed<any[]>(() => tickets.data || []);

// ---- Metric cards -------------------------------------------------------
const startOfToday = () => dayjs().startOf("day");

const metricCards = computed(() => {
  const open = rows.value.filter((t) => t.status_category !== "Resolved").length;
  const breached = rows.value.filter(
    (t) => t.agreement_status === "Failed"
  ).length;
  const resolvedToday = rows.value.filter(
    (t) =>
      t.status_category === "Resolved" &&
      t.resolution_date &&
      dayjs(t.resolution_date).isAfter(startOfToday())
  ).length;
  return [
    { title: __("Open"), value: open },
    { title: __("SLA breached / at risk"), value: breached },
    { title: __("Resolved today"), value: resolvedToday },
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

// ---- By Status (donut) --------------------------------------------------
const STATUS_COLORS: Record<string, string> = {
  Open: "#2563EB",
  Replied: "#0891B2",
  "Waiting on Customer": "#D97706",
  "On Hold": "#7C3AED",
  Escalated: "#E91E8C",
  Resolved: "#16A34A",
  Closed: "#64748B",
};
const statusChart = computed(() => {
  const m = countBy(rows.value, (t) => t.status || "Unknown");
  const data = [...m.entries()].map(([label, value]) => ({ label, value }));
  return {
    title: __("By Status"),
    data,
    categoryColumn: "label",
    valueColumn: "value",
    colors: data.map((d) => STATUS_COLORS[d.label] || "#94A3B8"),
    maxSliceCount: 12,
  };
});

// ---- By Team (donut) ----------------------------------------------------
const TEAM_COLORS: Record<string, string> = {
  "POS Support": "#2563EB",
  "IT Support": "#0891B2",
  Unassigned: "#94A3B8",
};
const teamChart = computed(() => {
  const m = countBy(rows.value, (t) => t.agent_group || "Unassigned");
  const data = [...m.entries()].map(([label, value]) => ({ label, value }));
  return {
    title: __("By Team"),
    data,
    categoryColumn: "label",
    valueColumn: "value",
    colors: data.map((d) => TEAM_COLORS[d.label] || "#94A3B8"),
    maxSliceCount: 12,
  };
});

// ---- By Park (donut, brand colors) --------------------------------------
const parkChart = computed(() => {
  const m = countBy(rows.value, (t) => parkLabel(t.pyek_property));
  const data = [...m.entries()].map(([label, value]) => ({ label, value }));
  return {
    title: __("By Park"),
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
