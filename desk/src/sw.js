/* PYEK: push-only service worker.
 *
 * READ THIS BEFORE ADDING ANYTHING.
 *
 * PR 95 fixed a freeze whose cause was a CACHING service worker: it served JS
 * chunks from a previous deploy, those chunks no longer matched the app shell,
 * every navigation rejected, and the installed PWA wedged. The fix was
 * `selfDestroying: true` — no service worker at all.
 *
 * Push requires a service worker, so this file replaces that. It is safe only
 * because of what it does NOT do:
 *
 *   - no `fetch` listener, so it can never answer a request with a stale asset
 *   - no precache manifest (vite-plugin-pwa runs with injectionPoint: undefined)
 *   - no runtime caching, no navigation fallback
 *
 * If you are tempted to add offline support here, don't do it in this file
 * without re-reading the PR 95 postmortem first. The app is online-only; a
 * cache buys nothing and cost us a wedged PWA once already.
 */

// Take over as soon as we're installed. There's no cache to migrate and no
// in-flight requests to protect, so waiting buys nothing — and a push that
// arrives before activation would otherwise be dropped.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) =>
  event.waitUntil(self.clients.claim())
);

const ICON = "/assets/helpdesk/desk/manifest/pyek-icon-192.png";
const BADGE = "/assets/helpdesk/desk/manifest/pyek-maskable-192.png";

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    // A malformed payload must still produce a notification: on some platforms a
    // push event that resolves without showing one gets the origin's push
    // permission revoked.
    data = {};
  }

  const title = data.title || "PYEKMAIL";
  event.waitUntil(
    self.registration.showNotification(title, {
      body: data.body || "",
      // Collapse by ticket, set server-side. Ten updates on one ticket should
      // replace each other rather than stack ten rows on a lock screen.
      tag: data.tag || "pmit",
      renotify: true,
      icon: ICON,
      badge: BADGE,
      data: { url: data.url || "/helpdesk" },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/helpdesk";
  // openWindow rather than matchAll+focus: this worker is served from
  // /assets/helpdesk/desk/, so its scope does not contain /helpdesk and
  // clients.matchAll() cannot see the app's windows to focus one. In an
  // installed PWA openWindow lands inside the app anyway.
  event.waitUntil(self.clients.openWindow(url));
});
