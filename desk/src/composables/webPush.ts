import { call } from "frappe-ui";
import { ref } from "vue";

/**
 * Web push opt-in for the installed PWA.
 *
 * The problem this solves: with the app closed, an assignment reached an agent
 * only by email. The in-app unread count lived on the "Menu" tab, where you had
 * to already be looking.
 *
 * Permission is requested from an explicit tap, never on load. A prompt fired on
 * first paint is the single fastest way to get permanently denied — and on iOS a
 * denial can only be undone in system Settings, so one bad prompt costs the
 * feature for that install.
 */

declare const __SW_VERSION__: string;

// The worker lives under the build output, so its scope is /assets/helpdesk/desk/
// — NOT /helpdesk. That's fine for push (and is why notificationclick uses
// openWindow rather than focusing an existing client), but it means every
// registration lookup has to go through the scope path below, not the script URL.
const SW_SCOPE = "/assets/helpdesk/desk/";

// Registered WITH a build stamp: FC serves this non-hashed file as `immutable`
// for a year, and a proxy was handing back the previous build's worker. See the
// __SW_VERSION__ comment in vite.config.js for the measurement.
const SW_URL = `${SW_SCOPE}sw.js?v=${__SW_VERSION__}`;

export type PushState =
  | "unsupported"
  | "denied"
  | "off"
  | "on"
  | "working";

export const pushState = ref<PushState>("off");

function supported(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

/** base64url (what VAPID uses) → Uint8Array (what applicationServerKey wants). */
function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

/**
 * Wait for THIS registration to have an active worker.
 *
 * Deliberately NOT `navigator.serviceWorker.ready`, which is the obvious call and
 * is wrong here: it resolves only for a registration whose scope covers the
 * current document. Our worker is served from /assets/helpdesk/desk/ (that's
 * where the build output lives) while the app runs at /helpdesk/, so its scope
 * never covers the page.
 *
 * Measured on the live site: the worker registered and reached "activated", and
 * `navigator.serviceWorker.ready` still never settled. That left enablePush()
 * hanging on the line straight after the user granted permission — so the iOS
 * prompt appeared, the user tapped Allow, and then nothing happened at all: no
 * subscription, no error, nothing server-side to diagnose from.
 *
 * pushManager.subscribe() needs an active worker, so we do have to wait — just
 * on the right thing, and with a ceiling so a stuck install can't hang the UI.
 */
function waitForActiveWorker(
  reg: ServiceWorkerRegistration,
  timeoutMs = 10000
): Promise<boolean> {
  if (reg.active) return Promise.resolve(true);
  const pending = reg.installing || reg.waiting;
  if (!pending) return Promise.resolve(false);
  return new Promise<boolean>((resolve) => {
    let settled = false;
    const finish = (ok: boolean) => {
      if (settled) return;
      settled = true;
      pending.removeEventListener("statechange", onChange);
      clearTimeout(timer);
      resolve(ok);
    };
    const onChange = () => {
      if (reg.active || pending.state === "activated") finish(true);
      else if (pending.state === "redundant") finish(false);
    };
    const timer = setTimeout(() => finish(Boolean(reg.active)), timeoutMs);
    pending.addEventListener("statechange", onChange);
    onChange();
  });
}

async function getRegistration(): Promise<ServiceWorkerRegistration> {
  // Look up by SCOPE, so a changed build stamp still finds the worker we already
  // registered (and its existing push subscription) instead of stranding it.
  const existing = await navigator.serviceWorker.getRegistration(SW_SCOPE);
  if (existing) return existing;
  // updateViaCache:"none" keeps the browser's own HTTP cache out of the update
  // check too — belt and braces alongside the build stamp.
  return navigator.serviceWorker.register(SW_URL, { updateViaCache: "none" });
}

/**
 * Reflect reality without prompting or registering anything. Safe to call on
 * mount — it only reads.
 */
export async function refreshPushState(): Promise<void> {
  if (!supported()) {
    pushState.value = "unsupported";
    return;
  }
  if (Notification.permission === "denied") {
    pushState.value = "denied";
    return;
  }
  try {
    const reg = await navigator.serviceWorker.getRegistration(SW_SCOPE);
    const sub = reg ? await reg.pushManager.getSubscription() : null;
    pushState.value = sub ? "on" : "off";
  } catch {
    pushState.value = "off";
  }
}

export async function enablePush(): Promise<boolean> {
  if (!supported()) {
    pushState.value = "unsupported";
    return false;
  }
  pushState.value = "working";
  try {
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      pushState.value = permission === "denied" ? "denied" : "off";
      return false;
    }

    const key: string = await call(
      "helpdesk.helpdesk.web_push.get_vapid_public_key"
    );
    if (!key) {
      // The server couldn't provision a keypair. Not the agent's problem to
      // solve, and pretending it worked would be worse.
      pushState.value = "off";
      return false;
    }

    const reg = await getRegistration();
    // A worker registered this instant isn't usable yet — subscribe() needs an
    // active one. See waitForActiveWorker for why this isn't serviceWorker.ready.
    const active = await waitForActiveWorker(reg);
    if (!active) {
      console.error("push: service worker never became active");
      pushState.value = "off";
      return false;
    }

    // Reuse an existing subscription if there is one; re-subscribing with the
    // same key returns the same endpoint anyway, but this avoids the churn.
    const existing = await reg.pushManager.getSubscription();
    const sub =
      existing ||
      (await reg.pushManager.subscribe({
        // Required to be true by every browser that ships push: a silent push is
        // not permitted, and passing false throws.
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(key),
      }));

    await call("helpdesk.helpdesk.web_push.subscribe", {
      subscription: JSON.stringify(sub),
    });
    pushState.value = "on";
    return true;
  } catch (e) {
    console.error("push: enable failed", e);
    await refreshPushState();
    return false;
  }
}

export async function disablePush(): Promise<void> {
  if (!supported()) return;
  pushState.value = "working";
  try {
    const reg = await navigator.serviceWorker.getRegistration(SW_SCOPE);
    const sub = reg ? await reg.pushManager.getSubscription() : null;
    if (sub) {
      // Tell the server first: if unsubscribe() succeeds and the round trip
      // fails, the row lingers and we push at a dead endpoint until it 410s.
      await call("helpdesk.helpdesk.web_push.unsubscribe", {
        endpoint: sub.endpoint,
      });
      await sub.unsubscribe();
    }
  } catch (e) {
    console.error("push: disable failed", e);
  } finally {
    await refreshPushState();
  }
}

export async function togglePush(): Promise<void> {
  if (pushState.value === "on") return disablePush();
  await enablePush();
}
