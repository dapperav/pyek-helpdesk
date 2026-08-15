/**
 * iOS standalone-PWA viewport heal.
 *
 * Documented iOS bug (17/18): in an installed PWA, the first time the
 * software keyboard opens, the layout viewport SHRINKS — innerHeight drops
 * by the status-bar inset (932 → 873 on a Pro Max, the exact numbers
 * measured on Mark's phone) — and never grows back until force-quit. Fixed
 * bottom bars then float above a dead letterboxed band. Nothing in markup
 * fixes it (we tried viewport metas twice); the working remedy is to force
 * WebKit to re-measure by toggling the app root's display for one reflow
 * after the keyboard goes away. The hidden frame is never painted (the
 * toggle happens synchronously within one task), so there is no flicker.
 *
 * Also runs once shortly after boot: on some versions the app LAUNCHES
 * already-shrunk (observed after a re-install), so a launch heal covers
 * that state too.
 */
import { ref } from "vue";

// Largest layout-viewport height seen this session — the heal target.
export const maxViewportHeight = ref(0);

function isStandalone(): boolean {
  return (
    window.matchMedia?.("(display-mode: standalone)")?.matches ||
    (navigator as any).standalone === true
  );
}

// In portrait standalone with viewport-fit=cover the app should get the
// whole screen; treat that as the floor for the heal target so a session
// that BOOTS shrunk (maxVH never saw the true height) still heals.
function expectedHeight(): number {
  if (isStandalone() && window.innerWidth < window.innerHeight) {
    return window.screen.height;
  }
  return 0;
}

function noteHeight() {
  maxViewportHeight.value = Math.max(
    maxViewportHeight.value,
    window.innerHeight
  );
}

function healViewport(getScroller: () => HTMLElement | null) {
  const want = Math.max(maxViewportHeight.value, expectedHeight());
  if (want - window.innerHeight <= 4) return;
  const el = document.getElementById("app") || document.body;
  // display:none wipes every descendant's scroll position — snapshot all
  // scrolled elements (rare event, so the full sweep is fine).
  const saves: Array<[HTMLElement, number]> = [];
  for (const n of document.querySelectorAll<HTMLElement>("*")) {
    if (n.scrollTop > 0) saves.push([n, n.scrollTop]);
  }
  el.style.display = "none";
  void el.offsetHeight; // force the reflow WebKit needs to re-measure
  el.style.display = "";
  for (const [n, v] of saves) n.scrollTop = v;
  const scroller = getScroller();
  if (scroller && !saves.some(([n]) => n === scroller)) {
    scroller.scrollTop = 0;
  }
}

/** Install on the mobile shell. Returns a teardown for onUnmounted. */
export function installViewportHeal(
  getScroller: () => HTMLElement | null
): () => void {
  let timer: ReturnType<typeof setTimeout> | null = null;
  const schedule = (delay: number) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => healViewport(getScroller), delay);
  };
  const onFocusOut = (e: FocusEvent) => {
    const t = e.target as HTMLElement | null;
    if (!t?.closest?.("input, textarea, [contenteditable]")) return;
    // The keyboard needs a beat to actually dismiss before re-measuring.
    schedule(150);
  };
  noteHeight();
  window.addEventListener("resize", noteHeight);
  document.addEventListener("focusout", onFocusOut, true);
  schedule(600); // launch heal, in case the session started shrunk
  return () => {
    window.removeEventListener("resize", noteHeight);
    document.removeEventListener("focusout", onFocusOut, true);
    if (timer) clearTimeout(timer);
  };
}
