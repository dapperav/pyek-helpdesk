import { ref } from "vue";

// TEMP diagnostic: last router/async-load error, surfaced in the mobile header
// debug line so a device screenshot reveals why /home fails to mount in the PWA.
export const lastError = ref("");
