<template>
  <!-- PYEK IT: phone-first dashboard. Opened by the "Dashboard" bottom-nav tab
       (route Home renders this on mobile, PyekHome on desktop). Triage tiles up
       top (each opens the master "All Open" queue) + jump-to the specific
       queues with live counts. All counts derive from ONE ticket fetch. -->
  <div class="flex flex-col h-full">
    <PullToRefreshIndicator
      :pull="pull"
      :refreshing="refreshing"
      :threshold="threshold"
    />
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
      <div class="flex flex-col gap-5 p-4">
        <!-- Greeting -->
        <div>
          <h1 class="text-xl font-semibold text-ink-gray-9">
            {{ greeting }}, {{ firstName }}
          </h1>
          <p class="mt-0.5 text-p-sm text-ink-gray-6">{{ todayLabel }}</p>
        </div>

        <!-- Triage tiles: tap opens the All Open queue -->
        <div class="grid grid-cols-2 gap-3">
          <button
            v-for="tile in tiles"
            :key="tile.key"
            class="flex flex-col items-start rounded-xl px-3.5 py-3 text-left active:opacity-80"
            :style="tile.style"
            @click="openView(tile.view)"
          >
            <span class="text-sm" :style="{ color: tile.fg }">{{ tile.label }}</span>
            <span class="mt-0.5 text-2xl font-medium" :style="{ color: tile.fg }">
              {{ tile.value }}
            </span>
          </button>
        </div>

        <!-- Jump to the specific queues -->
        <div>
          <p class="mb-2 text-sm-medium text-ink-gray-6">{{ __("Queues") }}</p>
          <div
            class="overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-base"
          >
            <button
              v-for="(j, i) in jumps"
              :key="j.key"
              class="flex w-full items-center justify-between px-4 py-3 text-left active:bg-surface-gray-2"
              :class="{ 'border-b border-outline-gray-2': i < jumps.length - 1 }"
              @click="openView(j.view)"
            >
              <span class="flex items-center gap-2.5 text-base text-ink-gray-8">
                <component :is="j.icon" class="size-4 text-ink-gray-6" />
                {{ j.label }}
              </span>
              <span
                class="rounded-full bg-surface-gray-2 px-2 text-sm text-ink-gray-6"
              >
                {{ j.value }}
              </span>
            </button>
          </div>
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
import { Button, createResource, dayjs, usePageMeta } from "frappe-ui";
import { computed } from "vue";
import { useRouter } from "vue-router";
import LucideScanBarcode from "~icons/lucide/scan-barcode";
import LucideHeadset from "~icons/lucide/headset";
import LucideMegaphone from "~icons/lucide/megaphone";
import LucideUser from "~icons/lucide/user";

usePageMeta(() => ({ title: __("Dashboard") }));

const router = useRouter();
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
const todayLabel = computed(() => dayjs().format("dddd, MMMM D"));

// Human-scoped counts from the backend (same human/bot test as the ack
// suppression and AI skip) — feeds the "Awaiting reply" tile, which replaced
// "SLA breached" (that number was historical machine failures, unactionable).
const homeStats = createResource({
  url: "helpdesk.api.pyek_home.get_home_stats",
  auto: true,
});

// One fetch of all tickets; every count is derived client-side (mirrors the
// desktop PyekHome dashboard).
const tickets = createResource({
  url: "frappe.client.get_list",
  makeParams: () => ({
    doctype: "HD Ticket",
    fields: [
      "name",
      "status",
      "status_category",
      "pyek_requested_due_date",
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

// Same gesture as the ticket screen. The Refresh button in the header stays — the
// gesture is the idiom, the button is the discoverable version of it.
const { pull, refreshing, threshold } = usePullToRefresh(() => {
  homeStats.reload();
  return tickets.reload();
});

const startOfTomorrow = () => dayjs().add(1, "day").startOf("day");
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
    open: r.length,
    unassigned: r.filter((t) => {
      try {
        return JSON.parse(t._assign || "[]").length === 0;
      } catch {
        return true;
      }
    }).length,
    dueSoon: r.filter(
      (t) =>
        t.pyek_requested_due_date &&
        dayjs(t.pyek_requested_due_date).isBefore(startOfTomorrow())
    ).length,
    pos: r.filter((t) => t.agent_group === "POS Support").length,
    // IT queue mirrors the "IT Tickets" view, which filters by mailbox.
    it: r.filter((t) => t.email_account === "IT Support").length,
    wrike: r.filter((t) => t.raised_by === "wrike@pyekgroup.com").length,
    mine: r.filter(assignedToMe).length,
  };
});

const tiles = computed(() => [
  {
    key: "open",
    label: __("Open"),
    value: counts.value.open,
    view: "All Open Tickets",
    fg: "#1D4ED8",
    style: { backgroundColor: "#EFF6FF" },
  },
  {
    key: "unassigned",
    label: __("Unassigned"),
    value: counts.value.unassigned,
    view: "All Open Tickets",
    fg: "#1E293B",
    style: {
      backgroundColor: "#fff",
      border: "0.5px solid var(--outline-gray-2, #e2e8f0)",
    },
  },
  {
    key: "dueSoon",
    label: __("Due soon"),
    value: counts.value.dueSoon,
    view: "All Open Tickets",
    fg: "#B45309",
    style: { backgroundColor: "#FFFBEB" },
  },
  {
    key: "awaiting",
    label: __("Awaiting reply"),
    value: homeStats.data?.awaiting_first_reply ?? 0,
    view: "Awaiting first reply",
    fg: "#B91C1C",
    style: { backgroundColor: "#FEF2F2" },
  },
]);

const jumps = computed(() => [
  { key: "pos", label: __("POS"), value: counts.value.pos, view: "POS Tickets", icon: LucideScanBarcode },
  { key: "it", label: __("IT"), value: counts.value.it, view: "IT Tickets", icon: LucideHeadset },
  { key: "wrike", label: __("Wrike"), value: counts.value.wrike, view: "Open Wrike Tickets", icon: LucideMegaphone },
  { key: "mine", label: __("My open tickets"), value: counts.value.mine, view: "My Open Tickets", icon: LucideUser },
]);

// Open a saved HD View by its label. Falls back to the plain ticket list if a
// view with that label isn't present.
const { publicViews } = useView();
function openView(label: string) {
  const v = (publicViews.value || []).find((x: any) => x.label === label);
  router.push({ name: "TicketsAgent", query: v ? { view: v.name } : {} });
}
</script>
