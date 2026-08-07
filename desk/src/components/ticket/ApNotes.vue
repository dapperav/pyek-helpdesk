<template>
  <!-- Quick internal note, at the bottom of the invoice card. Posts a real HD Ticket
       Comment (the same thing the Comments tab writes), so a note taken here is
       visible everywhere comments are and is never emailed to the vendor. Shows the
       last few inline so you can read and add without leaving the card — this
       replaced the separate "Recent Comments" panel rather than sitting next to it. -->
  <div class="mt-3 border-t border-outline-gray-2 pt-3">
    <p class="mb-1.5 px-0.5 text-xs font-medium uppercase tracking-wide text-ink-gray-5">
      {{ __("Notes") }}
    </p>

    <ul v-if="recent.length" class="mb-2 flex flex-col gap-1.5">
      <li
        v-for="c in recent"
        :key="c.name"
        class="rounded-lg bg-surface-gray-2 px-2.5 py-2"
      >
        <div class="mb-0.5 flex items-center gap-2">
          <span class="min-w-0 flex-1 truncate text-xs font-medium text-ink-gray-7">
            {{ c.authorName }}
          </span>
          <span class="shrink-0 text-xs text-ink-gray-5">{{ timeAgo(c.creation) }}</span>
        </div>
        <p v-if="c.preview" class="note-preview text-sm text-ink-gray-7 break-words">
          {{ c.preview }}
        </p>
        <p v-else class="text-sm italic text-ink-gray-4">
          {{ __("Attachment / no text") }}
        </p>
      </li>
    </ul>

    <textarea
      v-model="draft"
      rows="2"
      :placeholder="__('Add a note…')"
      class="w-full resize-y rounded-lg border border-outline-gray-2 bg-surface-white px-2.5 py-2 text-base text-ink-gray-8 outline-none placeholder:text-ink-gray-4 focus:border-outline-gray-3"
      @keydown.meta.enter="post"
      @keydown.ctrl.enter="post"
    />
    <button
      v-if="draft.trim()"
      class="mt-1.5 flex w-full items-center justify-center gap-2 rounded-lg py-2 text-base-medium text-white disabled:opacity-60"
      style="background-color: #1b2a4a"
      :disabled="posting"
      @click="post"
    >
      <LucideMessageSquarePlus class="size-4" />
      {{ posting ? __("Posting…") : __("Post note") }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, ref } from "vue";
import { call, toast } from "frappe-ui";
import { ActivitiesSymbol, TicketSymbol } from "@/types";
import { useUserStore } from "@/stores/user";
import { timeAgo } from "@/utils";
import { __ } from "@/translation";
import LucideMessageSquarePlus from "~icons/lucide/message-square-plus";

const props = defineProps<{ ticket: Record<string, any> }>();
const activities = inject(ActivitiesSymbol, undefined);
const ticketRes = inject(TicketSymbol, undefined);
const { getUser } = useUserStore();

function stripHtml(html: string) {
  const div = document.createElement("div");
  div.innerHTML = html || "";
  return (div.textContent || div.innerText || "").replace(/\s+/g, " ").trim();
}

const recent = computed(() => {
  const comments = activities?.value?.data?.comments || [];
  return [...comments]
    .sort((a: any, b: any) => new Date(b.creation).getTime() - new Date(a.creation).getTime())
    .slice(0, 3)
    .map((c: any) => ({
      name: c.name,
      creation: c.creation,
      authorName:
        c.user?.name || getUser(c.commented_by)?.full_name || c.commented_by,
      preview: stripHtml(c.content),
    }));
});

const draft = ref("");
const posting = ref(false);

// The comment body is stored as HTML, but this box takes plain text — escape it and
// wrap each line in a paragraph so a pasted note can't inject markup into the thread.
function toHtml(text: string) {
  const esc = (s: string) =>
    s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  return text
    .split(/\n+/)
    .map((line) => `<p>${esc(line)}</p>`)
    .join("");
}

async function post() {
  const text = draft.value.trim();
  if (!text || posting.value || !props.ticket?.name) return;
  posting.value = true;
  try {
    await call("run_doc_method", {
      dt: "HD Ticket",
      dn: props.ticket.name,
      method: "new_comment",
      args: { content: toHtml(text), attachments: [] },
    });
    draft.value = "";
    // Pull the thread back so the note shows here and in the Comments tab at once.
    await activities?.value?.reload?.();
    await ticketRes?.value?.reload?.();
    toast.success(__("Note added"));
  } catch (e) {
    toast.error(__("Couldn't add the note. Try again."));
  } finally {
    posting.value = false;
  }
}
</script>

<style scoped>
.note-preview {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
