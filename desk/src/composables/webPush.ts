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

const SW_URL = "/assets/helpdesk/desk/sw.js";

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

async function getRegistration(): Promise<ServiceWorkerRegistration> {
  const existing = await navigator.serviceWorker.getRegistration(SW_URL);
  if (existing) return existing;
  return navigator.serviceWorker.register(SW_URL);
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
    const reg = await navigator.serviceWorker.getRegistration(SW_URL);
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
    // A worker registered this instant isn't usable yet.
    await navigator.serviceWorker.ready;

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
    const reg = await navigator.serviceWorker.getRegistration(SW_URL);
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
