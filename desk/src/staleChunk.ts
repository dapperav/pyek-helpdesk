// PYEK: heal the installed PWA after a deploy.
//
// Every route is a lazy `import()`, so the running app holds chunk URLs like
// /assets/helpdesk/desk/assets/HomeView-<hash>.js. Frappe Cloud rebuilds assets
// on each deploy and does NOT keep the previous hashed files, so those URLs go
// 404 the moment we ship (verified against it.pyekmail.com: the request returns
// Frappe's 404 page and the import rejects with "Failed to fetch dynamically
// imported module").
//
// A browser tab is fine because reloading re-fetches the shell — /helpdesk is
// served `no-store`, while the hashed assets are `immutable`. An installed iOS
// PWA is the problem: iOS resumes it with the JS context intact for days, so its
// in-memory chunk URLs are already dead. Every navigation then rejects, and
// nothing recovered from that — the router's error hook only recorded the
// message for the debug strip. The tap did nothing and the screen never changed:
// that is the "freeze", and why the Dashboard (a lazy route whose child is lazy
// too, so two chunks must land) appeared to never load.
//
// Recovery is simply to reload the target path: the shell comes back fresh with
// current chunk URLs. We allow one attempt per path per session so that a
// genuine network failure degrades into a visible error instead of a reload loop.

const KEY = "pyek:chunk-reload";

/** True if `err` is a module/chunk that failed to load rather than a real bug. */
export function isStaleChunkError(err: unknown): boolean {
  const msg = String((err as any)?.message || err || "");
  return (
    // Chromium
    /Failed to fetch dynamically imported module/i.test(msg) ||
    /error loading dynamically imported module/i.test(msg) ||
    // Safari / iOS — the wording that matters for the PWA
    /Importing a module script failed/i.test(msg) ||
    /Unable to preload CSS/i.test(msg) ||
    /^Loading chunk \S+ failed/i.test(msg)
  );
}

/**
 * Reload `href` (an absolute in-app path, e.g. "/helpdesk/home") to pick up the
 * current chunk URLs. Returns false if we already tried this path in this
 * session, in which case the caller should let the error surface.
 */
export function recoverFromStaleChunk(href: string): boolean {
  if (typeof window === "undefined") return false;
  let attempted = "";
  try {
    attempted = sessionStorage.getItem(KEY) || "";
  } catch {
    // Private mode / storage disabled: skip the guard rather than the fix.
  }
  if (attempted === href) return false;
  try {
    sessionStorage.setItem(KEY, href);
  } catch {
    /* ignore */
  }
  window.location.replace(href);
  return true;
}

/** Called once a navigation succeeds, so a later deploy can heal again. */
export function clearStaleChunkGuard(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
