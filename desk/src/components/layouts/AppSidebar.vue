<template>
  <Sidebar
    v-model:collapsed="collapsed"
    :disable-collapse="mobile"
    class="border-e border-outline-gray-1"
  >
    <!-- On the mobile drawer, clear the iOS status-bar inset so the brand
         doesn't render behind the clock (the navy sidebar bg fills the notch
         strip). Desktop is unaffected. -->
    <div
      class="flex h-full flex-col p-2"
      :style="mobile ? { paddingTop: 'calc(0.5rem + env(safe-area-inset-top))' } : {}"
    >
      <UserMenu :options="profileSettings" :is-collapsed="isCollapsed" />

      <ScrollArea class="mt-2 min-h-0 flex-1 -mx-2" viewport-class="px-2">
        <template v-for="(section, index) in sections" :key="index">
          <SidebarLabel
            v-if="section.label"
            divider
            class="my-1 select-none"
            :class="section.collapsible && !isCollapsed && 'cursor-pointer'"
            @click="section.collapsible && toggleSection(section.label)"
          >
            <span class="flex items-center gap-1.5 text-sm font-medium">
              <span
                class="lucide-chevron-right size-4 shrink-0 text-ink-gray-9 transition-transform duration-300 ease-in-out"
                :class="{ 'rotate-90': isSectionOpen(section.label) }"
              />
              <span class="truncate">{{ section.label }}</span>
            </span>
          </SidebarLabel>
          <nav
            v-if="!section.label || isSectionOpen(section.label)"
            class="flex flex-col gap-0.5"
          >
            <SidebarItem
              v-for="item in section.items"
              :key="item.key"
              :id="item.id"
              :label="__(item.label)"
              :active="item.isActive"
              :class="item.spacedTop && 'mt-4'"
              @click="item.onClick && item.onClick()"
            >
              <template #prefix>
                <span
                  class="relative grid size-4 shrink-0 place-items-center text-ink-gray-7"
                >
                  <component :is="item.icon" class="size-4" />
                  <span
                    v-if="item.key === 'notifications' && item.badge"
                    class="absolute -right-0.5 -top-0.5 size-1.5 rounded-full bg-surface-blue-5"
                  />
                  <!-- Live queue count (POS/IT/Mine): cyan pill riding the
                       icon so it reads on the collapsed rail too. Red stays
                       reserved for the notifications bell. -->
                  <span v-else-if="item.count" class="pyek-railcount">{{
                    item.count > 99 ? "99+" : item.count
                  }}</span>
                </span>
              </template>
              <template #suffix>
                <span
                  v-if="item.shortcut"
                  class="me-2 flex items-center gap-0.5 font-medium text-ink-gray-5"
                >
                  <component :is="device.modifierIcon" class="h-3 w-3" />
                  <span class="text-sm">K</span>
                </span>
                <Badge
                  v-else-if="item.badge"
                  class="me-2"
                  :label="item.badge > 9 ? '9+' : item.badge"
                  theme="gray"
                  variant="subtle"
                />
                <Dropdown
                  v-else-if="item.view"
                  side="right"
                  align="start"
                  :options="viewActions(item.view, viewDialogConfig)"
                >
                  <template #default="{ open }">
                    <Button
                      variant="ghost"
                      icon="lucide-more-horizontal"
                      class="me-1 !size-6 rounded !text-ink-gray-7"
                      :class="
                        open
                          ? 'opacity-100'
                          : 'opacity-0 group-hover/sidebar-item:opacity-100'
                      "
                      @click.stop
                    />
                  </template>
                </Dropdown>
              </template>
            </SidebarItem>
          </nav>
        </template>
      </ScrollArea>

      <div class="mt-auto flex flex-col gap-2">
        <slot name="footer" :is-collapsed="isCollapsed" />
        <SidebarCollapseToggle v-if="!mobile" />
      </div>
    </div>
  </Sidebar>
  <CP v-if="!mobile" v-model="showCommandPalette" />
  <ViewModal
    v-if="viewDialogConfig.show"
    v-model="viewDialogConfig"
    @update="(view, action) => handleView(view, action, viewDialogConfig)"
  />
</template>

<script setup lang="ts">
import CP from "@/components/command-palette/CP.vue";
import UserMenu from "@/components/UserMenu.vue";
import { useDevice } from "@/composables";
import { currentView, useView } from "@/composables/useView";
import { useNotificationStore } from "@/stores/notification";
import { useQueueCountsStore } from "@/stores/queueCounts";
import { useSidebarStore } from "@/stores/sidebar";
import { useTelephonyStore } from "@/stores/telephony";
import { __ } from "@/translation";
import { getIcon, isCustomerPortal } from "@/utils";
import ViewModal from "@/components/ViewModal.vue";
import {
  Badge,
  Button,
  createResource,
  Dropdown,
  ScrollArea,
  Sidebar,
  SidebarCollapseToggle,
  SidebarItem,
  SidebarLabel,
} from "frappe-ui";
import { storeToRefs } from "pinia";
import { computed, reactive, ref, watch } from "vue";
import type { RouteLocationRaw } from "vue-router";
import { useRoute, useRouter } from "vue-router";
import LucideBell from "~icons/lucide/bell";
import LucideSearch from "~icons/lucide/search";
import {
  agentPortalSidebarOptions,
  customerPortalSidebarOptions,
} from "./layoutSettings";

const props = defineProps<{
  profileSettings: any[];
  mobile?: boolean;
}>();

const route = useRoute();
const router = useRouter();
const device = useDevice();
const notificationStore = useNotificationStore();
const sidebarStore = useSidebarStore();
const { isCallingEnabled } = storeToRefs(useTelephonyStore());
const { pinnedViews, publicViews, viewActions, handleView } = useView();

// Rail queue counts (agent portal only): started once, shared store.
const queueCounts = useQueueCountsStore();
if (!isCustomerPortal.value) queueCounts.start();

// Saved-view labels are stable across sites; names are not — resolve at
// click/render time from the loaded public views.
function publicViewByLabel(label: string) {
  return (publicViews.value || []).find((v: any) => v.label === label);
}

const showCommandPalette = ref(false);

// Local modal state for the per-view kebab menu (edit/duplicate). The action
// logic itself is shared via useView so the sidebar and breadcrumb stay in sync.
const viewDialogConfig = reactive({
  show: false,
  view: { label: "", icon: "", name: "" },
  mode: "create",
});

const collapsed = computed({
  get: () => !sidebarStore.isExpanded,
  set: (value) => sidebarStore.toggleExpanded(!value),
});

// The mobile drawer pins the sidebar open (disable-collapse), so it is never
// visually collapsed even when the store says so.
const isCollapsed = computed(() => collapsed.value && !props.mobile);

// Expanded/folded state of the collapsible view sections, keyed by label.
const closedSections = ref(new Set<string>());
const isSectionOpen = (label: string) => !closedSections.value.has(label);

function toggleSection(label: string) {
  if (isSectionOpen(label)) closedSections.value.add(label);
  else closedSections.value.delete(label);
}

// Optimistic active item: set immediately on click so the highlight is
// instant, then kept in sync with the route (browser back/forward, external
// navigation). A view's key is its name; a nav item's key is its route name.
const activeItem = ref<string | null>(currentRouteKey());

function currentRouteKey(): string | null {
  return (route.query.view as string) || (route.name as string) || null;
}

function selectItem(key: string, to: RouteLocationRaw, onSelect?: () => void) {
  activeItem.value = key;
  onSelect?.();
  router.push(to);
}

// KB articles still awaiting an SME confirm (Allannha for POS, Mark/Brannan
// for IT) — shown as a badge on the Knowledge Base entry so the queue burns
// down by being seen. Cached; agents only (the API returns 0 for others).
const kbConfirmCount = createResource({
  url: "helpdesk.api.knowledge_base.get_confirm_pending_count",
  cache: "kb-confirm-pending-count",
  auto: !isCustomerPortal.value,
});

const navItems = computed(() => {
  const options = isCustomerPortal.value
    ? customerPortalSidebarOptions
    : agentPortalSidebarOptions;
  return options
    .filter((item) => isCallingEnabled.value || item.label !== __("Call Logs"))
    .map((option: any, index: number) => {
      // Queue jump (POS/IT/Mine): opens the saved view, wears its live count.
      if (option.view) {
        const v = publicViewByLabel(option.view);
        return {
          label: option.label,
          icon: option.icon,
          isActive: !!v && activeItem.value === v.name,
          onClick: () => {
            const target = publicViewByLabel(option.view);
            if (!target) return; // views still loading — next click lands
            selectItem(
              target.name,
              { name: "TicketsAgent", query: { view: target.name } },
              () => {
                currentView.value = { label: target.label, icon: target.icon };
              }
            );
          },
          spacedTop: !!option.spacedTop,
          key: "view:" + option.view,
          count: queueCounts.counts[option.countKey] || 0,
          badge: 0,
        };
      }
      // Analytics: a jump to Home's chart section, not a place — never active.
      if (option.hash) {
        return {
          label: option.label,
          icon: option.icon,
          isActive: false,
          onClick: () => router.push({ name: option.to, hash: option.hash }),
          spacedTop: !!option.spacedTop,
          key: "hash:" + option.hash,
          badge: 0,
        };
      }
      return {
        label: option.label,
        icon: option.icon,
        isActive: activeItem.value === option.to,
        onClick: () => selectItem(option.to, { name: option.to }),
        // Separate the nav group from the search/notification tools above it.
        spacedTop:
          !!option.spacedTop || (index === 0 && !isCustomerPortal.value),
        key: option.label,
        badge:
          option.to === "AgentKnowledgeBase" ? kbConfirmCount.data || 0 : 0,
      };
    });
});

const searchItem = computed(() => ({
  label: __("Search"),
  icon: LucideSearch,
  onClick: () => (showCommandPalette.value = true),
  shortcut: true,
  key: "search",
}));

// The Notifications panel's click-outside handler ignores #notifications-btn,
// so this item's own click stays the single owner of open/close.
const notificationItem = computed(() =>
  props.mobile
    ? {
        label: __("Notifications"),
        icon: LucideBell,
        isActive: activeItem.value === "Notifications",
        onClick: () => selectItem("Notifications", { name: "Notifications" }),
        badge: notificationStore.unread,
        key: "notifications",
        id: "notifications-btn",
      }
    : {
        label: __("Notifications"),
        icon: LucideBell,
        onClick: () => notificationStore.toggle(),
        badge: notificationStore.unread,
        key: "notifications",
        id: "notifications-btn",
      }
);

const mainItems = computed(() => {
  if (isCustomerPortal.value) return navItems.value;
  const top = props.mobile
    ? [notificationItem.value]
    : [searchItem.value, notificationItem.value];
  return [...top, ...navItems.value];
});

const sections = computed(() => {
  const result = [{ label: "", items: mainItems.value, collapsible: false }];
  // Public Views left the sidebar (Mark, 2026-08-18): the Home board's pools
  // ARE the public views now. Private views stay — they have no Home
  // representation and are personal by definition.
  if (pinnedViews.value?.length) {
    result.push({
      label: __("Private Views"),
      items: parseViews(pinnedViews.value),
      collapsible: true,
    });
  }
  return result;
});

function parseViews(views: any[]) {
  return views.map((view) => ({
    label: view.label,
    icon: getIcon(view.icon),
    isActive: activeItem.value === view.name,
    onClick: () =>
      selectItem(
        view.name,
        { name: view.route_name, query: { view: view.name } },
        () => {
          currentView.value = { label: view.label, icon: view.icon };
        }
      ),
    key: view.name,
    view,
  }));
}

watch(
  () => [route.name, route.query.view],
  () => (activeItem.value = currentRouteKey())
);
</script>

<style>
/* The rail's navy theme itself already ships in index.css, scoped to
   [data-slot="sidebar"] (the PYEK BRANDING block) — nothing to restyle here.

   Live queue count riding a rail icon: cyan pill, red stays the bell's. */
.pyek-railcount {
  position: absolute;
  right: -10px;
  top: -8px;
  min-width: 15px;
  height: 15px;
  padding: 0 3.5px;
  border-radius: 8px;
  background: #0891b2;
  color: #fff;
  font-size: 9px;
  font-weight: 700;
  line-height: 1;
  display: grid;
  place-items: center;
  font-variant-numeric: tabular-nums;
}
</style>
