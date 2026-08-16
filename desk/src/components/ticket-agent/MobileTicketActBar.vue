<template>
  <!-- One-thumb act bar (PYEK): a push lands, the ticket opens, and the screen
       is already primed to act — take it, resolve it, or open the same action
       sheet the list swipe uses. Sits in the sticky footer ABOVE the composer
       prompt and steps aside (parent v-show) while an editor is open. -->
  <!-- v-show lives HERE, not on the component tag: this component has two
       roots (bar + sheet), and v-show on a fragment component silently does
       nothing. The bar steps aside while either editor is open. -->
  <div
    v-if="ticketDoc?.name"
    v-show="!suppressed"
    class="flex items-center gap-2 border-t px-3 py-1.5"
  >
    <!-- SLA countdown: the reason the push was worth acting on. Hidden once
         resolved, and once a breach is older than a day it is history, not a
         call to action — the dashboard already learned that lesson. -->
    <span
      v-if="slaChip"
      class="truncate rounded-full px-2 py-0.5 text-xs font-medium"
      :class="slaChip.cls"
    >
      {{ slaChip.text }}
    </span>
    <div class="ms-auto flex shrink-0 items-center gap-1.5">
      <!-- Reply is THE primary action (Mark's reply-flow pick #2, 2026-08-15):
           it opens the chat-style quick bar, which self-assigns on send — so
           on unassigned tickets it subsumes "Take it" and earns its slot. -->
      <Button variant="solid" :label="__('Reply')" @click="emit('reply')">
        <template #prefix>
          <LucideReply class="size-4" />
        </template>
      </Button>
      <Button
        v-if="!isMine"
        :label="__('Take it')"
        :loading="taking"
        @click="takeIt"
      >
        <template #prefix>
          <LucideUserPlus class="size-4" />
        </template>
      </Button>
      <Button
        v-if="canResolve"
        :label="__('Resolve')"
        :loading="resolving"
        @click="resolve"
      >
        <template #prefix>
          <LucideCircleCheck class="size-4 text-ink-green-3" />
        </template>
      </Button>
      <Button :aria-label="__('More actions')" @click="sheetOpen = true">
        <template #icon>
          <LucideMoreHorizontal class="size-4" />
        </template>
      </Button>
    </div>
  </div>
  <TicketActionSheet
    v-if="sheetOpen"
    :ticket="ticketDoc.name"
    :subject="ticketDoc.subject"
    :assign="ticketDoc._assign"
    @done="onSheetDone"
    @close="sheetOpen = false"
  />
</template>

<script setup lang="ts">
import TicketActionSheet from "@/components/ticket/TicketActionSheet.vue";
import { parseAssign, selfAssignTicket } from "@/composables/selfAssign";
import { useTicketStatusStore } from "@/stores/ticketStatus";
import { __ } from "@/translation";
import { AssigneeSymbol, TicketSymbol } from "@/types";
import { Button, toast } from "frappe-ui";
import { computed, inject, onMounted, onUnmounted, ref } from "vue";
import LucideCircleCheck from "~icons/lucide/circle-check";
import LucideMoreHorizontal from "~icons/lucide/more-horizontal";
import LucideReply from "~icons/lucide/reply";
import LucideUserPlus from "~icons/lucide/user-plus";

// Hidden while the reply flow (quick bar / full composer) is open. The signal
// arrives as a prop now — the module-level showEmailBox/showCommentBox refs
// this used to read are desktop-only state since the mobile reply redesign.
defineProps({
  suppressed: {
    type: Boolean,
    default: false,
  },
});
const emit = defineEmits(["reply"]);

const ticket = inject(TicketSymbol)!;
const assignees = inject(AssigneeSymbol, null);
const refreshTicket = inject<() => void>("refreshTicket", () => {});
const ticketStatusStore = useTicketStatusStore();

const sheetOpen = ref(false);
const taking = ref(false);
const resolving = ref(false);

const ticketDoc = computed(() => ticket.value?.doc);

const assignedNames = computed<string[]>(() => {
  const fetched = assignees?.value?.data;
  if (Array.isArray(fetched)) return fetched.map((a: any) => a.name);
  return parseAssign(ticketDoc.value?._assign);
});

const isMine = computed(
  () => !!window.agent && assignedNames.value.includes(window.agent)
);

const canResolve = computed(() => {
  const status = ticketDoc.value?.status;
  if (!status) return false;
  return ticketStatusStore.getStatus(status)?.category !== "Resolved";
});

// --- SLA countdown -----------------------------------------------------------
// Re-render every 30s so the chip counts down while the screen stays open.
const now = ref(Date.now());
let timer: ReturnType<typeof setInterval> | null = null;
onMounted(() => {
  timer = setInterval(() => (now.value = Date.now()), 30_000);
});
onUnmounted(() => {
  if (timer) clearInterval(timer);
});

// Frappe datetimes are site-local "YYYY-MM-DD HH:mm:ss" strings; Safari wants
// the T separator. Agents and the site share US Central, so local parse is
// the right reading.
function parseFrappeDate(value: string): number {
  return new Date(value.replace(" ", "T")).getTime();
}

function fmtSpan(ms: number): string {
  const mins = Math.max(1, Math.round(ms / 60_000));
  if (mins < 60) return `${mins}m`;
  const h = Math.floor(mins / 60);
  if (h >= 48) {
    const d = Math.floor(h / 24);
    const rh = h % 24;
    return rh ? `${d}d ${rh}h` : `${d}d`;
  }
  const m = mins % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

const slaChip = computed(() => {
  const doc = ticketDoc.value;
  if (!doc || !canResolve.value) return null;
  const target =
    !doc.first_responded_on && doc.response_by
      ? { by: doc.response_by, verb: __("Reply") }
      : doc.resolution_by
      ? { by: doc.resolution_by, verb: __("Resolve") }
      : null;
  if (!target) return null;
  const diff = parseFrappeDate(target.by) - now.value;
  if (diff >= 0) {
    return {
      text: `${target.verb} ${__("due in")} ${fmtSpan(diff)}`,
      cls:
        diff < 2 * 3600_000
          ? "bg-surface-amber-2 text-ink-amber-6"
          : "bg-surface-gray-2 text-ink-gray-7",
    };
  }
  // A breach older than a day is history, not something a thumb can rescue.
  if (-diff > 24 * 3600_000) return null;
  return {
    text: `${target.verb} ${__("overdue")} ${fmtSpan(-diff)}`,
    cls: "bg-surface-red-1 text-ink-red-6",
  };
});

// --- Actions -----------------------------------------------------------------

async function takeIt() {
  if (taking.value) return;
  taking.value = true;
  try {
    await selfAssignTicket(String(ticketDoc.value.name));
    toast.success(__("Ticket is yours."));
    refreshTicket();
  } catch {
    toast.error(__("Could not assign the ticket."));
  } finally {
    taking.value = false;
  }
}

async function resolve() {
  if (resolving.value) return;
  resolving.value = true;
  try {
    // Acting = taking it: resolving an unassigned ticket claims it first.
    if (!assignedNames.value.length) {
      await selfAssignTicket(String(ticketDoc.value.name));
    }
    await ticket.value.setValue.submit({ status: "Resolved" });
    refreshTicket();
  } catch {
    toast.error(__("Could not resolve the ticket."));
  } finally {
    resolving.value = false;
  }
}

function onSheetDone() {
  sheetOpen.value = false;
  refreshTicket();
}
</script>
