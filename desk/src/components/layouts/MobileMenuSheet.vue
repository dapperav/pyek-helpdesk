<template>
  <!-- PYEK: the tide menu (Mark's approved Wave design, 2026-08-15). The Menu
       tab makes the sheet RISE like a wave (fast crest, ~0.6s) and recede like
       the tide going out (slow pull, ~0.85s) — the two different easings are
       what sell it. A drifting wave-crest SVG forms the top edge, the body is
       frosted navy glass, and the whole sheet slides up BEHIND the glass bottom
       nav (sheet z-40, nav z-50), blurred through it.
       Always mounted (transform-based show/hide) so the exit animation can
       play — v-if would snap it away. Plain overlay, no headlessui. -->
  <div
    class="fixed inset-0 z-40"
    :class="!sidebarOpened && 'pointer-events-none'"
  >
    <!-- Dimmer is a touch darker than the stock overlay token: the Home
         hero's bright teal wave sat right behind the sheet's crest and cut
         into it visually (Mark, 2026-08-15). -->
    <button
      class="absolute inset-0 transition-opacity duration-500"
      style="background: rgba(8, 15, 30, 0.78)"
      :class="sidebarOpened ? 'opacity-100' : 'opacity-0'"
      :aria-hidden="!sidebarOpened"
      :tabindex="sidebarOpened ? 0 : -1"
      aria-label="Close menu"
      @click="close"
    />
    <div class="tide" :class="sidebarOpened && 'open'" :aria-hidden="!sidebarOpened">
      <div class="overflow-hidden">
        <svg
          class="crest"
          viewBox="0 0 750 40"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <path
            d="M0 24 Q 47 6 94 20 T 188 18 T 282 22 T 375 14 T 470 20 T 564 16 T 658 22 T 750 14 L 750 40 L 0 40 Z"
            fill="rgba(103,232,249,0.35)"
          />
          <!-- Near-opaque so page content (e.g. the hero's teal wave) can't
               bleed through the crest and muddy the sheet's top edge. -->
          <path
            d="M0 30 Q 47 14 94 26 T 188 24 T 282 28 T 375 22 T 470 28 T 564 24 T 658 28 T 750 22 L 750 40 L 0 40 Z"
            fill="rgba(27,42,74,0.97)"
          />
        </svg>
      </div>
      <div class="body">
        <div class="flex items-center gap-2 pb-3 pt-1.5">
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
        <div v-if="statusPicking" class="mb-2 flex flex-wrap gap-2">
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

        <div class="scroll min-h-0 flex-1 overflow-y-auto">
          <template v-if="!isCustomerPortal">
            <p class="grp">{{ __("Queues") }}</p>
            <button
              v-for="view in publicViews"
              :key="view.name"
              class="item"
              @click="view.onClick()"
            >
              <component :is="view.icon" class="ic size-5 shrink-0" />
              {{ view.label }}
            </button>

            <p class="grp">{{ __("Workspace") }}</p>
            <button class="item" @click="go('Notifications')">
              <LucideBell class="ic size-5 shrink-0" />
              {{ __("Notifications") }}
              <span v-if="notificationStore.unread" class="badge">
                {{ notificationStore.unread > 9 ? "9+" : notificationStore.unread }}
              </span>
            </button>
            <button class="item" @click="go('AgentKnowledgeBase')">
              <LucideBookOpen class="ic size-5 shrink-0" />
              {{ __("Knowledge Base") }}
              <span v-if="kbConfirmCount.data" class="badge">
                {{ kbConfirmCount.data > 9 ? "9+" : kbConfirmCount.data }}
              </span>
            </button>
            <button class="item" @click="openCustomerPortal">
              <LucideUsers class="ic size-5 shrink-0" />
              {{ __("Customer portal") }}
            </button>

            <p class="grp">{{ __("This device") }}</p>
            <button
              v-if="pushState !== 'unsupported'"
              class="item"
              @click="togglePush()"
            >
              <LucideBellRing v-if="pushState === 'on'" class="ic size-5 shrink-0" />
              <LucideBellPlus v-else class="ic size-5 shrink-0" />
              {{ pushLabel }}
            </button>
            <button class="item" @click="go('NotificationSettings')">
              <LucideSlidersHorizontal class="ic size-5 shrink-0" />
              {{ __("Notification settings") }}
            </button>
          </template>

          <!-- Customers keep a route to their ticket list. -->
          <button
            v-if="isCustomerPortal"
            class="item"
            @click="go('TicketsCustomer')"
          >
            <LucideTicket class="ic size-5 shrink-0" />
            {{ __("My tickets") }}
          </button>
          <button class="item" @click="toggleTheme()">
            <LucideSun v-if="currentTheme === 'dark'" class="ic size-5 shrink-0" />
            <LucideMoon v-else class="ic size-5 shrink-0" />
            {{ __("Toggle theme") }}
          </button>
          <button class="item" @click="authStore.logout()">
            <LucideLogOut class="ic size-5 shrink-0" />
            {{ __("Log out") }}
          </button>
          <!-- Shell geometry readout (temporary diagnostic, 2026-08-15): the
               bottom-nav band on Mark's iPhone has survived two blind fixes,
               so this prints the real numbers where he can screenshot them —
               a standalone PWA has no address bar for a ?debug URL. Remove
               once the band is understood and fixed. -->
          <p class="mt-3 text-center text-[10px] leading-4 text-white/40">
            {{ shellGeo }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import PyekMark from "@/components/PyekMark.vue";
import UserAvatar from "@/components/UserAvatar.vue";
import { mobileSidebarOpened as sidebarOpened } from "@/composables/mobile";
import { maxViewportHeight } from "@/composables/viewportHeal";
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

// Shell geometry (diagnostic — see the template note). Measured on each open
// so the numbers reflect the moment Mark screenshots them. "b4" is the build
// tag — bump it whenever this line's build changes, so a screenshot is never
// ambiguous about which deploy it came from.
const shellGeo = ref("");
function envProbe(edge: "top" | "bottom"): number {
  const probe = document.createElement("div");
  probe.style.cssText = `position:fixed;${edge}:0;left:0;width:1px;visibility:hidden;height:env(safe-area-inset-${edge})`;
  document.body.appendChild(probe);
  const v = probe.getBoundingClientRect().height;
  probe.remove();
  return Math.round(v);
}
watch(sidebarOpened, (open) => {
  if (!open) return;
  try {
    const nav = document.querySelector(".glassnav");
    const navRect = nav?.getBoundingClientRect();
    const drop = nav ? getComputedStyle(nav).bottom : "?";
    shellGeo.value =
      `b9 · drop ${drop}` +
      ` · ih ${window.innerHeight}` +
      ` · max ${maxViewportHeight.value}` +
      ` · scr ${screen.height}` +
      ` · envT ${envProbe("top")} · envB ${envProbe("bottom")}` +
      ` · nav ${Math.round(navRect?.top ?? -1)}–${Math.round(navRect?.bottom ?? -1)}`;
  } catch (e) {
    shellGeo.value = String(e);
  }
});

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
/* The tide: base rule carries the CLOSING transition (slow pull, tide going
   out); .open carries the OPENING one (fast rise, soft crest overshoot).
   CSS applies the destination state's transition, so each direction gets its
   own feel from just these two rules. */
.tide {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  max-height: 88dvh;
  transform: translateY(103%);
  transition: transform 0.85s cubic-bezier(0.5, 0, 0.75, 0.6);
}
.tide.open {
  transform: translateY(0);
  transition: transform 0.6s cubic-bezier(0.22, 1.1, 0.32, 1);
}
.crest {
  display: block;
  width: 200%;
  margin-bottom: -1px;
  animation: drift 7s ease-in-out infinite alternate;
}
@keyframes drift {
  from {
    transform: translateX(0);
  }
  to {
    transform: translateX(-12%);
  }
}
/* Frosted navy glass; the sheet rises behind the glass nav, so leave room for
   it (--pyek-nav-h set by MobileLayout) plus the home-indicator inset. */
.body {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 4px 20px calc(var(--pyek-nav-h, 60px) + 10px);
  color: #fff;
  background: rgba(27, 42, 74, 0.82);
  -webkit-backdrop-filter: blur(22px) saturate(1.5);
  backdrop-filter: blur(22px) saturate(1.5);
}
.grp {
  margin: 10px 0 4px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.45);
}
.item {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 10px;
  padding: 9px 0;
  text-align: left;
  font-size: 14.5px;
  color: rgba(255, 255, 255, 0.92);
}
.item:active {
  color: #fff;
}
.ic {
  color: #67e8f9;
}
.badge {
  margin-left: auto;
  border-radius: 9999px;
  background: #2563eb;
  padding: 2px 7px;
  font-size: 10.5px;
  font-weight: 700;
  color: #fff;
}
@media (prefers-reduced-motion: reduce) {
  .crest {
    animation: none;
  }
  .tide,
  .tide.open {
    transition-duration: 0.01s;
  }
}
</style>
