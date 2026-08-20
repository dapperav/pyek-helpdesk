<template>
  <!-- One button of the captioned rail. Shared so that everything on the rail
       wears a word — the nav items, the Help entry Sidebar.vue passes through
       the footer slot, and the expand toggle — instead of the nav being
       captioned and the chrome below it staying a bare glyph.
       data-slot/data-state let index.css's [data-slot="sidebar"] rules draw
       the bright active accent bar for free. -->
  <Tooltip :text="label || caption" placement="right">
    <button
      :id="id"
      type="button"
      data-slot="sidebar-item"
      :data-state="active ? 'active' : 'inactive'"
      :aria-current="active ? 'page' : undefined"
      class="flex w-full flex-col items-center gap-1 rounded px-0.5 py-1.5 transition"
      :class="
        active
          ? 'bg-surface-elevation-3 text-ink-gray-8 shadow-sm'
          : 'text-ink-gray-6 hover:bg-surface-gray-2'
      "
      @click="$emit('click')"
    >
      <span
        class="relative grid size-5 shrink-0 place-items-center"
        :class="active ? 'text-ink-gray-8' : 'text-ink-gray-7'"
      >
        <!-- Echo peeks over the bell from here (echo-eggs round, 2026-08-19). -->
        <slot name="overlay" />
        <component :is="icon" class="size-[18px]" />
        <!-- Unread notifications keep red to themselves; live queue counts
             wear the cyan pill, and a nudge-count (KB confirms) wears slate. -->
        <span
          v-if="dot"
          class="absolute -right-1 -top-1 size-1.5 rounded-full bg-surface-blue-5"
        />
        <span v-else-if="count" class="pyek-railcount">{{
          count > 99 ? "99+" : count
        }}</span>
        <span v-else-if="badge" class="pyek-railcount pyek-railcount-gray">{{
          badge > 9 ? "9+" : badge
        }}</span>
      </span>
      <span class="max-w-full truncate text-[10px] font-medium leading-none">{{
        caption
      }}</span>
    </button>
  </Tooltip>
</template>

<script setup lang="ts">
import { Tooltip } from "frappe-ui";

defineProps<{
  // The word under the icon — it has to survive a 4.5rem column, so it is
  // sometimes shorter than `label` (the tooltip's full name).
  caption: string;
  label?: string;
  icon: any;
  id?: string;
  active?: boolean;
  count?: number;
  badge?: number;
  dot?: boolean;
}>();

defineEmits<{ click: [] }>();
</script>
