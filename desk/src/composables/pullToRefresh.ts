import { inject, onUnmounted, provide, ref, watch } from "vue";
import type { InjectionKey, Ref } from "vue";

/**
 * The mobile shell's scroll container. MobileLayout owns the only scrolling
 * element on a phone (the area between the header and the bottom nav), so a page
 * that wants a pull gesture has to reach it rather than its own root element.
 */
export const MobileScrollElSymbol: InjectionKey<Ref<HTMLElement | null>> =
  Symbol("mobileScrollEl");

export function provideMobileScrollEl(el: Ref<HTMLElement | null>) {
  provide(MobileScrollElSymbol, el);
}

const THRESHOLD = 64; // px of pull that commits to a refresh
const MAX = 96; // px the indicator can travel, so it can't be dragged forever
const RESISTANCE = 0.5; // finger travel : indicator travel

/**
 * Pull down at the top of a mobile page to refresh it.
 *
 * An installed PWA has no browser chrome, so there is no reload button and no
 * address bar to pull — the gesture is the only affordance a phone user has, and
 * without it the only way to force fresh data was to navigate away and back.
 *
 * Deliberately conservative, because a gesture that fights the scroller is worse
 * than no gesture: it only arms at scrollTop 0, only on a single-finger downward
 * drag, and it bails the moment the container scrolls. preventDefault is called
 * only once past a few pixels of intentional pull, so a normal flick still
 * scrolls and iOS keeps its own overscroll behaviour.
 *
 * `onRefresh` should resolve when the data has landed; the spinner is shown until
 * it does. Non-touch devices never fire any of this.
 */
export function usePullToRefresh(onRefresh: () => Promise<unknown> | unknown) {
  const scrollEl = inject(MobileScrollElSymbol, ref(null));
  const pull = ref(0);
  const refreshing = ref(false);

  let startY = 0;
  let active = false;
  let bound: HTMLElement | null = null;

  function reset() {
    active = false;
    pull.value = 0;
  }

  function onTouchStart(e: TouchEvent) {
    const node = scrollEl.value;
    if (!node || refreshing.value) return;
    if (e.touches.length !== 1) return;
    if (node.scrollTop > 0) return;
    startY = e.touches[0].clientY;
    active = true;
  }

  function onTouchMove(e: TouchEvent) {
    if (!active) return;
    const node = scrollEl.value;
    if (!node) return reset();
    // The user started scrolling for real — get out of the way.
    if (node.scrollTop > 0) return reset();
    const dy = e.touches[0].clientY - startY;
    if (dy <= 0) {
      pull.value = 0;
      return;
    }
    pull.value = Math.min(MAX, dy * RESISTANCE);
    // Only claim the gesture once it's clearly a pull, so a flick still scrolls.
    if (pull.value > 4 && e.cancelable) e.preventDefault();
  }

  async function onTouchEnd() {
    if (!active) return;
    active = false;
    if (pull.value < THRESHOLD || refreshing.value) {
      pull.value = 0;
      return;
    }
    refreshing.value = true;
    pull.value = THRESHOLD; // park the spinner at the threshold while it works
    try {
      await onRefresh();
    } catch {
      // A failed refresh still has to release the indicator, or the page looks stuck.
    } finally {
      refreshing.value = false;
      pull.value = 0;
    }
  }

  function bind(node: HTMLElement | null) {
    unbind();
    if (!node) return;
    node.addEventListener("touchstart", onTouchStart, { passive: true });
    // Not passive: this one needs preventDefault to suppress iOS overscroll.
    node.addEventListener("touchmove", onTouchMove, { passive: false });
    node.addEventListener("touchend", onTouchEnd, { passive: true });
    node.addEventListener("touchcancel", reset, { passive: true });
    bound = node;
  }

  function unbind() {
    if (!bound) return;
    bound.removeEventListener("touchstart", onTouchStart);
    bound.removeEventListener("touchmove", onTouchMove);
    bound.removeEventListener("touchend", onTouchEnd);
    bound.removeEventListener("touchcancel", reset);
    bound = null;
  }

  // The layout's scroll element can arrive after this composable runs, and it
  // changes when the shell re-renders, so follow it rather than binding once.
  watch(scrollEl, (node) => bind(node), { immediate: true });
  onUnmounted(unbind);

  return { pull, refreshing, threshold: THRESHOLD };
}
