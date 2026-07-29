<template>
  <div class="flex flex-col h-full">
    <LayoutHeader>
      <template #left-header>
        <div class="text-lg-medium text-ink-gray-9">{{ __("Home") }}</div>
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

        <!-- Metric tiles: tap opens the closest saved view -->
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

        <!-- Jump to saved views -->
        <div>
          <p class="mb-2 text-sm-medium text-ink-gray-6">{{ __("Jump to") }}</p>
          <div class="overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-white">
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
              <span class="rounded-full bg-surface-gray-2 px-2 text-sm text-ink-gray-6">
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
import { useView } from "@/composables/useView";
import { useAuthStore } from "@/stores/auth";
import { __ } from "@/translation";
import { createResource, dayjs, usePageMeta } from "frappe-ui";
import { computed } from "vue";
import { useRouter } from "vue-router";
import LucideUser from "~icons/lucide/user";
import LucideCopy from "~icons/lucide/copy";
import LucideFileText from "~icons/lucide/file-text";
import LucideReceipt from "~icons/lucide/receipt";

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

// One fetch of all tickets; every count is derived client-side (mirrors the
// desktop dashboard). AP has a few hundred open tickets, so a single get_list
// with a slim field set is far cheaper than a dozen server-side counts.
const tickets = createResource({
  url: "frappe.client.get_list",
  makeParams: () => ({
    doctype: "HD Ticket",
    fields: [
      "name",
      "status",
      "status_category",
      "pyek_requested_due_date",
      "ap_missing_invoice",
      "ap_duplicate",
      "ap_doc_type",
      "is_merged",
      "_assign",
    ],
    limit_page_length: 0,
  }),
  auto: true,
});
const rows = computed<any[]>(() => tickets.data || []);

const startOfToday = () => dayjs().startOf("day");
const startOfTomorrow = () => dayjs().add(1, "day").startOf("day");
const notResolved = (t: any) => t.status_category !== "Resolved";
const hasDue = (t: any) => !!t.pyek_requested_due_date;

function assignedToMe(t: any): boolean {
  try {
    return (JSON.parse(t._assign || "[]") as string[]).includes(auth.user);
  } catch {
    return false;
  }
}

const counts = computed(() => {
  const r = rows.value;
  const overdue = r.filter(
    (t) => notResolved(t) && hasDue(t) && dayjs(t.pyek_requested_due_date).isBefore(startOfToday())
  ).length;
  const dueToday = r.filter(
    (t) =>
      notResolved(t) &&
      hasDue(t) &&
      !dayjs(t.pyek_requested_due_date).isBefore(startOfToday()) &&
      dayjs(t.pyek_requested_due_date).isBefore(startOfTomorrow())
  ).length;
  return {
    overdue,
    dueToday,
    pendingApproval: r.filter((t) => t.status === "Pending Approval").length,
    missing: r.filter((t) => notResolved(t) && Number(t.ap_missing_invoice)).length,
    mine: r.filter((t) => notResolved(t) && assignedToMe(t)).length,
    duplicates: r.filter((t) => notResolved(t) && Number(t.ap_duplicate) && !Number(t.is_merged)).length,
    statements: r.filter((t) => t.ap_doc_type === "Statement").length,
    reimbursements: r.filter((t) => t.ap_doc_type === "Reimbursement").length,
  };
});

const tiles = computed(() => [
  {
    key: "overdue",
    label: __("Overdue"),
    value: counts.value.overdue,
    view: "Due & overdue",
    fg: "#B91C1C",
    style: { backgroundColor: "#FEF2F2" },
  },
  {
    key: "dueToday",
    label: __("Due today"),
    value: counts.value.dueToday,
    view: "Due & overdue",
    fg: "#B45309",
    style: { backgroundColor: "#FFFBEB" },
  },
  {
    key: "pending",
    label: __("Pending approval"),
    value: counts.value.pendingApproval,
    view: "Pending approval",
    fg: "#1E293B",
    style: { backgroundColor: "#fff", border: "0.5px solid var(--outline-gray-2, #e2e8f0)" },
  },
  {
    key: "missing",
    label: __("Missing invoice"),
    value: counts.value.missing,
    view: "Missing Invoice",
    fg: "#1E293B",
    style: { backgroundColor: "#fff", border: "0.5px solid var(--outline-gray-2, #e2e8f0)" },
  },
]);

const jumps = computed(() => [
  { key: "mine", label: __("My queue"), value: counts.value.mine, view: "My queue", icon: LucideUser },
  { key: "dupes", label: __("Duplicates"), value: counts.value.duplicates, view: "Duplicates", icon: LucideCopy },
  { key: "stmts", label: __("Statements"), value: counts.value.statements, view: "Statements", icon: LucideFileText },
  { key: "reimb", label: __("Reimbursements"), value: counts.value.reimbursements, view: "Reimbursements", icon: LucideReceipt },
]);

// Open a saved HD View by its label. Falls back to the plain ticket list if a
// view with that label isn't present.
const { publicViews } = useView();
function openView(label: string) {
  const v = (publicViews.value || []).find((x: any) => x.label === label);
  router.push({ name: "TicketsAgent", query: v ? { view: v.name } : {} });
}
</script>
