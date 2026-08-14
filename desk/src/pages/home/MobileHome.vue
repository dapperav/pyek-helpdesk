<template>
  <!-- PYEK IT: phone-first home, redesigned 2026-08-14 (Mark's picks: Home is
       the ROUTER — the bottom bar slimmed to Home · Mine · Menu, so this page
       carries the queue boxes). Three bands: a "needs you now" action strip
       (only non-zero chips), navy brand queue cards, and the newest unanswered
       human tickets with their AI summaries. All counts derive from one ticket
       fetch + get_home_stats (whose bot_senders list scopes "human" with the
       same judgment the backend uses). -->
  <div class="flex flex-col h-full">
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

    <div class="flex-1 overflow-y-auto">
      <div class="flex flex-col gap-5 p-4">
        <!-- Greeting -->
        <div>
          <h1 class="text-xl font-semibold text-ink-gray-9">
            {{ greeting }}, {{ firstName }}
          </h1>
          <p class="mt-0.5 text-p-sm text-ink-gray-6">{{ todayLabel }}</p>
        </div>

        <!-- Needs you now: only chips with something behind them render. -->
        <div>
          <p class="mb-2 text-sm-medium text-ink-gray-6">
            {{ __("Needs you now") }}
          </p>
          <div v-if="actionChips.length" class="flex gap-2 overflow-x-auto">
            <button
              v-for="chip in actionChips"
              :key="chip.key"
              class="flex shrink-0 flex-col items-start rounded-xl px-3.5 py-2.5 text-left active:opacity-80"
              :style="{ backgroundColor: chip.bg }"
              @click="openView(chip.view)"
            >
              <span class="text-sm" :style="{ color: chip.fg }">
                {{ chip.label }}
              </span>
              <span
                class="mt-0.5 text-xl font-semibold"
                :style="{ color: chip.fg }"
              >
                {{ chip.value }}
              </span>
            </button>
          </div>
          <div
            v-else
            class="rounded-xl px-3.5 py-3 text-sm font-medium"
            style="background-color: #ecfdf5; color: #047857"
          >
            {{ __("All clear — nothing is waiting on you right now.") }}
          </div>
        </div>

        <!-- Queue boxes: the router. Navy brand cards, big counts. -->
        <div>
          <p class="mb-2 text-sm-medium text-ink-gray-6">{{ __("Queues") }}</p>
          <div class="grid grid-cols-2 gap-3">
            <button
              v-for="q in queueCards"
              :key="q.key"
              class="flex flex-col items-start rounded-xl px-3.5 py-3 text-left active:opacity-80"
              style="background-color: #1b2a4a"
              @click="openView(q.view)"
            >
              <span class="flex w-full items-center justify-between">
                <component :is="q.icon" class="size-5" style="color: #67e8f9" />
                <span class="text-2xl font-semibold text-white">
                  {{ q.value }}
                </span>
              </span>
              <span class="mt-1.5 text-sm font-medium text-white/80">
                {{ q.label }}
              </span>
            </button>
          </div>
        </div>

        <!-- Newest unanswered human tickets, with the AI summary as the line
             that tells you WHAT it is — not just how many. Hidden at zero
             (the strip's all-clear already says so). -->
        <div v-if="latest.length">
          <p class="mb-2 text-sm-medium text-ink-gray-6">
            {{ __("Just came in") }}
          </p>
          <div
            class="overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-base"
          >
            <button
              v-for="(t, i) in latest"
              :key="t.name"
              class="block w-full px-4 py-3 text-left active:bg-surface-gray-2"
              :class="{
                'border-b border-outline-gray-2': i < latest.length - 1,
              }"
              @click="openTicket(t.name)"
            >
              <span class="flex items-baseline justify-between gap-2">
                <span class="truncate text-base font-medium text-ink-gray-9">
                  {{ t.subject }}
                </span>
                <span class="shrink-0 text-xs text-ink-gray-5">
                  {{ prettyDate(t.creation) }}
                </span>
              </span>
              <span
                v-if="t.pyek_summary"
                class="summary mt-0.5 text-sm text-ink-gray-6"
              >
                {{ t.pyek_summary }}
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
import { prettyDate } from "@/utils";
import { Button, createResource, dayjs, usePageMeta } from "frappe-ui";
import { computed } from "vue";
import { useRouter } from "vue-router";
import LucideHeadset from "~icons/lucide/headset";
import LucideMegaphone from "~icons/lucide/megaphone";
import LucideScanBarcode from "~icons/lucide/scan-barcode";
import LucideUser from "~icons/lucide/user";

usePageMeta(() => ({ title: __("Home") }));

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

// Human-scoped counts + the bot_senders list (same human/bot judgment as the
// ack suppression and AI skip) — feeds the strip and scopes "Just came in".
const homeStats = createResource({
  url: "helpdesk.api.pyek_home.get_home_stats",
  auto: true,
});

// One fetch of all tickets; queue counts derive client-side (mirrors the
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

// Newest tickets with subject + AI summary for the "Just came in" band. Kept
// separate from the count fetch: summaries are long text, so pulling them for
// EVERY ticket would bloat the big fetch for four rendered rows.
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

// Same gesture as the ticket screen. The Refresh button in the header stays — the
// gesture is the idiom, the button is the discoverable version of it.
const { pull, refreshing, threshold } = usePullToRefresh(refreshAll);

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

// Only chips with a non-zero count render — the strip is a to-do, not a report.
const actionChips = computed(() =>
  [
    {
      key: "awaiting",
      label: __("Awaiting first reply"),
      value: homeStats.data?.awaiting_first_reply ?? 0,
      view: "Awaiting first reply",
      fg: "#B91C1C",
      bg: "#FEF2F2",
    },
    {
      key: "dueSoon",
      label: __("Due soon"),
      value: counts.value.dueSoon,
      view: "All Open Tickets",
      fg: "#B45309",
      bg: "#FFFBEB",
    },
    {
      key: "mine",
      label: __("My open"),
      value: counts.value.mine,
      view: "My Open Tickets",
      fg: "#1D4ED8",
      bg: "#EFF6FF",
    },
  ].filter((c) => c.value > 0)
);

const queueCards = computed(() => [
  { key: "pos", label: __("POS"), value: counts.value.pos, view: "POS Tickets", icon: LucideScanBarcode },
  { key: "it", label: __("IT"), value: counts.value.it, view: "IT Tickets", icon: LucideHeadset },
  { key: "wrike", label: __("Wrike"), value: counts.value.wrike, view: "Open Wrike Tickets", icon: LucideMegaphone },
  { key: "mine", label: __("My tickets"), value: counts.value.mine, view: "My Open Tickets", icon: LucideUser },
]);

// Open a saved HD View by its label. Falls back to the plain ticket list if a
// view with that label isn't present.
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
.summary {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
