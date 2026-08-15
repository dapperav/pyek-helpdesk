<template>
  <!-- Outlook-inbox style row (desktop + AP) or a "Clean Card" (mobile IT/HR —
       Mark's V1 pick, 2026-08-15). The old left status line survives in both:
       as the stripe on the row, and as the card's colored EDGE (blue =
       open/needs our reply, red = urgent, grey = automated no-reply mail,
       none = we've replied & are waiting). Bold when unread for the agent. -->
  <div
    class="relative"
    :class="isCard ? 'shrink-0' : 'overflow-hidden border-b border-outline-gray-1'"
  >
    <!-- Swipe hint (mobile only), behind the sliding row on the right. Swiping
         the row left reveals it; releasing past the threshold opens the action
         sheet (Assign / Resolve / Close / On hold). -->
    <button
      v-if="isMobileView"
      v-show="offset < 0"
      type="button"
      class="absolute inset-y-0 right-0 flex items-center justify-center gap-1.5 text-sm font-medium text-white"
      :class="isCard ? 'rounded-[14px]' : ''"
      :style="{ backgroundColor: '#1B2A4A', width: REVEAL + 'px' }"
      aria-label="Ticket actions"
      @click.stop="openSheet"
    >
      <LucideMoreHorizontal class="size-5 shrink-0" />
      Actions
    </button>

    <!-- ============ CLEAN CARD (mobile, IT/HR) ============ -->
    <div
      v-if="isCard"
      class="relative cursor-pointer select-none overflow-hidden rounded-[14px] border border-[#dbe7f0] py-[11px] pl-4 pr-[13px] shadow-[0_3px_12px_rgba(18,54,94,0.06)]"
      :style="foregroundStyle"
      @click="onRowClick"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerEnd"
      @pointercancel="onPointerEnd"
    >
      <!-- The old Outlook stripe, promoted to the card edge. -->
      <span
        class="absolute inset-y-0 left-0 w-1"
        :class="edgeClass"
        :title="stripTitle"
      />
      <div :class="isNotificationSender ? 'opacity-70' : ''">
        <!-- Sender leads: avatar doubles as the select checkbox. -->
        <div class="mb-1 flex items-center gap-2">
          <button
            type="button"
            role="checkbox"
            class="grid size-[30px] shrink-0 place-items-center rounded-full text-[11px] font-bold"
            :class="
              selected
                ? 'bg-surface-blue-5 text-white'
                : isNotificationSender
                ? 'bg-[#eef2f6] text-[#94a3b8]'
                : 'bg-gradient-to-b from-[#e0f6ff] to-[#bfeefb] text-[#0b6e8f]'
            "
            :aria-label="selected ? 'Deselect ticket' : 'Select ticket'"
            :aria-checked="selected"
            @click.stop="$emit('toggle')"
          >
            <LucideCheck v-if="selected" class="size-4" />
            <template v-else>{{ initials }}</template>
          </button>
          <span class="min-w-0 flex-1">
            <span
              class="block truncate text-[12.5px] font-semibold"
              :class="isNotificationSender ? 'text-[#64748b]' : 'text-[#12365e]'"
            >{{ cardName }}</span>
            <span
              v-if="cardVia"
              class="block truncate text-[10.5px] text-[#7d9ab5]"
            >{{ cardVia }}</span>
          </span>
          <span class="shrink-0 self-start pt-0.5 text-[10.5px] text-[#7d9ab5]">
            {{ dateLabel }}
          </span>
        </div>

        <!-- Subject: the unread signal lives here. -->
        <div class="flex items-center gap-1.5">
          <span
            v-if="row.priority === 'High'"
            class="size-2 shrink-0 rounded-full"
            :style="{ backgroundColor: priorityColor }"
            :title="row.priority"
          />
          <span
            class="min-w-0 flex-1 truncate text-sm"
            :class="[
              unread ? 'font-semibold' : 'font-medium',
              isNotificationSender ? 'text-[#475569]' : 'text-[#12365e]',
            ]"
          >{{ row.subject || __("(No subject)") }}</span>
        </div>

        <!-- AI summary (or the requester's words) — bots don't get one. -->
        <div
          v-if="!isNotificationSender && (aiSummary || snippet)"
          class="pyek-clamp2 mt-0.5 text-[12.5px] leading-snug text-[#48708f]"
        >{{ aiSummary || snippet }}</div>

        <!-- Footer: queue tag + one chip (SLA clock when running, else
             status) + assignees + the ticket number riding quietly. -->
        <div class="mt-2 flex items-center gap-1.5">
          <span v-if="queueTag" class="pyek-qtag" :class="queueTag.cls">{{
            queueTag.label
          }}</span>
          <span v-if="cardChip" class="pyek-schip truncate" :class="cardChip.cls">{{
            cardChip.text
          }}</span>
          <span class="ml-auto flex shrink-0 items-center gap-1.5">
            <MultipleAvatar
              v-if="row._assign"
              :avatars="row._assign"
              :hide-name="true"
            />
            <span class="text-[10px] font-bold tracking-[0.08em] text-[#a8bccd]"
              >#{{ row.name }}</span
            >
          </span>
        </div>
      </div>
    </div>

    <!-- ============ OUTLOOK ROW (desktop + AP) ============ -->
    <!-- Sliding foreground = the ticket row (opaque so it covers the panels
         when closed). -->
    <div
      v-else
      class="relative flex cursor-pointer items-stretch"
      :class="
        selected
          ? 'bg-surface-blue-1'
          : 'bg-surface-base hover:bg-surface-gray-2'
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
      <!-- PYEK-AP: each row leads with a small CONTACT CARD (avatar/photo +
           sender name + email + park), then subject + status/flags on the
           right. Internal (@pyek) senders show their M365 profile photo when
           the enricher has populated ap_sender_photo; everyone else = initials.
           Non-AP (IT/HR) keeps the original 3-line Outlook layout below. -->
      <template v-if="isAP">
        <div class="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:gap-3">
          <!-- Contact card -->
          <div class="flex min-w-0 items-center gap-2.5 sm:flex-1">
            <img
              v-if="senderPhoto"
              :src="senderPhoto"
              :alt="senderName"
              class="size-9 shrink-0 rounded-full object-cover"
            />
            <div
              v-else
              class="grid size-9 shrink-0 place-items-center rounded-full bg-surface-gray-3 text-xs font-medium text-ink-gray-7"
            >{{ initials }}</div>
            <div class="min-w-0">
              <div
                class="truncate text-sm text-ink-gray-8"
                :class="unread ? 'font-semibold' : 'font-medium'"
              >{{ senderName }}</div>
              <div class="truncate text-xs text-ink-gray-5">{{ senderEmail }}</div>
              <div class="truncate text-xs text-ink-gray-5">{{ row.subject || __("(No subject)") }}</div>
            </div>
          </div>
          <!-- Park + amount, then status / due / flags -->
          <div class="flex min-w-0 flex-col gap-1 sm:flex-1">
            <div class="flex items-center gap-2">
              <span
                v-if="isHighPriority"
                class="size-2 shrink-0 rounded-full"
                :style="{ backgroundColor: priorityColor }"
                :title="row.priority"
              />
              <span
                v-if="park"
                class="shrink-0 rounded border border-outline-gray-3 px-1.5 py-px text-[10px] font-medium leading-4 text-ink-gray-6"
              >{{ park }}</span>
              <span
                v-if="amountLabel !== '—'"
                class="min-w-0 flex-1 truncate text-sm font-medium text-ink-gray-8"
                :class="unread ? 'font-semibold' : ''"
              >{{ amountLabel }}</span>
            </div>
            <div class="flex flex-wrap items-center gap-1.5">
              <Badge
                v-if="statusLabel"
                class="shrink-0"
                :label="statusLabel"
                :theme="statusTheme"
                variant="subtle"
              />
              <Badge
                v-if="dueLabel"
                class="shrink-0"
                :label="dueLabel"
                :theme="dueTheme"
                variant="subtle"
              />
              <Badge
                v-for="f in apFlags"
                :key="f.label"
                class="shrink-0"
                :label="f.label"
                :theme="f.theme"
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

      <template v-else>
        <!-- Line 1: requester + date -->
        <div class="flex items-center gap-2">
          <span
            class="min-w-0 flex-1 truncate text-sm text-ink-gray-8"
            :class="unread ? 'font-semibold' : 'font-medium'"
          >{{ requester }}</span>
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
          >{{ row.subject || __("(No subject)") }}</span>
          <Badge
            v-if="statusLabel && !isMobileView"
            class="shrink-0"
            :label="statusLabel"
            :theme="statusTheme"
            variant="subtle"
          />
        </div>

        <!-- Line 3: main preview (AI summary when the enricher has one, else the
             snippet) + due badge + assignee -->
        <div class="flex items-center gap-2">
          <span class="min-w-0 flex-1 truncate text-xs text-ink-gray-5">{{
            aiSummary || snippet
          }}</span>
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

        <!-- Line 4 (only when a summary led line 3): the requester's own words,
             verbatim, one shade fainter — Mark's "summary + sender's words". -->
        <div v-if="aiSummary && snippet" class="flex items-center gap-2">
          <span class="min-w-0 flex-1 truncate text-xs text-ink-gray-4">
            &ldquo;{{ snippet }}&rdquo;
          </span>
        </div>
      </template>
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

// --- Swipe-left to REVEAL an "Actions" button (mobile only) ----------------
// Left-drag reveals the "Actions" button and HOLDS it open — it does NOT open
// the sheet on its own. Tapping the revealed button opens the action sheet;
// tapping the row closes it. touch-action:pan-y + a horizontal/vertical
// direction lock so it never fights vertical scroll. Desktop untouched.
const REVEAL = 112; // held-open offset + width of the Actions button
const OPEN_AT = 56; // release past this (left) snaps to held-open
const DECIDE_AT = 20; // clearly-horizontal travel before the drag engages
const offset = ref(0);
const dragging = ref(false);
let startX = 0;
let startY = 0;
let base = 0;
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
        backgroundColor: props.selected ? "var(--surface-blue-1)" : "#ffffff",
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
  base = offset.value; // start from the current (possibly held-open) position
}
function onPointerMove(e: PointerEvent) {
  if (!active) return;
  const dx = e.clientX - startX;
  const dy = e.clientY - startY;
  if (!decided) {
    if (Math.abs(dx) < DECIDE_AT && Math.abs(dy) < DECIDE_AT) return;
    // Engage only on a clearly-horizontal drag; otherwise release so the list
    // scrolls vertically as normal.
    if (Math.abs(dx) > Math.abs(dy)) {
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
  offset.value = Math.max(-REVEAL, Math.min(0, base + dx)); // clamp to reveal
}
function onPointerEnd() {
  const wasHorizontal = horizontal;
  active = false;
  dragging.value = false;
  decided = false;
  horizontal = false;
  if (!wasHorizontal) return;
  // Snap to held-open (showing the Actions button) or fully closed.
  offset.value = offset.value <= -OPEN_AT ? -REVEAL : 0;
}
function onRowClick() {
  if (moved) {
    moved = false;
    return; // swallow the click that follows a swipe
  }
  if (offset.value !== 0) {
    offset.value = 0; // tap on an open row just closes it
    return;
  }
  emit("click");
}
function openSheet() {
  offset.value = 0;
  emit("actions");
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

// --- Clean Card (mobile IT/HR — Mark's V1 pick over the Ticket Stub) --------
// Same precedence as the stripe, worn as the card's left edge.
const isCard = computed(() => isMobileView.value && !isAP.value);
const edgeClass = computed(() => {
  if (isNotificationSender.value) return "pyek-edge--grey";
  if (isUrgent.value) return "pyek-edge--red";
  if (needsAction.value) return "pyek-edge--blue";
  return "";
});

// Sender-first header: person (or bot) name, then the address it came from.
const cardName = computed(
  () => props.row.contact || (props.row.raised_by || "").split("@")[0] || "—"
);
const cardVia = computed(() => {
  if (isNotificationSender.value) return __("automated");
  const email = props.row.raised_by || "";
  return email && email !== cardName.value ? email : "";
});

// Queue tag (POS / IT), from the ticket's team.
const queueTag = computed(() => {
  const group = (props.row.agent_group || "").trim();
  if (!group) return null;
  const word = group.split(/\s+/)[0].toUpperCase();
  if (word.startsWith("POS")) return { label: "POS", cls: "pyek-qtag--pos" };
  if (word === "IT") return { label: "IT", cls: "pyek-qtag--it" };
  return { label: word, cls: "pyek-qtag--other" };
});

// One chip: the SLA clock while it's running (list edition of
// MobileTicketActBar's slaChip), else the status. A breach older than a day
// is history, not a call to action — same rule as the act bar.
function parseFrappeDate(value: string): number {
  // Frappe datetimes are site-local "YYYY-MM-DD HH:mm:ss"; Safari wants the T.
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
const cardChip = computed(() => {
  if (
    needsAction.value &&
    !isNotificationSender.value &&
    !props.row.first_responded_on &&
    props.row.response_by
  ) {
    const diff = parseFrappeDate(props.row.response_by) - Date.now();
    // A deadline beyond a week (some SLAs hand out year-long response
    // windows) isn't a running clock worth a chip — show the status instead.
    if (diff >= 0 && diff <= 7 * 24 * 3600_000) {
      return {
        text: `${__("reply due")} ${fmtSpan(diff)}`,
        cls: diff < 2 * 3600_000 ? "pyek-schip--due" : "pyek-schip--wait",
      };
    }
    if (diff < 0 && -diff <= 24 * 3600_000) {
      return {
        text: `${__("reply overdue")} ${fmtSpan(-diff)}`,
        cls: "pyek-schip--due",
      };
    }
  }
  const label = (statusLabel.value || "").toLowerCase();
  if (!label) return null;
  return {
    text: label,
    cls: needsAction.value ? "pyek-schip--open" : "pyek-schip--wait",
  };
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

// --- AI summary: the enricher's pyek_summary, injected by the backend as
// `_ai_summary`. When present it leads the preview; the requester's verbatim
// snippet drops to a fainter second line. ---
const aiSummary = computed(() => props.row._ai_summary || "");

// --- Preview snippet: the requester's latest message (their words, not our
// signature), provided pre-stripped by the backend as `_last_message`; falls
// back to the ticket description (HTML) when there are no communications yet. ---
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

// --- PYEK-AP invoice row -----------------------------------------------------
// On the AP instance the backend injects ap_* keys into each row (guarded by
// has_field, so IT/HR rows never carry them). When present, the row leads with a
// contact card — avatar/photo + sender name + email + park — then subject +
// status/flags, instead of the requester/preview layout. Keyed off the KEY being
// present (not its value), so portal-link tickets with no vendor still render
// AP-style.
const isAP = computed(
  () => "ap_vendor" in props.row || "ap_doc_type" in props.row
);
const park = computed(() => props.row.pyek_property || "");
const amountLabel = computed(() => {
  const a = props.row.ap_amount;
  if (a === null || a === undefined || a === "" || Number(a) === 0) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Number(a));
});
const senderEmail = computed(() => props.row.raised_by || "");
// M365 profile photo for internal (@pyek) senders — populated by the enricher
// into ap_sender_photo. Empty for external vendors → initials fallback.
const senderPhoto = computed(() => props.row.ap_sender_photo || "");
// Card name line: the extracted vendor (title-cased) reads best on an invoice
// queue; fall back to the contact / email local-part when there's no vendor.
const senderName = computed(() => {
  const v = props.row.ap_vendor;
  if (v) return v.charAt(0).toUpperCase() + v.slice(1).toLowerCase();
  return props.row.contact || (props.row.raised_by || "").split("@")[0] || "—";
});
const initials = computed(() => {
  const parts = senderName.value
    .replace(/[^A-Za-z0-9 ]/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
});
const apFlags = computed(() => {
  const flags: { label: string; theme: string }[] = [];
  if (props.row.ap_duplicate) flags.push({ label: "Duplicate", theme: "red" });
  if (props.row.ap_missing_invoice)
    flags.push({ label: "Missing", theme: "orange" });
  else if ("ap_vendor" in props.row && !props.row.ap_vendor)
    flags.push({ label: "Via link", theme: "gray" });
  return flags;
});
</script>

<style scoped>
/* Clean Card vocabulary (Mark's V1 mockup, label ticket-cards). Sub-11px
   sizes and the chip palette aren't in the Tailwind scale, so they live here. */
.pyek-clamp2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.pyek-qtag {
  font-size: 9.5px;
  font-weight: 800;
  border-radius: 5px;
  padding: 1.5px 6px;
  letter-spacing: 0.04em;
}
.pyek-qtag--pos {
  background: #e0edff;
  color: #1d4ed8;
}
.pyek-qtag--it {
  background: #d9f5ee;
  color: #047857;
}
.pyek-qtag--other {
  background: #eef2f6;
  color: #64748b;
}
.pyek-schip {
  font-size: 10px;
  font-weight: 600;
  border-radius: 999px;
  padding: 2px 8px;
}
.pyek-schip--open {
  background: #eff6ff;
  color: #1d4ed8;
}
.pyek-schip--wait {
  background: #f1f5f9;
  color: #64748b;
}
.pyek-schip--due {
  background: #fef2f2;
  color: #b91c1c;
}
.pyek-edge--blue {
  background: linear-gradient(180deg, #3b82f6, #2563eb);
}
.pyek-edge--red {
  background: linear-gradient(180deg, #f87171, #dc2626);
}
.pyek-edge--grey {
  background: #cbd5e1;
}
</style>
