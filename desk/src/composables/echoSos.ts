import { reactive } from "vue";
import { call } from "frappe-ui";
import { useAuthStore } from "@/stores/auth";
import { globalStore } from "@/stores/globalStore";
import { echoShowGlobal, sosOnDuty } from "@/composables/echoEggs";
import { __ } from "@/translation";

// ---------------------------------------------------------------------------
// Echo on duty — the SOS receiver (Mark's pick, 2026-08-19: TIMED BUT
// RECURRING, mock echo-sos-v1). When someone fires an SOS, every other
// agent's open desk gets serious-pose Echo bottom-right via the realtime
// event send_sos publishes. He stays ~90s, slips away, and resurfaces every
// ~4 minutes while the window is active. The window ends when the agent
// clicks through or dismisses, when the awaiting count falls back under the
// threshold (→ one all-clear pop), or at the 30-minute cap (the send
// cooldown). While on duty every easter egg is silenced (echoEggs.ts).
// ---------------------------------------------------------------------------

const SURFACE_MS = 90_000;
const RESURFACE_GAP_MS = 4 * 60_000;
const WINDOW_MS = 30 * 60_000;
const ALL_CLEAR_POLL_MS = 2 * 60_000;

export const sosAlert = reactive({
  visible: false,
  senderName: "",
  count: 0,
  url: "/helpdesk/tickets",
});

let windowEndsAt = 0;
let surfaceTimer: number | undefined;
let gapTimer: number | undefined;
let pollTimer: number | undefined;
let threshold = 8;

function clearTimers() {
  clearTimeout(surfaceTimer);
  clearTimeout(gapTimer);
  clearInterval(pollTimer);
}

function surface() {
  sosAlert.visible = true;
  surfaceTimer = window.setTimeout(() => {
    sosAlert.visible = false;
    if (Date.now() < windowEndsAt) {
      gapTimer = window.setTimeout(surface, RESURFACE_GAP_MS);
    } else {
      endWindow();
    }
  }, SURFACE_MS);
}

export function endWindow(allClear = false) {
  clearTimers();
  sosAlert.visible = false;
  sosOnDuty.value = false;
  if (allClear) {
    echoShowGlobal("float", __("Crisis passed — the water's calming."));
  }
}

async function pollAllClear() {
  try {
    const stats = await call("helpdesk.api.pyek_home.get_home_stats");
    const waiting = Number(stats?.awaiting_first_reply ?? NaN);
    if (!Number.isNaN(waiting) && waiting < threshold) endWindow(true);
  } catch {
    // a failed poll never ends (or extends) the window
  }
}

function onSos(payload: {
  sender?: string;
  sender_name?: string;
  waiting?: number;
  url?: string;
}) {
  const auth = useAuthStore();
  // the sender gets their own "SOS is out" pop from the Home flow
  if (!payload || payload.sender === auth.userId) return;
  clearTimers();
  sosAlert.senderName = payload.sender_name || __("the team");
  sosAlert.count = Number(payload.waiting || 0);
  sosAlert.url = payload.url || "/helpdesk/tickets";
  sosOnDuty.value = true;
  windowEndsAt = Date.now() + WINDOW_MS;
  call("helpdesk.api.pyek_sos.get_sos_state")
    .then((s: any) => {
      if (s?.threshold) threshold = Number(s.threshold);
    })
    .catch(() => {});
  pollTimer = window.setInterval(pollAllClear, ALL_CLEAR_POLL_MS);
  surface();
}

let started = false;

/** Idempotent; DesktopLayout calls this once per agent desk. */
export function startEchoSos() {
  if (started) return;
  started = true;
  const { $socket } = globalStore();
  $socket.on("pyek_sos", onSos);
  // send_sos can't be dry-run without buzzing every agent's phone — this
  // hook lets a console drive the receiver end to end on dev AND prod:
  // __pyekSosDemo({sender_name:'Mark', waiting:9, url:'/helpdesk/tickets'})
  (window as any).__pyekSosDemo = onSos;
}
