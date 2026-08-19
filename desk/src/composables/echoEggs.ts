import { onUnmounted, reactive, ref, type Ref } from "vue";
import { call } from "frappe-ui";
import { __ } from "@/translation";
import type { EchoPose } from "@/components/echo/echoAssets";

// ---------------------------------------------------------------------------
// Echo easter eggs — the brain (Mark's echo-eggs spec, approved 2026-08-19).
//
// Two behaviors share this module:
//  • POPS: full pose sticker + one bubble line (EchoPop.vue). Event-driven,
//    app-wide via the DesktopLayout layer; PyekHome keeps its scenic crest
//    spot. Scarcity is the whole point: one pop at a time, a global
//    10-minute cooldown shared by every source (including Home's ambient
//    scheduler), and celebration pops are muted while anything urgent is
//    open (the PR 92 voice-drop rule). User-invoked moments (hidden
//    trigger) bypass the cooldown because the user asked.
//  • PEEKS: EchoPeek.vue, silent. One peek at a time app-wide; each spot
//    re-peeks at most every 30 minutes while its condition holds.
//
// Everything is client-side — no new server code (a new endpoint's first
// prod call is its first real test; see PR 155).
// ---------------------------------------------------------------------------

const POP_COOLDOWN_MS = 10 * 60_000;
const POP_LINGER_MS = 8_500;
const PEEK_LINGER_MS = 10_000;
const PEEK_REPEEK_MS = 30 * 60_000;
const STREAK_WINDOW_MS = 60 * 60_000;

const LS_LAST_POP = "pyekEcho:lastPop";
const LS_CLOSES = "pyekEcho:closes";
const LS_GREET = "pyekEcho:greetDay";
const LS_NIGHT = "pyekEcho:nightDay";

// ---- global pop state (rendered by DesktopLayout's fixed layer) -----------

export const globalPop = reactive<{ show: boolean; pose: EchoPose; text: string }>({
  show: false,
  pose: "thumbs",
  text: "",
});
let globalHide: number | undefined;

function lastPopAt(): number {
  return Number(localStorage.getItem(LS_LAST_POP) || 0);
}

/** Shared cooldown gate — Home's ambient scheduler asks this too. */
export function echoCanPop(): boolean {
  return Date.now() - lastPopAt() >= POP_COOLDOWN_MS;
}

export function echoMarkPop() {
  localStorage.setItem(LS_LAST_POP, String(Date.now()));
}

// ---- urgent guard ----------------------------------------------------------
// Any live urgent ticket mutes celebration pops. Same proven
// frappe.client.get_count pattern as stores/queueCounts.ts.

const urgentOpen = ref(0);
let urgentFetchedAt = 0;

async function refreshUrgent() {
  try {
    const n = await call("frappe.client.get_count", {
      doctype: "HD Ticket",
      filters: { priority: "Urgent", status_category: ["in", ["Open", "Paused"]] },
    });
    urgentOpen.value = typeof n === "number" ? n : 0;
  } catch {
    // an unreadable count never blocks Echo entirely — fail open
    urgentOpen.value = 0;
  }
  urgentFetchedAt = Date.now();
}

function urgentGuardActive(): boolean {
  if (Date.now() - urgentFetchedAt > 5 * 60_000) refreshUrgent(); // refresh for next time
  return urgentOpen.value > 0;
}

// ---- the pop API -----------------------------------------------------------

export type EchoEvent =
  | "streak"
  | "sla"
  | "claim"
  | "night"
  | "found"; // hidden trigger

function lineFor(kind: EchoEvent, ctx: Record<string, any> = {}): { pose: EchoPose; text: string } | null {
  switch (kind) {
    case "streak": {
      const n = ctx.count ?? 3;
      if (n >= 7) return { pose: "cheer", text: __("That's the whole set — nothing left in the water.") };
      if (n >= 5) return { pose: "cheer", text: __("Five straight. Leave a little for the tide.") };
      return { pose: "cheer", text: __("Three in a row — the water's glassy.") };
    }
    case "sla": {
      const m = Math.max(1, Math.round(ctx.mins ?? 1));
      return {
        pose: "clock",
        text:
          m <= 5
            ? __("That one was drifting — you pulled it back.")
            : __("Under the wire by {0} minutes. Clean save.", [m]),
      };
    }
    case "claim":
      return {
        pose: "ok",
        text: ctx.alt ? __("Claimed. I'll let the tide know.") : __("Yours now — nice reflexes."),
      };
    case "night":
      return { pose: "night", text: __("Late one? I'll keep watch with you.") };
    case "found":
      return { pose: "peek", text: __("You found me. This stays between us.") };
  }
  return null;
}

const CELEBRATIONS: EchoEvent[] = ["streak", "sla", "claim", "night"];

/**
 * Fire an event pop in the global bottom-right layer. Returns true if it
 * actually showed (callers with their own spot, like Home's claim pop, can
 * route the same guards through here with `render:false`).
 */
export function echoEvent(
  kind: EchoEvent,
  ctx: Record<string, any> = {},
  opts: { render?: boolean } = {}
): { pose: EchoPose; text: string } | null {
  const isCelebration = CELEBRATIONS.includes(kind);
  const force = kind === "found"; // user summoned him — always answer
  if (!force) {
    if (!echoCanPop()) return null;
    if (isCelebration && urgentGuardActive()) return null;
  }
  const line = lineFor(kind, ctx);
  if (!line) return null;
  echoMarkPop();
  if (opts.render === false) return line;
  clearTimeout(globalHide);
  // no rAF dance: pops are cooldown-spaced minutes apart, so the previous
  // entrance animation is long gone — and rAF never fires in hidden tabs,
  // which would leave the pop permanently un-shown
  globalPop.pose = line.pose;
  globalPop.text = line.text;
  globalPop.show = true;
  globalHide = window.setTimeout(() => (globalPop.show = false), POP_LINGER_MS);
  return line;
}

// ---- close-streak tracking -------------------------------------------------

/** Call from every path that closes/resolves a ticket by hand. */
export function echoRecordClose() {
  let closes: number[] = [];
  try {
    closes = JSON.parse(localStorage.getItem(LS_CLOSES) || "[]");
  } catch {
    closes = [];
  }
  const now = Date.now();
  closes = closes.filter((t) => now - t < STREAK_WINDOW_MS);
  closes.push(now);
  localStorage.setItem(LS_CLOSES, JSON.stringify(closes));
  const n = closes.length;
  // 3rd close pops, then every 2nd after (3, 5, 7, ...)
  if (n >= 3 && (n - 3) % 2 === 0) echoEvent("streak", { count: n });
}

/** Call after a reply send when the ticket still had a first-response clock. */
export function echoRecordSlaSave(minsLeft: number) {
  if (minsLeft > 0 && minsLeft <= 15) echoEvent("sla", { mins: minsLeft });
}

// ---- once-per-day moments --------------------------------------------------

function dayKey(shiftHours = 0): string {
  const d = new Date(Date.now() - shiftHours * 3_600_000);
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
}

/** First Home load of the day → true exactly once. */
export function echoClaimGreeting(): boolean {
  const key = dayKey();
  if (localStorage.getItem(LS_GREET) === key) return false;
  localStorage.setItem(LS_GREET, key);
  return true;
}

function maybeNightPop() {
  const h = new Date().getHours();
  if (h < 21 && h >= 5) return;
  // one key per NIGHT (a 2am session belongs to yesterday's shift)
  const key = dayKey(6);
  if (localStorage.getItem(LS_NIGHT) === key) return;
  if (echoEvent("night")) localStorage.setItem(LS_NIGHT, key);
}

// ---- hidden trigger ---------------------------------------------------------

let waveClicks = 0;
let waveTimer: number | undefined;

/** 5 quick clicks on the wave mark summon him anywhere. */
export function echoWaveClick() {
  waveClicks++;
  clearTimeout(waveTimer);
  waveTimer = window.setTimeout(() => (waveClicks = 0), 1_600);
  if (waveClicks >= 5) {
    waveClicks = 0;
    echoEvent("found");
  }
}

// ---- the peek manager -------------------------------------------------------
// One peek at a time app-wide. Spots register a condition; the scanner
// activates the first eligible one, lets it linger 10s, then frees the slot.
// A spot that stays true re-peeks at most every 30 minutes.

type PeekSpot = {
  id: string;
  cond: () => boolean;
  active: Ref<boolean>;
  eligibleAt: number;
};
const peekSpots = new Map<string, PeekSpot>();
// per-spot memory survives route changes within the session
const peekEligible = new Map<string, number>();
let peekBusy = false;
let peekScanTimer: number | undefined;

function scanPeeks() {
  if (peekBusy) return;
  for (const spot of peekSpots.values()) {
    if (Date.now() < spot.eligibleAt) continue;
    let hit = false;
    try {
      hit = spot.cond();
    } catch {
      hit = false;
    }
    if (!hit) continue;
    peekBusy = true;
    spot.active.value = true;
    spot.eligibleAt = Date.now() + PEEK_REPEEK_MS;
    peekEligible.set(spot.id, spot.eligibleAt);
    window.setTimeout(() => {
      spot.active.value = false;
      // small grace so two peeks never overlap visually
      window.setTimeout(() => (peekBusy = false), 1_200);
    }, PEEK_LINGER_MS);
    return; // one at a time
  }
}

/**
 * Register a peek spot from a component. Returns the `active` ref to bind
 * to <EchoPeek>. The condition is polled (~45s), so it can read reactive
 * state freely. Unregisters on component unmount.
 */
export function useEchoPeek(id: string, cond: () => boolean): Ref<boolean> {
  const active = ref(false);
  peekSpots.set(id, {
    id,
    cond,
    active,
    eligibleAt: peekEligible.get(id) ?? Date.now() + 12_000, // let the page settle first
  });
  onUnmounted(() => {
    peekSpots.delete(id);
    if (active.value) {
      active.value = false;
      peekBusy = false;
    }
  });
  return active;
}

// ---- lifecycle ---------------------------------------------------------------

let started = false;

/** Idempotent; DesktopLayout calls this once. */
export function startEchoEggs() {
  if (started) return;
  started = true;
  refreshUrgent();
  maybeNightPop();
  peekScanTimer = window.setInterval(scanPeeks, 45_000);
  window.setTimeout(scanPeeks, 15_000); // first pass after the page settles
  window.setInterval(maybeNightPop, 15 * 60_000);
}
