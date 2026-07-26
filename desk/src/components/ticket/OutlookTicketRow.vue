<template>
  <!-- Outlook-inbox style row. The left line is an Outlook-style status
       indicator (blue = open/needs our reply, red = urgent, grey = automated
       no-reply/notification mail, none = we've replied & are waiting). Then a
       3-line block (requester + date / priority + subject + status / preview
       snippet + due date + assignee). Bold when unread for the current agent. -->
  <div class="relative overflow-hidden border-b border-outline-gray-1">
    <!-- Swipe hint (mobile only), behind the sliding row on the right. Swiping
         the row left reveals it; releasing past the threshold opens the action
         sheet (Assign / Resolve / Close / On hold). -->
    <div
      v-if="isMobileView"
      v-show="offset < 0"
      class="absolute inset-y-0 right-0 flex items-center justify-end gap-1.5 pr-5 text-sm font-medium text-white"
      :style="{ backgroundColor: '#1B2A4A', width: MAX_DRAG + 'px' }"
    >
      <LucideMoreHorizontal class="size-5 shrink-0" />
      Actions
    </div>

    <!-- Sliding foreground = the ticket row (opaque so it covers the panels
         when closed). -->
    <div
      class="relative flex cursor-pointer items-stretch"
      :class="
        selected
          ? 'bg-surface-blue-1'
          : 'bg-surface-white hover:bg-surface-gray-2'
      "
      :style="foregroundStyle"
      @click="onRowClick"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerEnd"
      @pointercancel="onPointerEnd"
    >
      <!-- Status line (Outlook-style; transparent when no action is pending so
           the row stays aligned but shows no bar). -->
      <div
        class="w-1 shrink-0"
        :style="{ backgroundColor: stripColor }"
        :title="stripTitle"
      />

    <!-- Select checkbox (tap to select without opening the ticket). Wide,
         full-height tap target so it's easy to hit and won't open the ticket. -->
    <button
      type="button"
      role="checkbox"
      class="grid shrink-0 place-items-center px-3"
      :aria-label="selected ? 'Deselect ticket' : 'Select ticket'"
      :aria-checked="selected"
      @click.stop="$emit('toggle')"
    >
      <span
        class="grid size-5 place-items-center rounded-md border transition"
        :class="
          selected
            ? 'border-transparent bg-surface-blue-5 text-white'
            : 'border-outline-gray-4'
        "
      >
        <LucideCheck v-if="selected" class="size-3.5" />
      </span>
    </button>

    <div class="flex min-w-0 flex-1 flex-col gap-0.5 py-2.5 pl-1 pr-4">
      <!-- Line 1: requester + date -->
      <div class="flex items-center gap-2">
        <span
          class="min-w-0 flex-1 truncate text-sm text-ink-gray-8"
          :class="unread ? 'font-semibold' : 'font-medium'"
        >
          {{ requester }}
        </span>
        <span class="shrink-0 text-xs text-ink-gray-5">{{ dateLabel }}</span>
      </div>

      <!-- Line 2: priority indicator + subject + status pill -->
      <div class="flex items-center gap-2">
        <span
          v-if="isHighPriority"
          class="size-2 shrink-0 rounded-full"
          :style="{ backgroundColor: priorityColor }"
          :title="row.priority"
        />
        <span
          class="min-w-0 flex-1 truncate text-sm"
          :class="unread ? 'font-semibold text-ink-gray-9' : 'text-ink-gray-7'"
        >
          {{ row.subject || __("(No subject)") }}
        </span>
        <Badge
          v-if="statusLabel && !isMobileView"
          class="shrink-0"
          :label="statusLabel"
          :theme="statusTheme"
          variant="subtle"
        />
      </div>

      <!-- Line 3: preview snippet + due date + assignee avatar -->
      <div class="flex items-center gap-2">
        <span class="min-w-0 flex-1 truncate text-xs text-ink-gray-5">
          {{ snippet }}
        </span>
        <Badge
          v-if="dueLabel && !isMobileView"
          class="shrink-0"
          :label="dueLabel"
          :theme="dueTheme"
          variant="subtle"
        />
        <MultipleAvatar
          v-if="row._assign"
          class="shrink-0"
          :avatars="row._assign"
          :hide-name="true"
        />
      </div>
    </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { MultipleAvatar } from "@/components";
import { useScreenSize } from "@/composables/screen";
import { useAuthStore } from "@/stores/auth";
import { useTicketStatusStore } from "@/stores/ticketStatus";
import { __ } from "@/translation";
import { Badge, dayjs } from "frappe-ui";
import { computed, ref } from "vue";
import LucideCheck from "~icons/lucide/check";
import LucideMoreHorizontal from "~icons/lucide/more-horizontal";

const props = defineProps<{ row: Record<string, any>; selected?: boolean }>();
const emit = defineEmits<{
  (e: "click"): void;
  (e: "toggle"): void;
  (e: "actions"): void;
}>();

const { userId } = useAuthStore();
const { getStatus } = useTicketStatusStore();
const { isMobileView } = useScreenSize();

// --- Swipe-left to open the action sheet (mobile only) --------------------
// Left-drag reveals the "Actions" hint; releasing past OPEN_AT opens the
// bottom action sheet (rendered by the parent list). touch-action:pan-y + a
// horizontal/vertical direction lock so it never fights vertical scrolling.
// Sensitivity: needs DECIDE_AT px of clearly-horizontal, leftward movement to
// engage and OPEN_AT px of travel to fire. Desktop untouched (off mobile).
const MAX_DRAG = 120;
const OPEN_AT = 70;
const DECIDE_AT = 20;
const offset = ref(0);
const dragging = ref(false);
let startX = 0;
let startY = 0;
let active = false;
let decided = false;
let horizontal = false;
let moved = false;

const foregroundStyle = computed(() =>
  isMobileView.value
    ? {
        transform: `translateX(${offset.value}px)`,
        transition: dragging.value ? "none" : "transform 0.2s ease",
        touchAction: "pan-y",
        // Opaque + stacked ABOVE the hint, so at rest the row looks normal.
        position: "relative",
        zIndex: 1,
        backgroundColor: props.selected
          ? "var(--surface-blue-1)"
          : "var(--surface-white)",
      }
    : {}
);

function onPointerDown(e: PointerEvent) {
  if (!isMobileView.value) return;
  active = true;
  decided = false;
  horizontal = false;
  moved = false;
  startX = e.clientX;
  startY = e.clientY;
}
function onPointerMove(e: PointerEvent) {
  if (!active) return;
  const dx = e.clientX - startX;
  const dy = e.clientY - startY;
  if (!decided) {
    if (Math.abs(dx) < DECIDE_AT && Math.abs(dy) < DECIDE_AT) return;
    // Only engage on a clearly-horizontal, LEFTWARD drag; otherwise release so
    // the list scrolls vertically as normal.
    if (Math.abs(dx) > Math.abs(dy) && dx < 0) {
      decided = true;
      horizontal = true;
      dragging.value = true;
      try {
        (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
      } catch {
        /* noop */
      }
    } else {
      active = false;
      return;
    }
  }
  moved = true;
  offset.value = Math.max(-MAX_DRAG, Math.min(0, dx)); // left only
}
function onPointerEnd() {
  const wasHorizontal = horizontal;
  const traveled = offset.value;
  active = false;
  dragging.value = false;
  decided = false;
  horizontal = false;
  offset.value = 0; // always snap back; the sheet is the "open" state
  if (wasHorizontal && traveled <= -OPEN_AT) emit("actions");
}
function onRowClick() {
  if (moved) {
    moved = false;
    return; // swallow the click that follows a swipe
  }
  emit("click");
}

// --- Outlook-style left status line ---------------------------------------
// Precedence (Mark's spec, 2026-07-25):
//   grey  = automated / no-reply / notification sender (de-emphasized; WINS
//           even when the sender's mail is auto-flagged Urgent, e.g. the UniFi
//           camera "gone offline" alerts)
//   red   = Urgent (from a real sender)
//   blue  = Open / needs our first response (ball in our court)
//   none  = we've replied & are waiting on the customer, or the ticket is
//           resolved / closed / on hold (no bar, Outlook-style)
// Notification sender detection mirrors the enricher's is_ai_excluded
// substring match (config.py) so the UI and the AI-exclusion logic agree.
const NOTIFICATION_SENDER_PATTERNS = [
  "noreply",
  "no-reply",
  "no_reply",
  "donotreply",
  "do-not-reply",
  "do_not_reply",
  "notification",
  "notifications",
  "mailer-daemon",
  "postmaster",
  "bounce",
];
const isNotificationSender = computed(() => {
  const from = (props.row.raised_by || "").toLowerCase();
  return !!from && NOTIFICATION_SENDER_PATTERNS.some((p) => from.includes(p));
});
const isUrgent = computed(() => props.row.priority === "Urgent");
// Statuses where the ball is in OUR court (unreplied / needs a response).
const NEEDS_ACTION_STATUSES = new Set(["Open", "Escalated"]);
const needsAction = computed(() =>
  NEEDS_ACTION_STATUSES.has(props.row.status)
);

const stripColor = computed(() => {
  if (isNotificationSender.value) return "#94A3B8"; // grey
  if (isUrgent.value) return "#E03434"; // red
  if (needsAction.value) return "#2563EB"; // blue
  return "transparent"; // replied / waiting / done → no bar
});
const stripTitle = computed(() => {
  if (isNotificationSender.value) return "Automated / no-reply";
  if (isUrgent.value) return "Urgent";
  if (needsAction.value) return "Open — needs a response";
  return "Waiting on customer / no action needed";
});

// --- Unread (per-agent, from the framework-maintained _seen array) ---
const unread = computed(() => {
  try {
    const seen = props.row._seen ? JSON.parse(props.row._seen) : [];
    return !seen.includes(userId || "");
  } catch {
    return false;
  }
});

// --- Requester ---
const requester = computed(
  () => props.row.contact || props.row.raised_by || "—"
);

// --- Date (Outlook-style: time today, month/day this year, else short date) ---
const dateLabel = computed(() => {
  if (!props.row.modified) return "";
  const d = dayjs(props.row.modified);
  const now = dayjs();
  if (d.isSame(now, "day")) return d.format("h:mm A");
  if (d.isSame(now, "year")) return d.format("MMM D");
  return d.format("M/D/YY");
});

// --- Priority indicator ---
const PRIORITY_COLORS: Record<string, string> = {
  Urgent: "#E03434",
  High: "#E86C13",
  Medium: "#64748B",
  Low: "#CBD5E1",
};
const priorityColor = computed(
  () => PRIORITY_COLORS[props.row.priority] || "#CBD5E1"
);
// Only surface the priority dot when it's actionable (High/Urgent) — Medium/Low
// dots showed on nearly every row and just added noise.
const isHighPriority = computed(() =>
  ["High", "Urgent"].includes(props.row.priority)
);

// --- Status pill ---
const STATUS_THEME: Record<string, string> = {
  Open: "blue",
  Replied: "green",
  Resolved: "green",
  Closed: "gray",
  "Waiting on Customer": "orange",
  "On Hold": "gray",
  Escalated: "red",
};
const statusLabel = computed(
  () => getStatus(props.row.status)?.label_agent || props.row.status || ""
);
const statusTheme = computed(() => STATUS_THEME[props.row.status] || "gray");

// --- Due date (AI-enriched `pyek_requested_due_date`; replaces the old SLA
// badge). Shown only when a due date is set; turns red once overdue and
// orange when due today/tomorrow, so the deadline still reads at a glance. ---
const dueLabel = computed(() => {
  if (!props.row.pyek_requested_due_date) return "";
  const d = dayjs(props.row.pyek_requested_due_date);
  const now = dayjs();
  let when: string;
  if (d.isSame(now, "day")) when = "Today";
  else if (d.isSame(now.add(1, "day"), "day")) when = "Tomorrow";
  else if (d.isSame(now, "year")) when = d.format("MMM D");
  else when = d.format("M/D/YY");
  return `Due ${when}`;
});
const dueTheme = computed(() => {
  if (!props.row.pyek_requested_due_date) return "gray";
  const d = dayjs(props.row.pyek_requested_due_date).startOf("day");
  const today = dayjs().startOf("day");
  if (d.isBefore(today)) return "red"; // overdue
  if (d.diff(today, "day") <= 1) return "orange"; // due today/tomorrow
  return "gray";
});

// --- Preview snippet: the latest email in the thread (Outlook-style), provided
// pre-stripped by the backend as `_last_message`; falls back to the ticket
// description (HTML) when there are no email communications yet. ---
const snippet = computed(() => {
  if (props.row._last_message) return props.row._last_message;
  const html = props.row.description;
  if (!html) return "";
  const el = document.createElement("div");
  el.innerHTML = html;
  // Drop <style>/<script> so their CSS/JS text (e.g. Outlook VML) doesn't leak
  // into the preview — textContent would otherwise include it.
  el.querySelectorAll("style, script").forEach((n) => n.remove());
  return (el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 160);
});
</script>
