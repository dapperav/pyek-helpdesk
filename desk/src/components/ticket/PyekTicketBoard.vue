<template>
  <!-- The desktop tickets BOARD (Mark's pick, 2026-08-18 evening, mock
       desktop-tickets-v2/v3): an ownership map, not a status dump.
       Open / Waiting on customer show only tickets NOBODY owns; the moment a
       ticket has an assignee it lives in Assigned (with owner tag, status
       chip, and a "quiet Nd" chip so an out-of-office teammate's tickets
       don't rot invisibly). Mine-style views collapse to two lanes — there
       everything is yours already. Resolved/closed stay off the board. -->
  <div class="px-5 pb-2">
    <div
      class="grid grid-cols-1 items-start gap-4"
      :class="mineView ? 'lg:grid-cols-2' : 'lg:grid-cols-3'"
    >
      <section
        v-for="lane in lanes"
        :key="lane.key"
        class="min-w-0 rounded-[14px] border border-[#e3e9f2] bg-[#f3f7fc] p-2.5"
      >
        <header class="relative flex items-center gap-2 px-1.5 pt-1">
          <!-- Echo peeks over the Open lane when its oldest unowned ticket
               has been sitting past the age line -->
          <EchoPeek
            v-if="lane.key === 'open' && !mineView"
            :active="agePeek"
            :width="50"
            :overlap="10"
            left="14px"
          />
          <span class="text-[13px] font-bold text-[#1b2a4a]">{{
            lane.name
          }}</span>
          <span
            class="rounded-full border border-[#e3e9f2] bg-white px-2 text-[11.5px] font-bold text-[#5b6577] tabular-nums"
          >
            {{ lane.rows.length }}
          </span>
          <span
            class="h-1 flex-1 rounded opacity-50"
            :style="{ background: lane.bar }"
          />
        </header>
        <p class="px-1.5 pb-2 pt-0.5 text-[11.5px] text-[#8b94a5]">
          {{ lane.sub }}
        </p>

        <!-- wrapper exists so EchoPeek can hang OVER the card's top edge —
             the article's own overflow-hidden would decapitate him -->
        <div v-for="row in lane.rows" :key="row.name" class="relative mb-2">
          <EchoPeek
            v-if="slaPeekTarget === row.name"
            :active="slaPeek"
            :width="56"
            :overlap="12"
            left="18px"
          />
          <EchoPeek
            v-else-if="quietPeekTarget === row.name"
            :active="quietPeek"
            :width="56"
            :overlap="12"
            left="18px"
          />
        <article
          class="pyek-bcard relative flex min-w-0 cursor-pointer flex-col gap-1.5 overflow-hidden rounded-[10px] border border-[#e3e9f2] bg-white py-2.5 pl-4 pr-3 transition-shadow hover:shadow-[0_2px_10px_rgba(27,42,74,0.10)]"
          @click="$emit('rowClick', row)"
        >
          <span
            class="absolute inset-y-0 left-0 w-1"
            :style="{ background: edgeColor(row) }"
          />
          <div class="flex items-center gap-2">
            <span
              class="grid size-[26px] shrink-0 place-items-center overflow-hidden rounded-full text-[10.5px] font-bold"
              :class="
                isBot(row)
                  ? 'bg-[#eef2f6] text-[#94a3b8]'
                  : 'bg-gradient-to-b from-[#e0f6ff] to-[#bfeefb] text-[#0b6e8f]'
              "
            >
              <img
                v-if="row._sender_photo"
                :src="row._sender_photo"
                class="size-full object-cover"
                alt=""
              />
              <template v-else>{{ initials(row) }}</template>
            </span>
            <span class="flex min-w-0 flex-1 items-center gap-1.5">
              <span
                v-if="unread(row)"
                class="size-2 shrink-0 rounded-full bg-[#2563eb]"
              />
              <span
                class="truncate text-[12.5px] font-semibold"
                :class="isBot(row) ? 'text-[#64748b]' : 'text-[#12365e]'"
                >{{ senderName(row) }}</span
              >
            </span>
            <span class="shrink-0 text-[11px] text-[#7d9ab5] tabular-nums">{{
              dateLabel(row)
            }}</span>
          </div>

          <div class="flex items-center gap-1.5">
            <span
              v-if="row.priority === 'High'"
              class="size-2 shrink-0 rounded-full bg-[#f59e0b]"
              :title="row.priority"
            />
            <span
              class="pyek-clamp2 min-w-0 flex-1 text-[13px] leading-snug"
              :class="[
                unread(row) ? 'font-bold' : 'font-semibold',
                isBot(row) ? 'text-[#475569]' : 'text-[#12365e]',
              ]"
              >{{ row.subject || __("(No subject)") }}</span
            >
          </div>

          <div
            v-if="!isBot(row) && (row._ai_summary || row._last_message)"
            class="pyek-clamp2 text-[12px] leading-snug text-[#48708f]"
          >
            {{ row._ai_summary || row._last_message }}
          </div>

          <div class="mt-0.5 flex flex-wrap items-center gap-1.5">
            <span v-if="queueTag(row)" class="bchip" :class="queueTag(row).cls">
              {{ queueTag(row).label }}
            </span>
            <span v-if="slaChipFor(row)" class="bchip" :class="slaChipFor(row).cls">
              {{ slaChipFor(row).text }}
            </span>
            <span
              v-if="lane.key === 'assg' && statusChip(row)"
              class="bchip"
              :class="statusChip(row).cls"
              >{{ statusChip(row).text }}</span
            >
            <span
              v-if="lane.key === 'assg' && quietDays(row.modified) >= 1"
              class="bchip bchip--quiet"
              :title="__('No activity on this ticket')"
              >{{ __("quiet") }} {{ quietDays(row.modified) }}d</span
            >
            <span class="ml-auto flex shrink-0 items-center gap-1.5">
              <span v-if="lane.key === 'assg' && owner(row)" class="bowner">
                <span
                  class="grid size-5 shrink-0 place-items-center overflow-hidden rounded-full bg-[#5b7db1] text-[8.5px] font-bold text-white"
                >
                  <img
                    v-if="owner(row).image"
                    :src="owner(row).image"
                    class="size-full object-cover"
                    alt=""
                  />
                  <template v-else>{{ owner(row).initials }}</template>
                </span>
                {{ owner(row).firstName }}
                <template v-if="ownerExtra(row)"> +{{ ownerExtra(row) }}</template>
              </span>
              <span
                class="text-[10px] font-bold tracking-[0.08em] text-[#a8bccd]"
                >#{{ row.name }}</span
              >
            </span>
          </div>
        </article>
        </div>

        <div
          v-if="!lane.rows.length"
          class="rounded-[10px] border-[1.5px] border-dashed border-[#d4deea] px-3 py-4 text-center text-[12.5px] text-[#8b94a5]"
        >
          <!-- when a lane DRAINS while you watch, Echo floats up to say it
               himself (echo-eggs round); a lane that was already empty keeps
               the quiet text -->
          <img
            v-if="drainedLane === lane.key"
            :src="ECHO_POSES.float"
            class="drained-echo mx-auto mb-1.5 w-16"
            alt=""
          />
          {{ __("All clear — nothing in the water.") }}
        </div>
      </section>
    </div>

    <!-- Resolved/closed are deliberately not lanes ("I really only need to
         see open and waiting on customer" — Mark). Say what the board is not
         showing so it never reads as "covered everything". -->
    <p
      v-if="offBoardCount > 0"
      class="mt-3 px-1 text-center text-[12px] text-[#8b94a5]"
    >
      {{
        __("{0} resolved or closed ticket(s) in this view are off the board — switch to List to see them.", [offBoardCount])
      }}
    </p>
  </div>
</template>

<script setup lang="ts">
import EchoPeek from "@/components/echo/EchoPeek.vue";
import { ECHO_POSES } from "@/components/echo/echoAssets";
import { useEchoPeek } from "@/composables/echoEggs";
import {
  edgeColor,
  isNotificationSender,
  parseAssign,
  parseFrappeDate,
  quietDays,
  slaClock,
} from "@/composables/ticketCardSignals";
import { useAuthStore } from "@/stores/auth";
import { useUserStore } from "@/stores/user";
import { __ } from "@/translation";
import { dayjs } from "frappe-ui";
import { computed, ref, watch } from "vue";

const props = defineProps<{
  rows: any[];
  // Mine-style view (filters pin _assign to the viewer): two lanes, no owner
  // tags — everything on the board is already yours.
  mineView?: boolean;
}>();

defineEmits<{ (e: "rowClick", row: any): void }>();

const { getUser } = useUserStore();
const { userId } = useAuthStore();

const isBot = (row: any) => isNotificationSender(row.raised_by);
const isLive = (row: any) =>
  row.status_category === "Open" || row.status_category === "Paused";
const assigned = (row: any) => parseAssign(row._assign).length > 0;

const lanes = computed(() => {
  const live = props.rows.filter(isLive);
  if (props.mineView) {
    return [
      {
        key: "open",
        name: __("Open"),
        sub: __("Assigned to you, needs your move"),
        bar: "#2563eb",
        rows: live.filter((r) => r.status_category === "Open"),
      },
      {
        key: "wait",
        name: __("Waiting on customer"),
        sub: __("Your tickets parked on the requester"),
        bar: "#eab308",
        rows: live.filter((r) => r.status_category === "Paused"),
      },
    ];
  }
  return [
    {
      key: "open",
      name: __("Open"),
      sub: __("No owner yet — needs a first reply"),
      bar: "#2563eb",
      rows: live.filter((r) => r.status_category === "Open" && !assigned(r)),
    },
    {
      key: "wait",
      name: __("Waiting on customer"),
      sub: __("No owner — parked on the requester"),
      bar: "#eab308",
      rows: live.filter((r) => r.status_category === "Paused" && !assigned(r)),
    },
    {
      key: "assg",
      name: __("Assigned"),
      sub: __("Owned, still open or waiting — nothing hides in a teammate's Mine"),
      bar: "#0891b2",
      rows: live.filter(assigned),
    },
  ];
});

const offBoardCount = computed(
  () => props.rows.length - props.rows.filter(isLive).length
);

// --- Echo easter eggs on the board (spec approved 2026-08-19) ---------------
// Drained lane: only a TRANSITION to zero earns the float — a lane that was
// already empty when you arrived keeps the quiet dashed text.
const drainedLane = ref<string | null>(null);
let drainTimer: ReturnType<typeof setTimeout> | null = null;
const prevLaneCounts: Record<string, number> = {};
watch(lanes, (ls) => {
  for (const l of ls) {
    const prev = prevLaneCounts[l.key];
    if (prev !== undefined && prev > 0 && l.rows.length === 0) {
      drainedLane.value = l.key;
      if (drainTimer) clearTimeout(drainTimer);
      drainTimer = setTimeout(() => (drainedLane.value = null), 9_000);
    }
    prevLaneCounts[l.key] = l.rows.length;
  }
});

// Peeks — silent "needs eyes" markers. One at a time app-wide; the manager
// in echoEggs.ts re-peeks a spot at most every 30 minutes.
const slaPeekTarget = computed<string | null>(() => {
  for (const l of lanes.value)
    for (const r of l.rows) if (slaClock(r)?.kind === "hot") return r.name;
  return null;
});
const quietPeekTarget = computed<string | null>(() => {
  const assg = lanes.value.find((l) => l.key === "assg");
  const worst = (assg?.rows || [])
    .filter((r: any) => quietDays(r.modified) >= 3)
    .sort((a: any, b: any) => quietDays(b.modified) - quietDays(a.modified))[0];
  return worst ? worst.name : null;
});
const openLaneAging = computed(() => {
  const open = lanes.value.find((l) => l.key === "open");
  // creation may not ride on every list view's rows — then this egg just
  // never fires, which is fine
  return (open?.rows || []).some(
    (r: any) =>
      r.creation && Date.now() - parseFrappeDate(r.creation) > 3 * 86_400_000
  );
});
const slaPeek = useEchoPeek("board-sla", () => !!slaPeekTarget.value);
const quietPeek = useEchoPeek("board-quiet", () => !!quietPeekTarget.value);
const agePeek = useEchoPeek(
  "board-age",
  () => !props.mineView && openLaneAging.value
);

// --- card bits (same vocabulary as the mobile Clean Card) ------------------
const senderName = (row: any) =>
  row.contact || (row.raised_by || "").split("@")[0] || "—";

function initials(row: any): string {
  const name = senderName(row);
  return name
    .split(/[\s.@_-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p: string) => p[0])
    .join("")
    .toUpperCase();
}

function unread(row: any): boolean {
  try {
    const seen = row._seen ? JSON.parse(row._seen) : [];
    return !seen.includes(userId || "");
  } catch {
    return false;
  }
}

function dateLabel(row: any): string {
  if (!row.modified) return "";
  const d = dayjs(row.modified);
  const now = dayjs();
  if (d.isSame(now, "day")) return d.format("h:mm A");
  if (d.isSame(now, "year")) return d.format("MMM D");
  return d.format("M/D/YY");
}

function queueTag(row: any): { label: string; cls: string } | null {
  const group = (row.agent_group || "").trim();
  if (!group) return null;
  const word = group.split(/\s+/)[0].toUpperCase();
  if (word.startsWith("POS")) return { label: "POS", cls: "bchip--pos" };
  if (word === "IT") return { label: "IT", cls: "bchip--it" };
  return { label: word, cls: "bchip--other" };
}

function slaChipFor(row: any): { text: string; cls: string } | null {
  const clock = slaClock(row);
  if (!clock) return null;
  return {
    text: __(clock.text),
    cls: clock.kind === "hot" ? "bchip--hot" : "bchip--due",
  };
}

function statusChip(row: any): { text: string; cls: string } | null {
  if (row.status_category === "Open")
    return { text: __("Open"), cls: "bchip--open" };
  if (row.status_category === "Paused")
    return { text: __("Waiting"), cls: "bchip--wait" };
  return null;
}

function owner(row: any): {
  firstName: string;
  initials: string;
  image?: string;
} | null {
  const emails = parseAssign(row._assign);
  if (!emails.length) return null;
  const u: any = getUser(emails[0]);
  const full = u?.full_name || emails[0].split("@")[0];
  return {
    firstName: full.split(" ")[0],
    initials: full
      .split(" ")
      .slice(0, 2)
      .map((p: string) => p[0])
      .join("")
      .toUpperCase(),
    image: u?.user_image,
  };
}

const ownerExtra = (row: any) => Math.max(0, parseAssign(row._assign).length - 1);
</script>

<style scoped>
.pyek-clamp2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.bchip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  padding: 2.5px 8px;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.bchip--pos {
  background: #e0f2fe;
  color: #075985;
}
.bchip--it {
  background: #ede9fe;
  color: #5b21b6;
}
.bchip--other {
  background: #f1f5f9;
  color: #475569;
}
.bchip--due {
  background: #fff7ed;
  color: #b45309;
}
.bchip--hot {
  background: #fef2f2;
  color: #be123c;
}
.bchip--open {
  background: #eff6ff;
  color: #1d4ed8;
}
.bchip--wait {
  background: #fefce8;
  color: #a16207;
}
.bchip--quiet {
  background: #f1f5f9;
  color: #64748b;
}
.bowner {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #f2f6fb;
  border: 1px solid #e3e9f2;
  border-radius: 999px;
  padding: 2px 9px 2px 3px;
  font-size: 11.5px;
  font-weight: 600;
  color: #5b6577;
}
</style>

<style scoped>
/* Echo floating up into a freshly-drained lane — one gentle rise, then
   still (calm-seas rule). */
.drained-echo {
  animation: drained-rise 0.8s cubic-bezier(0.25, 0.9, 0.35, 1) both;
  filter: drop-shadow(0 3px 8px rgba(4, 26, 46, 0.18));
}
@keyframes drained-rise {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
@media (prefers-reduced-motion: reduce) {
  .drained-echo {
    animation: none;
    opacity: 1;
  }
}
</style>
