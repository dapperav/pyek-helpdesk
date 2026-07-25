<template>
  <!-- Outlook-inbox style row: park color strip on the left edge, then a
       3-line block (requester + date / priority + subject + status / preview
       snippet + SLA + assignee). Bold when unread for the current agent. -->
  <div
    class="relative flex cursor-pointer items-stretch border-b border-outline-gray-1 transition"
    :class="selected ? 'bg-surface-blue-1' : 'hover:bg-surface-gray-2'"
    @click="$emit('click')"
  >
    <!-- Park color strip (stays at the very left edge) -->
    <div
      class="w-1 shrink-0"
      :style="{ backgroundColor: stripColor }"
      :title="park"
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

      <!-- Line 3: preview snippet + SLA badge + assignee avatar -->
      <div class="flex items-center gap-2">
        <span class="min-w-0 flex-1 truncate text-xs text-ink-gray-5">
          {{ snippet }}
        </span>
        <Badge
          v-if="slaTheme && !isMobileView"
          class="shrink-0"
          :label="__(row.agreement_status)"
          :theme="slaTheme"
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
import { parkColor, parkLabel } from "@/config/parks";
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

// --- Park strip ---
const park = computed(() => parkLabel(props.row.pyek_property));
const stripColor = computed(() => parkColor(park.value));

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

// --- SLA badge (only the actionable states; hide Fulfilled/Paused/empty) ---
const SLA_THEME: Record<string, string> = {
  Failed: "red",
  "First Response Due": "orange",
  "Resolution Due": "orange",
};
const slaTheme = computed(() => SLA_THEME[props.row.agreement_status] || null);

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
