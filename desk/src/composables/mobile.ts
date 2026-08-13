import { ref } from "vue";

export const mobileSidebarOpened = ref(false);

/**
 * True once there is somewhere to go back to inside the app.
 *
 * Exists because a push notification cold-launches the PWA straight onto a
 * ticket. The mobile ticket screen deliberately hides the bottom nav (the sticky
 * reply box owns that space), which is fine when you tapped in from a list —
 * breadcrumb and swipe-back both work. Arriving from a notification there is no
 * history at all, so hiding the nav left the app with no way out: Mark had to
 * force-quit it. Used to keep the nav visible in exactly that case.
 *
 * Set from the router's afterEach off vue-router's own history state:
 * `history.state.back` is null exactly when the current entry is the first
 * in-app one. This replaced counting afterEach calls (navigationCount > 1),
 * which was measured wrong on the live site 2026-08-13 — boot completes more
 * than one navigation, so a cold-launched ticket still hid the nav, the very
 * dead end this exists to prevent.
 */
export const canGoBackInApp = ref(false);
