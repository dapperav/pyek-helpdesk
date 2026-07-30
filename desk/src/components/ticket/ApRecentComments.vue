<template>
  <!-- AP-only quick glance: the 3 most recent internal comments on THIS ticket.
       Clicking one jumps to that comment in the activity panel and highlights it.
       Renders nothing on IT/HR tickets (no ap_vendor) or when there are no
       comments. -->
  <div
    v-if="isAP && recentComments.length"
    class="mx-5 mt-3 rounded-xl border border-outline-gray-2 bg-surface-white overflow-hidden"
  >
    <Section label="Recent Comments" v-model:opened="opened">
      <template #header="{ opened, toggle }">
        <div
          class="flex gap-2.5 items-center justify-between sticky top-0 bg-surface-base z-10 px-4 py-4 cursor-pointer"
          @click="toggle"
        >
          <span class="text-ink-gray-8 text-base-semibold select-none">
            {{ __("Recent Comments") }}
          </span>
          <LucideChevronRight
            class="size-4 text-ink-gray-6"
            :class="{ 'rotate-90': opened }"
          />
        </div>
      </template>
      <ul class="px-4 pb-4 pt-0 space-y-0.5">
        <li
          v-for="c in recentComments"
          :key="c.name"
          @click="jumpToComment(c)"
        >
          <div
            class="-mx-2 px-2 py-2 cursor-pointer rounded hover:bg-surface-gray-2 transition-colors"
          >
            <div class="mb-1 flex items-center gap-2">
              <Avatar
                size="sm"
                :label="c.authorName"
                :image="getUser(c.commented_by).user_image"
              />
              <span class="min-w-0 flex-1 truncate text-sm font-medium text-ink-gray-8">
                {{ c.authorName }}
              </span>
              <span class="shrink-0 text-xs text-ink-gray-5">
                {{ timeAgo(c.creation) }}
              </span>
            </div>
            <p v-if="c.preview" class="comment-preview text-sm text-ink-gray-6 break-words">
              {{ c.preview }}
            </p>
            <p v-else class="text-sm italic text-ink-gray-4">
              {{ __("Attachment / no text") }}
            </p>
          </div>
        </li>
      </ul>
    </Section>
  </div>
</template>

<script setup lang="ts">
import { ActivitiesSymbol, TicketSymbol } from "@/types";
import { useUserStore } from "@/stores/user";
import { timeAgo } from "@/utils";
import { useStorage } from "@vueuse/core";
import { Avatar } from "frappe-ui";
import { computed, inject, nextTick } from "vue";
import { useRoute, useRouter } from "vue-router";
import LucideChevronRight from "~icons/lucide/chevron-right";
import Section from "../Section.vue";

const ticket = inject(TicketSymbol)!;
const activities = inject(ActivitiesSymbol)!;
const { getUser } = useUserStore();
const route = useRoute();
const router = useRouter();

// Persisted collapse state; default open — this is a quick-glance panel.
const opened = useStorage("apRecentCommentsOpen", true, localStorage);

const isAP = computed(
  () => !!ticket.value?.doc && "ap_vendor" in ticket.value.doc
);

// Strip HTML from the stored comment body for a plain-text preview.
function stripHtml(html: string) {
  const div = document.createElement("div");
  div.innerHTML = html || "";
  return (div.textContent || div.innerText || "").replace(/\s+/g, " ").trim();
}

const recentComments = computed(() => {
  const comments = activities.value?.data?.comments || [];
  return [...comments]
    .sort(
      (a, b) => new Date(b.creation).getTime() - new Date(a.creation).getTime()
    )
    .slice(0, 3)
    .map((c: any) => ({
      name: c.name,
      creation: c.creation,
      commented_by: c.commented_by,
      // Backend enriches each comment with a resolved `user` object; fall back
      // to the users store, then the raw email.
      authorName:
        c.user?.name || getUser(c.commented_by)?.full_name || c.commented_by,
      preview: stripHtml(c.content),
    }));
});

// Jump to the comment in the activity panel and briefly highlight it. The
// comment renders (wrapper id = its creation timestamp) on both the Activity and
// Comments tabs, so if it's already on screen we scroll in place; otherwise we
// switch to the Comments tab and scroll once it renders.
function jumpToComment(c: { creation: string }) {
  const scrollTo = () => {
    // getElementById (not a CSS selector) — the id is an ISO timestamp with
    // spaces/colons that a selector can't match.
    const el = document.getElementById(c.creation);
    if (!el) return false;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.add("bg-surface-yellow-2", "rounded-lg", "transition-colors");
    setTimeout(() => el.classList.remove("bg-surface-yellow-2"), 2000);
    return true;
  };
  if (scrollTo()) return;
  if (route.hash !== "#comment") router.push({ hash: "comment" });
  nextTick(() => setTimeout(scrollTo, 350));
}
</script>

<style scoped>
.comment-preview {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
