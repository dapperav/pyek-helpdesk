import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { useStorage } from "@vueuse/core";

export const useSidebarStore = defineStore("sidebar", () => {
  const isOpen = ref(true);
  // The icon rail is the default (Mark, 2026-08-18): navigation collapsed to
  // icons everywhere; Home's pools carry the views. New storage key on
  // purpose — everyone lands on the rail once, and their own toggle sticks
  // from there.
  const isExpanded = useStorage("sidebar_rail_expanded", false);
  // Match frappe-ui Sidebar's width/collapsedWidth props (15rem/4.5rem),
  // since the notifications panel anchors against this value. The rail grew
  // from 3rem to 4.5rem on 2026-08-20 to fit a caption under every icon
  // (Mark: "icons alone are guesswork"); AppSidebar passes the same value as
  // :collapsed-width, so the two must move together.
  const width = computed(() => {
    return isExpanded.value ? "15rem" : "4.5rem";
  });

  function toggle(state?: boolean) {
    isOpen.value = state ?? !isOpen.value;
  }

  function toggleExpanded(state?: boolean) {
    isExpanded.value = state ?? !isExpanded.value;
  }

  return {
    isExpanded,
    isOpen,
    toggle,
    toggleExpanded,
    width,
  };
});
