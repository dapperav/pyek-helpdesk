<template>
  <!-- Bottom action sheet opened by swiping a ticket row left. Full-screen
       backdrop + a sheet pinned to the bottom (safe-area padded). Emits `done`
       after an action so the list reloads, `close` on dismiss. -->
  <div class="fixed inset-0 z-50" @click.self="emit('close')">
    <div class="absolute inset-0 bg-black-overlay-400" @click="emit('close')" />
    <div
      class="absolute inset-x-0 bottom-0 rounded-t-2xl shadow-2xl"
      style="
        padding-bottom: env(safe-area-inset-bottom);
        background-color: #ffffff;
      "
    >
      <div class="mx-auto mb-1 mt-2.5 h-1 w-9 rounded-full bg-surface-gray-4" />

      <!-- Main actions -->
      <template v-if="!picking">
        <p
          class="truncate px-5 pb-1 pt-2 text-xs font-medium uppercase tracking-wide text-ink-gray-5"
        >
          {{ subject || __("Ticket actions") }}
        </p>
        <button class="sheet-btn" :disabled="busy" @click="assignToMe">
          <LucideUserPlus class="size-5 shrink-0 text-ink-gray-6" />
          {{ __("Assign to me") }}
        </button>
        <button class="sheet-btn" :disabled="busy" @click="openPicker">
          <LucideUsers class="size-5 shrink-0 text-ink-gray-6" />
          {{ __("Assign to someone") }}
          <LucideChevronRight class="ms-auto size-4 text-ink-gray-4" />
        </button>
        <button class="sheet-btn" :disabled="busy" @click="setStatus('Resolved')">
          <LucideCircleCheck class="size-5 shrink-0 text-ink-green-3" />
          {{ __("Resolve") }}
        </button>
        <button class="sheet-btn" :disabled="busy" @click="setStatus('Closed')">
          <LucideArchive class="size-5 shrink-0 text-ink-gray-6" />
          {{ __("Close") }}
        </button>
        <button class="sheet-btn" :disabled="busy" @click="setStatus('On Hold')">
          <LucidePause class="size-5 shrink-0 text-ink-amber-3" />
          {{ __("On hold") }}
        </button>
        <button
          class="w-full border-t border-outline-gray-1 py-3.5 text-center text-sm font-medium text-ink-gray-6"
          @click="emit('close')"
        >
          {{ __("Cancel") }}
        </button>
      </template>

      <!-- Assignee picker -->
      <template v-else>
        <div class="flex items-center gap-2 px-4 pb-1 pt-2">
          <button
            class="grid size-7 place-items-center rounded active:bg-surface-gray-2"
            @click="picking = false"
          >
            <LucideChevronLeft class="size-5 text-ink-gray-6" />
          </button>
          <span
            class="text-xs font-medium uppercase tracking-wide text-ink-gray-5"
          >
            {{ __("Assign to") }}
          </span>
        </div>
        <div class="max-h-[50vh] overflow-y-auto">
          <button
            v-for="a in agents"
            :key="a.name"
            class="sheet-btn"
            :disabled="busy"
            @click="assignTo(a.name)"
          >
            <span
              class="grid size-7 shrink-0 place-items-center rounded-full bg-surface-gray-2 text-xs font-medium text-ink-gray-7"
            >
              {{ initials(a.agent_name || a.name) }}
            </span>
            {{ a.agent_name || a.name }}
          </button>
          <p
            v-if="agentsResource.loading"
            class="py-4 text-center text-sm text-ink-gray-5"
          >
            {{ __("Loading…") }}
          </p>
          <p
            v-else-if="!agents.length"
            class="py-4 text-center text-sm text-ink-gray-5"
          >
            {{ __("No agents found") }}
          </p>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from "@/stores/auth";
import { __ } from "@/translation";
import { createResource } from "frappe-ui";
import { computed, ref } from "vue";
import LucideArchive from "~icons/lucide/archive";
import LucideChevronLeft from "~icons/lucide/chevron-left";
import LucideChevronRight from "~icons/lucide/chevron-right";
import LucideCircleCheck from "~icons/lucide/circle-check";
import LucidePause from "~icons/lucide/pause";
import LucideUserPlus from "~icons/lucide/user-plus";
import LucideUsers from "~icons/lucide/users";

const props = defineProps<{ ticket: string; subject?: string }>();
const emit = defineEmits<{ (e: "done"): void; (e: "close"): void }>();

const { userId } = useAuthStore();
const picking = ref(false);
const busy = ref(false);

const statusResource = createResource({
  url: "helpdesk.api.ticket.bulk_set_status",
});
const assignResource = createResource({ url: "frappe.desk.form.assign_to.add" });
const agentsResource = createResource({
  url: "frappe.client.get_list",
  makeParams: () => ({
    doctype: "HD Agent",
    fields: ["name", "agent_name"],
    filters: { is_active: 1 },
    order_by: "agent_name asc",
    limit_page_length: 0,
  }),
});
const agents = computed<any[]>(() => agentsResource.data || []);

function initials(name: string) {
  return (name || "?")
    .split(/[\s.@]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}

function openPicker() {
  picking.value = true;
  if (!agentsResource.data) agentsResource.fetch();
}

async function run(fn: () => Promise<any>) {
  if (busy.value) return;
  busy.value = true;
  try {
    await fn();
    emit("done");
  } catch {
    emit("close");
  } finally {
    busy.value = false;
  }
}

function setStatus(status: string) {
  run(() => statusResource.submit({ ticket_ids: [props.ticket], status }));
}
function assignToMe() {
  run(() =>
    assignResource.submit({
      doctype: "HD Ticket",
      name: props.ticket,
      assign_to: [userId],
    })
  );
}
function assignTo(agent: string) {
  run(() =>
    assignResource.submit({
      doctype: "HD Ticket",
      name: props.ticket,
      assign_to: [agent],
    })
  );
}
</script>

<style scoped>
.sheet-btn {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  text-align: left;
  font-size: 15px;
  color: var(--ink-gray-8);
}
.sheet-btn:active {
  background: var(--surface-gray-2);
}
.sheet-btn:disabled {
  opacity: 0.5;
}
</style>
