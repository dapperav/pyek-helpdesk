<template>
  <!-- Zero-height until pulled, so it costs no layout on a page nobody is
       dragging. The arrow flips once you're past the commit threshold — that
       flip is the whole affordance: it says "let go now and it will refresh". -->
  <div
    class="flex items-center justify-center overflow-hidden transition-[height] duration-100"
    :style="{ height: `${pull}px` }"
  >
    <LoadingIndicator v-if="refreshing" class="size-4 text-ink-gray-5" />
    <LucideArrowDown
      v-else-if="pull > 0"
      class="size-4 text-ink-gray-5 transition-transform duration-150"
      :class="{ 'rotate-180': pull >= threshold }"
    />
  </div>
</template>

<script setup lang="ts">
import { LoadingIndicator } from "frappe-ui";
import LucideArrowDown from "~icons/lucide/arrow-down";

defineProps<{
  pull: number;
  refreshing: boolean;
  threshold: number;
}>();
</script>
