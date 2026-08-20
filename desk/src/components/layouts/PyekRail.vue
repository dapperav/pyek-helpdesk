<template>
  <!-- PYEK captioned rail (Mark, 2026-08-20: "icons alone are guesswork").
       The default desktop sidebar: 4.5rem wide, every icon wearing a small
       caption, items grouped under hairline rules. frappe-ui's SidebarItem
       can't carry this — its row is a fixed 28px with the label collapsed to
       zero width — so the rail is its own component and the 15rem panel stays
       stock SidebarItem. Colors come from the navy [data-slot="sidebar"] vars
       in index.css. -->
  <div class="flex flex-col gap-2">
    <div
      v-for="(group, index) in groups"
      :key="group.key"
      class="flex flex-col gap-0.5"
      :class="index > 0 && 'border-t border-outline-gray-1 pt-2'"
    >
      <span
        v-if="group.label"
        class="select-none pb-0.5 text-center text-[9px] font-semibold uppercase tracking-[0.1em] text-ink-gray-5"
        >{{ group.label }}</span
      >

      <PyekRailItem
        v-for="item in group.items"
        :key="item.key"
        :id="item.id"
        :caption="item.caption"
        :label="item.label"
        :icon="item.icon"
        :active="item.isActive"
        :count="item.count"
        :badge="item.key === 'notifications' ? 0 : item.badge"
        :dot="item.key === 'notifications' && !!item.badge"
        @click="item.onClick && item.onClick()"
      >
        <template v-if="item.key === 'notifications'" #overlay>
          <EchoPeek :active="bellPeek" :width="26" :overlap="6" left="-5px" />
        </template>
      </PyekRailItem>
    </div>
  </div>
</template>

<script setup lang="ts">
import EchoPeek from "@/components/echo/EchoPeek.vue";
import PyekRailItem from "@/components/layouts/PyekRailItem.vue";

export type RailItem = {
  key: string;
  id?: string;
  caption: string;
  label: string;
  icon: any;
  isActive?: boolean;
  onClick?: () => void;
  count?: number;
  badge?: number;
};

defineProps<{
  groups: { key: string; label: string; items: RailItem[] }[];
  // The bell's Echo peek is owned by AppSidebar (it watches the notification
  // store); the rail only needs to know whether he's up.
  bellPeek?: boolean;
}>();
</script>
