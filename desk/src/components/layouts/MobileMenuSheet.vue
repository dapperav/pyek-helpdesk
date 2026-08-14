<template>
  <!-- PYEK: the branded replacement for the old mobile drawer, which wrapped the
       DESKTOP AppSidebar in a sheet — stock Frappe chrome that looked bolted on
       next to the navy shell. This is a bottom sheet in the same design language
       as TicketActionSheet (Mark's pick, 2026-08-14): navy brand header with the
       agent's identity + availability, the saved queues, and the device/account
       rows. Opened by the bottom bar's Menu tab (same `mobileSidebarOpened` ref
       the drawer used). Plain overlay, no headlessui — which also sidesteps the
       drawer's empty-render wart under vite dev. -->
  <div v-if="sidebarOpened" class="fixed inset-0 z-50" @click.self="close">
    <div class="absolute inset-0 bg-black-overlay-400" @click="close" />
    <div
      class="absolute inset-x-0 bottom-0 flex max-h-[85dvh] flex-col overflow-hidden rounded-t-2xl shadow-2xl bg-surface-base"
    >
      <!-- Navy brand header -->
      <div class="shrink-0 px-5 pb-4 pt-2.5" style="background-color: #1b2a4a">
        <div class="mx-auto mb-3 h-1 w-9 rounded-full bg-white/30" />
        <div class="flex items-center gap-2">
          <PyekMark class="h-5 w-auto shrink-0" />
          <span class="text-base tracking-tight">
            <span class="font-bold text-white">PYEK</span
            ><span class="font-medium" style="color: #67e8f9">MAIL</span>
          </span>
          <div
            v-if="!isCustomerPortal"
            class="ms-auto flex min-w-0 items-center gap-2.5"
          >
            <UserAvatar :name="userId" size="lg" />
            <div class="min-w-0">
              <p class="truncate text-sm font-medium text-white">
                {{ userName }}
              </p>
              <!-- Availability: tap toggles the chip row below. -->
              <button
                v-if="authStore.hasAgentRecord"
                class="flex items-center gap-1.5 text-xs text-white/70 active:text-white"
                @click="statusPicking = !statusPicking"
              >
                <span
                  class="size-2 shrink-0 rounded-full"
                  :class="agentStatusStore.statusColor(agentStatusStore.myStatus)"
                />
                {{
                  agentStatusStore.myStatus
                    ? __(agentStatusStore.myStatus)
                    : __("Set status")
                }}
                <LucideChevronDown class="size-3" />
              </button>
            </div>
          </div>
        </div>
        <div v-if="statusPicking" class="mt-3 flex flex-wrap gap-2">
          <button
            v-for="option in agentStatusStore.statusOptions"
            :key="option"
            class="flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1.5 text-xs font-medium text-white active:bg-white/20"
            @click="selectStatus(option)"
          >
            <span
              class="size-2 shrink-0 rounded-full"
              :class="agentStatusStore.statusColor(option)"
            />
            {{ __(option) }}
          </button>
        </div>
      </div>

      <!-- Scrollable body -->
      <div
        class="min-h-0 flex-1 overflow-y-auto"
        style="padding-bottom: env(safe-area-inset-bottom)"
      >
        <template v-if="!isCustomerPortal">
          <p class="menu-section">{{ __("Queues") }}</p>
          <button
            v-for="view in publicViews"
            :key="view.name"
            class="menu-btn"
            @click="view.onClick()"
          >
            <component
              :is="view.icon"
              class="size-5 shrink-0 text-ink-gray-6"
            />
            {{ view.label }}
          </button>

          <p class="menu-section">{{ __("Workspace") }}</p>
          <button class="menu-btn" @click="go('Notifications')">
            <LucideBell class="size-5 shrink-0 text-ink-gray-6" />
            {{ __("Notifications") }}
            <span v-if="notificationStore.unread" class="menu-badge">
              {{ notificationStore.unread > 9 ? "9+" : notificationStore.unread }}
            </span>
          </button>
          <button class="menu-btn" @click="go('AgentKnowledgeBase')">
            <LucideBookOpen class="size-5 shrink-0 text-ink-gray-6" />
            {{ __("Knowledge Base") }}
            <span v-if="kbConfirmCount.data" class="menu-badge">
              {{ kbConfirmCount.data > 9 ? "9+" : kbConfirmCount.data }}
            </span>
          </button>
          <button class="menu-btn" @click="openCustomerPortal">
            <LucideUsers class="size-5 shrink-0 text-ink-gray-6" />
            {{ __("Customer portal") }}
          </button>

          <p class="menu-section">{{ __("This device") }}</p>
          <button
            v-if="pushState !== 'unsupported'"
            class="menu-btn"
            @click="togglePush()"
          >
            <LucideBellRing
              v-if="pushState === 'on'"
              class="size-5 shrink-0 text-ink-gray-6"
            />
            <LucideBellPlus v-else class="size-5 shrink-0 text-ink-gray-6" />
            {{ pushLabel }}
          </button>
          <button class="menu-btn" @click="go('NotificationSettings')">
            <LucideSlidersHorizontal class="size-5 shrink-0 text-ink-gray-6" />
            {{ __("Notification settings") }}
          </button>
        </template>

        <!-- Customers keep a route to their ticket list — the old drawer's
             sidebar carried it, so the sheet must too. -->
        <button
          v-if="isCustomerPortal"
          class="menu-btn mt-2"
          @click="go('TicketsCustomer')"
        >
          <LucideTicket class="size-5 shrink-0 text-ink-gray-6" />
          {{ __("My tickets") }}
        </button>
        <button class="menu-btn" @click="toggleTheme()">
          <LucideSun
            v-if="currentTheme === 'dark'"
            class="size-5 shrink-0 text-ink-gray-6"
          />
          <LucideMoon v-else class="size-5 shrink-0 text-ink-gray-6" />
          {{ __("Toggle theme") }}
        </button>
        <button class="menu-btn" @click="authStore.logout()">
          <LucideLogOut class="size-5 shrink-0 text-ink-gray-6" />
          {{ __("Log out") }}
        </button>

        <button
          class="w-full border-t border-outline-gray-1 py-3.5 text-center text-sm font-medium text-ink-gray-6"
          @click="close"
        >
          {{ __("Close") }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import PyekMark from "@/components/PyekMark.vue";
import UserAvatar from "@/components/UserAvatar.vue";
import { mobileSidebarOpened as sidebarOpened } from "@/composables/mobile";
import { useView } from "@/composables/useView";
import { pushState, refreshPushState, togglePush } from "@/composables/webPush";
import { useAgentStatusStore } from "@/stores/agentStatus";
import { useAuthStore } from "@/stores/auth";
import { useNotificationStore } from "@/stores/notification";
import { useUserStore } from "@/stores/user";
import { __ } from "@/translation";
import { isCustomerPortal } from "@/utils";
import { createResource, useTheme } from "frappe-ui";
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import LucideBell from "~icons/lucide/bell";
import LucideBellPlus from "~icons/lucide/bell-plus";
import LucideBellRing from "~icons/lucide/bell-ring";
import LucideBookOpen from "~icons/lucide/book-open";
import LucideChevronDown from "~icons/lucide/chevron-down";
import LucideLogOut from "~icons/lucide/log-out";
import LucideMoon from "~icons/lucide/moon";
import LucideSlidersHorizontal from "~icons/lucide/sliders-horizontal";
import LucideSun from "~icons/lucide/sun";
import LucideTicket from "~icons/lucide/ticket";
import LucideUsers from "~icons/lucide/users";

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const agentStatusStore = useAgentStatusStore();
const notificationStore = useNotificationStore();
const { currentTheme, toggleTheme } = useTheme();
const { publicViews } = useView();
const { getUser } = useUserStore();

const { userId } = authStore;
const userName = computed(() => getUser(userId)?.full_name || userId);

const statusPicking = ref(false);

// Same source (and cache key) as the desktop sidebar's KB badge.
const kbConfirmCount = createResource({
  url: "helpdesk.api.knowledge_base.get_confirm_pending_count",
  cache: "kb-confirm-pending-count",
  auto: true,
});

// Read-only: reflects whether this device already has a subscription. Never
// prompts — a permission prompt on load is the fastest route to a permanent
// iOS denial (reversible only in system Settings).
onMounted(refreshPushState);

const pushLabel = computed(() => {
  switch (pushState.value) {
    case "on":
      return __("Notifications on");
    case "working":
      return __("Just a moment…");
    case "denied":
      return __("Notifications blocked");
    default:
      return __("Notify me on this device");
  }
});

function close() {
  sidebarOpened.value = false;
  statusPicking.value = false;
}

function go(routeName: string) {
  router.push({ name: routeName });
}

function openCustomerPortal() {
  const path = router.resolve({ name: "TicketsCustomer" });
  window.open(path.href);
}

function selectStatus(option: string) {
  agentStatusStore.setMyStatus(option);
  statusPicking.value = false;
}

watch(() => route.fullPath, close);
</script>

<style scoped>
.menu-section {
  padding: 14px 20px 4px;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--ink-gray-5);
}
.menu-btn {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  text-align: left;
  font-size: 15px;
  color: var(--ink-gray-8);
}
.menu-btn:active {
  background: var(--surface-gray-2);
}
.menu-badge {
  margin-inline-start: auto;
  min-width: 20px;
  border-radius: 9999px;
  background-color: #2563eb;
  padding: 2px 6px;
  text-align: center;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.2;
  color: white;
}
</style>
