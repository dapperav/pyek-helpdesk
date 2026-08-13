import { computed, ref } from "vue";

export const mobileSidebarOpened = ref(false);

/**
 * How many in-app navigations have completed since the app booted.
 *
 * Incremented from the router's afterEach. The FIRST navigation is the one that
 * resolved whatever URL the app was launched at, so a value of 1 means "we are
 * still on the screen we cold-started on, with nothing behind us".
 */
export const navigationCount = ref(0);

/**
 * True once there is somewhere to go back to inside the app.
 *
 * Exists because a push notification cold-launches the PWA straight onto a
 * ticket. The mobile ticket screen deliberately hides the bottom nav (the sticky
 * reply box owns that space), which is fine when you tapped in from a list —
 * breadcrumb and swipe-back both work. Arriving from a notification there is no
 * history at all, so hiding the nav left the app with no way out: Mark had to
 * force-quit it. Used to keep the nav visible in exactly that case.
 */
export const canGoBackInApp = computed(() => navigationCount.value > 1);
