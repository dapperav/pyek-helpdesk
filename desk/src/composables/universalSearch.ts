import { ref } from "vue";

// Global state for the universal ticket search overlay (Mark, 2026-08-18:
// "1 search bar that could look up any ticket by a wild card, no matter the
// status"). Module-level on purpose: one overlay, many openers (rail Search,
// Ctrl+K, /, the tickets-view box).
export const showUniversalSearch = ref(false);
export const universalSearchSeed = ref("");

export function openUniversalSearch(seed = "") {
  universalSearchSeed.value = seed;
  showUniversalSearch.value = true;
}
