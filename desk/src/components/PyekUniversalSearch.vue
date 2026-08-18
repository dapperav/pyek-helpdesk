<template>
  <!-- Universal ticket search (Mark, 2026-08-18, mock desktop-search-v1
       "looks great"): one box for names, keywords, thread text, and ticket
       numbers — every status, results bucketed Open / Waiting / Resolved.
       Engine = three EXISTING endpoints composed client-side (no new server
       code): helpdesk.api.search.search (SQLite FTS over subjects,
       descriptions, comments, emails), helpdesk.api.contact.search_contacts
       (person names -> emails), frappe.client.get_list (ticket metadata,
       same call PyekHome makes). -->
  <Dialog v-model:open="show" size="2xl" position="top" bare>
    <template #default>
      <div class="flex max-h-[76vh] flex-col overflow-hidden rounded-xl bg-surface-modal">
        <div class="flex items-center gap-2.5 border-b border-outline-gray-1 px-4 py-3.5">
          <LucideSearch class="size-4 shrink-0 text-ink-gray-4" />
          <input
            ref="inputEl"
            v-model="query"
            class="w-full border-none bg-transparent p-0 text-base text-ink-gray-8 placeholder:text-ink-gray-4 focus:ring-0"
            :placeholder="__('Search any ticket — person, keyword, thread text, or #number…')"
            autocomplete="off"
            @keydown="onKeydown"
          />
          <LoadingIndicator v-if="loading" class="size-4 shrink-0 text-ink-gray-4" />
          <span v-else class="shrink-0 rounded border border-outline-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-4">esc</span>
        </div>

        <div ref="listEl" class="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
          <!-- number jump -->
          <button
            v-if="jumpId"
            class="jumprow"
            :class="{ sel: selIndex === 0 }"
            @click="openTicket(jumpId)"
          >
            <LucideTicket class="size-4 shrink-0" />
            <span>
              {{ __("Go to ticket") }} <b>#{{ jumpId }}</b>
            </span>
            <span class="ml-auto text-xs font-bold text-ink-blue-2">↵</span>
          </button>

          <template v-for="bucket in buckets" :key="bucket.key">
            <div v-if="bucket.rows.length" class="grouphead" :class="bucket.cls">
              {{ bucket.label }}
              <span class="n">{{ bucket.total }}</span>
            </div>
            <button
              v-for="row in bucket.rows"
              :key="row.name"
              class="hit"
              :class="{ sel: flatIndex(row) === selIndex }"
              @click="openRow(row)"
            >
              <span class="avatar" :style="{ background: avatarColor(row) }">{{
                initials(row)
              }}</span>
              <span class="min-w-0 flex-1">
                <span class="flex min-w-0 items-baseline gap-2">
                  <span class="shrink-0 text-[12.5px] font-semibold text-ink-gray-8">{{
                    senderName(row)
                  }}</span>
                  <span class="truncate text-[13px] text-ink-gray-7">{{
                    row.subject || __("(No subject)")
                  }}</span>
                </span>
                <!-- snippet comes back from the FTS pre-highlighted (the
                     search page v-htmls the same payload) -->
                <span
                  v-if="row.snippet"
                  class="snippet mt-0.5 block truncate text-xs text-ink-gray-5"
                >
                  <span v-if="row.inThread" class="me-1 font-semibold" style="color: #0e7490">{{
                    __("in thread:")
                  }}</span>
                  <span v-html="row.snippet" />
                </span>
              </span>
              <span class="flex shrink-0 items-center gap-2">
                <span v-if="queueTag(row)" class="uchip" :class="queueTag(row).cls">{{
                  queueTag(row).label
                }}</span>
                <span class="uchip" :class="statusChipCls(row)">{{
                  statusChipLabel(row)
                }}</span>
                <span class="text-[11px] font-bold text-ink-gray-4 tabular-nums">#{{ row.name }}</span>
                <span class="w-12 text-right text-[11px] text-ink-gray-4 tabular-nums">{{
                  dateLabel(row)
                }}</span>
              </span>
            </button>
          </template>

          <div v-if="showEmpty" class="px-4 py-8 text-center text-sm text-ink-gray-5">
            {{ __("Nothing matched — tried subjects, senders, thread text, and numbers, across every status.") }}
          </div>
          <div v-else-if="!hasResults && !jumpId" class="px-4 py-8 text-center text-sm text-ink-gray-5">
            {{ __("Type a name, a keyword, or a ticket number.") }}
          </div>
        </div>

        <div class="flex gap-4 border-t border-outline-gray-1 px-4 py-2.5 text-xs text-ink-gray-5">
          <span><b class="font-semibold text-ink-gray-6">{{ __("Everything, every status") }}</b> — {{ __("subjects, senders, and the full email/comment thread") }}</span>
          <span class="ms-auto">↑↓ · ↵</span>
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import {
  showUniversalSearch,
  universalSearchSeed,
} from "@/composables/universalSearch";
import { useShortcut } from "@/composables/shortcuts";
import { __ } from "@/translation";
import { call, dayjs, Dialog, LoadingIndicator } from "frappe-ui";
import { computed, nextTick, ref, watch } from "vue";
import { useRouter } from "vue-router";
import LucideSearch from "~icons/lucide/search";
import LucideTicket from "~icons/lucide/ticket";

const router = useRouter();
const show = showUniversalSearch;
const query = ref("");
const loading = ref(false);
const inputEl = ref<HTMLInputElement | null>(null);
const listEl = ref<HTMLElement | null>(null);
const selIndex = ref(0);

type Row = {
  name: string;
  subject?: string;
  status?: string;
  status_category?: string;
  raised_by?: string;
  contact?: string;
  agent_group?: string;
  modified?: string;
  snippet?: string;
  inThread?: boolean;
  hash?: string;
};
const rowsByBucket = ref<{ open: Row[]; wait: Row[]; done: Row[] }>({
  open: [],
  wait: [],
  done: [],
});
const searched = ref(false);

// Ctrl/Cmd+K (replaces the old palette binding on the agent desktop) and "/".
useShortcut({ key: "k", meta: true }, () => (show.value = !show.value));
useShortcut("/", () => (show.value = true));

watch(show, (open) => {
  if (open) {
    query.value = universalSearchSeed.value;
    universalSearchSeed.value = "";
    searched.value = false;
    if (!query.value) rowsByBucket.value = { open: [], wait: [], done: [] };
    nextTick(() => inputEl.value?.focus());
    if (query.value) run();
  }
});

let timer: ReturnType<typeof setTimeout> | null = null;
watch(query, () => {
  selIndex.value = 0;
  if (timer) clearTimeout(timer);
  timer = setTimeout(run, 300);
});

const jumpId = computed(() => {
  const m = query.value.trim().match(/^#?(\d{1,5})$/);
  if (!m) return "";
  return m[1].length < 4 ? m[1].padStart(4, "0") : m[1];
});

let runSeq = 0;
async function run() {
  const q = query.value.trim();
  if (q.length < 2) {
    rowsByBucket.value = { open: [], wait: [], done: [] };
    searched.value = false;
    return;
  }
  const mine = ++runSeq;
  loading.value = true;
  try {
    // 1) FTS (subjects, descriptions, comments, emails — all statuses) and
    //    contact-name lookup, in parallel. Each degrades to empty on failure
    //    (e.g. a not-yet-built FTS index must not kill the name path).
    const [fts, contacts] = await Promise.all([
      call("helpdesk.api.search.search", { query: q }).catch(() => null),
      fetchContacts(q).catch(() => []),
    ]);
    if (mine !== runSeq) return;

    // Ticket id -> best snippet/hash from the FTS hits.
    const meta: Record<string, { snippet?: string; inThread?: boolean; hash?: string }> = {};
    for (const r of fts?.results || []) {
      let tid = "";
      let hash = "";
      let inThread = false;
      if (r.doctype === "HD Ticket") tid = r.name;
      else if (r.doctype === "HD Ticket Comment") {
        tid = r.reference_ticket;
        hash = `#comment-${r.name}`;
        inThread = true;
      } else if (r.doctype === "Communication") {
        tid = r.reference_name;
        inThread = true;
      }
      if (!tid) continue;
      if (!meta[tid] || (!meta[tid].snippet && r.content)) {
        meta[tid] = {
          snippet: r.content || meta[tid]?.snippet,
          inThread: meta[tid] ? meta[tid].inThread : inThread,
          hash: meta[tid]?.hash || hash,
        };
      }
    }

    const emails = (contacts || [])
      .map((c: any) => c.email_id)
      .filter(Boolean);
    const ids = Object.keys(meta);

    // 2) One metadata fetch for the union (same client call PyekHome makes).
    //    A subject-LIKE fallback keeps keyword search alive even if the FTS
    //    index is missing on prod.
    const FIELDS = [
      "name",
      "subject",
      "status",
      "status_category",
      "raised_by",
      "contact",
      "agent_group",
      "modified",
    ];
    const fetches: Promise<any>[] = [];
    if (ids.length)
      fetches.push(
        listTickets({ name: ["in", ids] }, ids.length).catch(() => [])
      );
    if (emails.length)
      fetches.push(
        listTickets({ raised_by: ["in", emails] }, 30).catch(() => [])
      );
    if (!ids.length && !fts?.results)
      fetches.push(
        listTickets({ subject: ["like", `%${q}%`] }, 20).catch(() => [])
      );
    const lists = await Promise.all(fetches);
    if (mine !== runSeq) return;

    const seen = new Set<string>();
    const merged: Row[] = [];
    for (const list of lists) {
      for (const t of list || []) {
        if (seen.has(t.name)) continue;
        seen.add(t.name);
        merged.push({ ...t, ...(meta[t.name] || {}) });
      }
    }
    merged.sort((a, b) => (b.modified || "").localeCompare(a.modified || ""));
    rowsByBucket.value = {
      open: merged.filter((t) => t.status_category === "Open"),
      wait: merged.filter((t) => t.status_category === "Paused"),
      done: merged.filter(
        (t) => t.status_category !== "Open" && t.status_category !== "Paused"
      ),
    };
    searched.value = true;
  } finally {
    if (mine === runSeq) loading.value = false;
  }
}

// search_contacts is whitelisted GET-only — frappe-ui's call() POSTs and
// would 405, so this one goes over a plain GET with the session cookie.
async function fetchContacts(q: string): Promise<any[]> {
  const r = await fetch(
    `/api/method/helpdesk.api.contact.search_contacts?txt=${encodeURIComponent(q)}`,
    { headers: { Accept: "application/json" } }
  );
  if (!r.ok) return [];
  return (await r.json())?.message || [];
}

function listTickets(filters: Record<string, any>, limit: number) {
  return call("frappe.client.get_list", {
    doctype: "HD Ticket",
    filters,
    fields: [
      "name",
      "subject",
      "status",
      "status_category",
      "raised_by",
      "contact",
      "agent_group",
      "modified",
    ],
    order_by: "modified desc",
    limit_page_length: limit,
  });
}

const CAP = 10;
const buckets = computed(() => {
  const b = rowsByBucket.value;
  return [
    { key: "open", label: __("Open"), cls: "gh-open", total: b.open.length, rows: b.open.slice(0, CAP) },
    { key: "wait", label: __("Waiting on customer"), cls: "gh-wait", total: b.wait.length, rows: b.wait.slice(0, CAP) },
    { key: "done", label: __("Resolved · closed"), cls: "gh-done", total: b.done.length, rows: b.done.slice(0, CAP) },
  ];
});

const flatRows = computed(() => buckets.value.flatMap((b) => b.rows));
const hasResults = computed(() => flatRows.value.length > 0);
const showEmpty = computed(
  () =>
    searched.value &&
    !loading.value &&
    !hasResults.value &&
    !jumpId.value &&
    query.value.trim().length >= 2
);

function flatIndex(row: Row): number {
  return flatRows.value.indexOf(row) + (jumpId.value ? 1 : 0);
}

function onKeydown(e: KeyboardEvent) {
  const count = flatRows.value.length + (jumpId.value ? 1 : 0);
  if (e.key === "ArrowDown") {
    e.preventDefault();
    selIndex.value = Math.min(selIndex.value + 1, Math.max(0, count - 1));
    scrollSelIntoView();
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    selIndex.value = Math.max(selIndex.value - 1, 0);
    scrollSelIntoView();
  } else if (e.key === "Enter") {
    e.preventDefault();
    if (jumpId.value && selIndex.value === 0) return openTicket(jumpId.value);
    const row = flatRows.value[selIndex.value - (jumpId.value ? 1 : 0)];
    if (row) openRow(row);
  }
}

function scrollSelIntoView() {
  nextTick(() => {
    listEl.value
      ?.querySelector(".sel")
      ?.scrollIntoView({ block: "nearest" });
  });
}

function openTicket(ticketId: string, hash?: string) {
  show.value = false;
  router.push({
    name: "TicketAgent",
    params: { ticketId },
    ...(hash ? { hash } : {}),
  });
}
function openRow(row: Row) {
  openTicket(row.name, row.hash);
}

// --- display bits (same vocabulary as the board cards) ---------------------
const senderName = (row: Row) =>
  row.contact || (row.raised_by || "").split("@")[0] || "—";

function initials(row: Row): string {
  return senderName(row)
    .split(/[\s.@_-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();
}

const AVATAR_COLORS = ["#5b7db1", "#b0705c", "#6b8f71", "#8d6cab", "#c08b2d", "#3e7d8f"];
function avatarColor(row: Row): string {
  const s = senderName(row);
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length];
}

function queueTag(row: Row): { label: string; cls: string } | null {
  const word = (row.agent_group || "").trim().split(/\s+/)[0]?.toUpperCase();
  if (!word) return null;
  if (word.startsWith("POS")) return { label: "POS", cls: "u-pos" };
  if (word === "IT") return { label: "IT", cls: "u-it" };
  return { label: word, cls: "u-other" };
}

function statusChipLabel(row: Row): string {
  if (row.status_category === "Open") return __("Open");
  if (row.status_category === "Paused") return __("Waiting");
  return __(row.status || "Closed");
}
function statusChipCls(row: Row): string {
  if (row.status_category === "Open") return "u-open";
  if (row.status_category === "Paused") return "u-wait";
  return "u-done";
}

function dateLabel(row: Row): string {
  if (!row.modified) return "";
  const d = dayjs(row.modified);
  const now = dayjs();
  if (d.isSame(now, "day")) return d.format("h:mm A");
  if (d.isSame(now, "year")) return d.format("MMM D");
  return d.format("M/D/YY");
}
</script>

<style scoped>
.jumprow {
  display: flex;
  align-items: center;
  gap: 10px;
  width: calc(100% - 16px);
  margin: 10px 8px 2px;
  padding: 9px 12px;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 9px;
  font-size: 13px;
  color: #0c4a6e;
  cursor: pointer;
  text-align: left;
}
.jumprow:hover,
.jumprow.sel {
  background: #e0f2fe;
}
.grouphead {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 10px 6px;
  font-size: 11px;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  font-weight: 700;
}
.grouphead .n {
  border-radius: 999px;
  padding: 0 7px;
  background: var(--surface-gray-2);
  color: var(--ink-gray-6);
  font-size: 11px;
}
.gh-open { color: #1d4ed8; }
.gh-wait { color: #a16207; }
.gh-done { color: #047857; }
.hit {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  border-radius: 9px;
  cursor: pointer;
  min-width: 0;
  text-align: left;
  background: transparent;
  border: 0;
}
.hit:hover,
.hit.sel {
  background: var(--surface-gray-2);
}
.avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  flex: 0 0 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10.5px;
  font-weight: 700;
  color: #fff;
}
.snippet :deep(mark) {
  background: #fff3bf;
  color: inherit;
  border-radius: 2px;
  padding: 0 1px;
}
.uchip {
  display: inline-flex;
  border-radius: 999px;
  font-size: 10.5px;
  font-weight: 600;
  padding: 2px 8px;
  white-space: nowrap;
}
.u-pos { background: #e0f2fe; color: #075985; }
.u-it { background: #ede9fe; color: #5b21b6; }
.u-other { background: #f1f5f9; color: #475569; }
.u-open { background: #eff6ff; color: #1d4ed8; }
.u-wait { background: #fefce8; color: #a16207; }
.u-done { background: #ecfdf5; color: #047857; }
</style>
