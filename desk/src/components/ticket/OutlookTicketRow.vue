<template>
  <!-- Outlook-inbox style row. The left line is an Outlook-style status
       indicator (blue = open/needs our reply, red = urgent, grey = automated
       no-reply/notification mail, none = we've replied & are waiting). Then a
       3-line block (requester + date / priority + subject + status / preview
       snippet + due date + assignee). Bold when unread for the current agent. -->
  <div
    class="relative flex cursor-pointer items-stretch border-b border-outline-gray-1 transition"
    :class="selected ? 'bg-surface-blue-1' : 'hover:bg-surface-gray-2'"
    @click="$emit('click')"
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
          v-if="unread"
          class="size-2 shrink-0 rounded-full bg-surface-blue-5"
          title="Unread"
        />
        <span
          class="min-w-0 flex-1 truncate text-sm text-ink-gray-8"
          :class="unread ? 'font-semibold' : 'font-medium'"
        >
          {{ requester }}
        </span>
        <span
          v-if="isMobileView"
          class="size-2 shrink-0 rounded-full"
          :style="{ backgroundColor: statusDotColor }"
          :title="statusLabel"
        />
        <span class="shrink-0 text-xs text-ink-gray-5">{{ dateLabel }}</span>
      </div>

      <!-- Line 2: priority indicator + subject + status pill -->
      <div class="flex items-center gap-2">
        <span
          class="size-2 shrink-0 rounded-full"
          :style="{ backgroundColor: priorityColor }"
          :title="row.priority || 'No priority'"
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
</template>

<script setup lang="ts">
import { MultipleAvatar } from "@/components";
import { useScreenSize } from "@/composables/screen";
import { useAuthStore } from "@/stores/auth";
import { useTicketStatusStore } from "@/stores/ticketStatus";
import { __ } from "@/translation";
import { Badge, dayjs } from "frappe-ui";
import { computed } from "vue";
import LucideCheck from "~icons/lucide/check";

const props = defineProps<{ row: Record<string, any>; selected?: boolean }>();
defineEmits<{ (e: "click"): void; (e: "toggle"): void }>();

const { userId } = useAuthStore();
const { getStatus } = useTicketStatusStore();
const { isMobileView } = useScreenSize();

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

// On phones the text pill is shown as a compact colored dot to save row width.
const STATUS_DOT: Record<string, string> = {
  Open: "#2563EB",
  Replied: "#16A34A",
  Resolved: "#16A34A",
  Closed: "#64748B",
  "Waiting on Customer": "#D97706",
  "On Hold": "#64748B",
  Escalated: "#E03434",
};
const statusDotColor = computed(
  () => STATUS_DOT[props.row.status] || "#94A3B8"
);

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
  return (el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 160);
});
</script>
