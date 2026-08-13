/* PYEK: push-only service worker for the PMIT PWA.
 *
 * WHY IT LIVES HERE, not in the build output.
 *
 * It used to be emitted to /assets/helpdesk/desk/sw.js, which gave it a scope of
 * /assets/helpdesk/desk/ — while the app runs at /helpdesk/. That scope is not an
 * inconvenience, it's a functional limit: clients.matchAll() only returns clients
 * inside scope, so the worker could never see the app's own windows. The only
 * thing left was clients.openWindow(), and on iOS standalone that foregrounds the
 * installed app WITHOUT honouring the path — so tapping a notification opened
 * PYEKMAIL but not the ticket it was about. Confirmed by Mark on a real iPhone.
 *
 * Served from helpdesk/www/sw.js, Frappe serves it at /sw.js, whose default scope
 * is the whole origin. Now matchAll can find the running app and navigate it.
 * (The /helpdesk/ path was not an option: Frappe's SPA catch-all answers ANY
 * unknown path under /helpdesk/ with the app-shell HTML and a 200, so a worker
 * there would have been served HTML.)
 *
 * READ THIS BEFORE ADDING ANYTHING. PR 95 fixed a freeze caused by a CACHING
 * service worker that served JS chunks from a previous deploy. This worker is
 * safe only because of what it does NOT do:
 *
 *   - no `fetch` listener, so it can never answer a request with a stale asset
 *   - no precache manifest, no runtime caching, no navigation fallback
 *
 * That matters more now, not less: this worker's scope is the entire origin,
 * including the Frappe desk at /app. It controls nothing because it never
 * intercepts a request. Do not add offline support here.
 */

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
    // A malformed payload must STILL show something: a push event that resolves
    // without showing a notification can cost the origin its push permission.
    data = {};
  }

  event.waitUntil(
    self.registration.showNotification(data.title || "PYEKMAIL", {
      body: data.body || "",
      // Collapse by ticket (set server-side) so ten updates on one ticket replace
      // each other instead of stacking ten rows on a lock screen.
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
  const raw = (event.notification.data && event.notification.data.url) || "/helpdesk";

  event.waitUntil(
    (async () => {
      const target = new URL(raw, self.location.origin);
      const windows = await self.clients.matchAll({
        type: "window",
        includeUncontrolled: true,
      });

      for (const client of windows) {
        if (new URL(client.url).origin !== target.origin) continue;
        // Reuse the app that's already open and steer it to the ticket. This is
        // the path openWindow couldn't do on iOS, and is why the worker needed a
        // scope covering /helpdesk in the first place.
        if ("navigate" in client) {
          try {
            await client.navigate(target.href);
          } catch {
            // Some engines refuse to navigate a client they don't control;
            // focusing it is still better than opening a second window.
          }
        }
        await client.focus();
        return;
      }

      // Nothing open — cold launch straight at the ticket.
      await self.clients.openWindow(target.href);
    })()
  );
});
