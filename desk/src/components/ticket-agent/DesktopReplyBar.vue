<template>
  <!-- The phone's persistent texting bar, desktop edition (Mark's picks,
       2026-08-18). In-flow under the thread — no fixed positioning, no
       keyboard lift; the desktop viewport doesn't move. Forked from
       MobileReplyFlow's quick bar rather than shared: the mobile flow is
       shipped and loved, and its other half (full-screen composer, SLA pill,
       self-assign-on-send) is deliberately NOT desktop behavior — on desktop
       the escape hatch is the existing EmailEditor and replying never claims
       the ticket. Single root: transient controls inside use
       @mousedown.prevent (the blur-collapse trap, see MobileReplyFlow). -->
  <div class="relative border-t bg-surface-base px-6 md:px-5 pt-1.5">
    <!-- After-send prompt, anchored above the bar. Same wording as the
         phone's toast, but Close routes through the parent so the desktop
         resolution prompt is honored (pick #4). -->
    <div
      v-show="toastVisible"
      class="absolute bottom-full left-1/2 z-20 mb-2 flex -translate-x-1/2 items-center gap-2.5 rounded-xl px-3.5 py-2 shadow-xl"
      style="background: #123d2e"
    >
      <span class="whitespace-nowrap text-sm font-medium text-white">
        {{ __("Sent · Close ticket?") }}
      </span>
      <button
        class="rounded-lg px-3 py-1 text-sm font-semibold text-[#04120c]"
        style="background: #2fb383"
        @click="closeFromToast"
      >
        {{ __("Close") }}
      </button>
    </div>

    <!-- AI draft chip: reply mode, empty input, enricher-grounded draft only
         (same gates as the phone). Click fills the input, stays ignorable. -->
    <button
      v-if="expanded && showAiChip"
      class="mb-1.5 flex w-auto max-w-[640px] items-center gap-2 rounded-xl border border-outline-gray-2 bg-surface-base px-3 py-2 text-left shadow-md"
      @mousedown.prevent
      @click="useAiDraft"
    >
      <LucideSparkles class="size-4 shrink-0 text-ink-gray-6" />
      <span class="flex-1 truncate text-sm text-ink-gray-7">{{ aiPreview }}</span>
      <span class="shrink-0 text-sm font-semibold text-ink-gray-9">
        {{ __("Use") }}
      </span>
    </button>

    <!-- @mention picker, same hand-rolled token-under-caret machinery as the
         phone bar (plain textarea, so no tiptap mention extension here). -->
    <div
      v-if="mentionMatches.length"
      class="absolute bottom-full left-5 z-20 mb-1.5 w-[300px] overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-base shadow-lg"
    >
      <button
        v-for="a in mentionMatches"
        :key="a.user"
        class="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-surface-gray-2"
        @mousedown.prevent
        @click="pickMention(a)"
      >
        <Avatar size="sm" :label="a.agent_name" :image="a.user_image" />
        <span class="text-sm text-ink-gray-8">{{ a.agent_name }}</span>
        <span class="ms-auto truncate text-xs text-ink-gray-4">{{ a.user }}</span>
      </button>
    </div>

    <div v-if="quickAttachments.length" class="mb-1.5 flex flex-wrap gap-1.5">
      <AttachmentItem
        v-for="a in quickAttachments"
        :key="a.file_url"
        :label="a.file_name"
        :url="a.file_url"
      >
        <template #suffix>
          <FeatherIcon
            class="h-3.5"
            name="x"
            @click.self.stop="removeQuickAttachment(a)"
          />
        </template>
      </AttachmentItem>
    </div>

    <div v-if="expanded" class="mb-1.5 flex items-center gap-2">
      <div class="flex rounded-lg bg-surface-gray-2 p-0.5">
        <button
          class="rounded-md px-3 py-0.5 text-xs font-medium"
          :class="
            mode === 'reply'
              ? 'bg-surface-base text-ink-gray-9 shadow-sm'
              : 'text-ink-gray-5'
          "
          @mousedown.prevent
          @click="setMode('reply')"
        >
          {{ __("Reply") }}
        </button>
        <button
          class="rounded-md px-3 py-0.5 text-xs font-medium"
          :class="
            mode === 'note'
              ? 'bg-surface-amber-2 text-ink-amber-6 shadow-sm'
              : 'text-ink-gray-5'
          "
          @mousedown.prevent
          @click="setMode('note')"
        >
          {{ __("Note") }}
        </button>
      </div>
      <span class="truncate text-xs text-ink-gray-5">{{ modeLabel }}</span>
      <span class="ms-auto hidden text-xs text-ink-gray-4 lg:inline">
        {{ __("Esc collapses") }}
      </span>
    </div>

    <div class="flex items-end gap-1.5 pb-2">
      <!-- Close: two clicks on purpose — the first arms it ("Close?"), the
           second hands off to the parent, which asks "what fixed it" when no
           resolution is recorded yet (pick #4: desktop keeps the prompt the
           phone deliberately skips). -->
      <button
        v-if="!expanded && canClose"
        class="flex h-[38px] shrink-0 items-center justify-center rounded-full border transition-colors"
        :class="
          closeArmed
            ? 'border-transparent px-3 text-sm font-semibold text-white'
            : 'w-[38px] border-outline-gray-2 bg-surface-base text-ink-green-3'
        "
        :style="closeArmed ? { backgroundColor: '#2fb383' } : {}"
        :aria-label="__('Close ticket')"
        @click="tapClose"
      >
        <template v-if="closeArmed">{{ __("Close?") }}</template>
        <LucideCircleCheck v-else class="size-4.5" />
      </button>
      <FileUploader
        v-if="expanded"
        class="shrink-0"
        :upload-args="{ doctype: 'HD Ticket', docname: tid, private: true }"
        @success="(f) => quickAttachments.push(f)"
      >
        <template #default="{ openFileSelector, uploading }">
          <button
            class="flex h-[38px] w-9 shrink-0 items-center justify-center text-ink-gray-5 disabled:opacity-40"
            :disabled="uploading"
            :aria-label="__('Attach image')"
            @mousedown.prevent
            @click="openFileSelector()"
          >
            <LucideImagePlus class="size-4.5" />
          </button>
        </template>
      </FileUploader>
      <textarea
        ref="quickInput"
        v-model="quickText"
        rows="1"
        :placeholder="quickPlaceholder"
        class="max-h-[120px] min-h-[38px] flex-1 resize-none rounded-[19px] border border-outline-gray-2 px-3.5 py-2 text-base text-ink-gray-9 placeholder-ink-gray-4 focus:outline-none focus:ring-1 focus:ring-outline-gray-3"
        :class="mode === 'note' ? 'bg-surface-amber-1' : 'bg-surface-gray-1'"
        @input="autogrow"
        @focus="focused = true"
        @blur="focused = false"
        @keydown.esc.stop="escapeBar"
      />
      <button
        v-if="expanded"
        class="flex h-[38px] w-9 shrink-0 items-center justify-center text-ink-gray-5"
        :aria-label="__('Full editor')"
        :title="__('Full editor (Shift+R)')"
        @mousedown.prevent
        @click="expandToEditor"
      >
        <LucideMaximize2 class="size-4.5" />
      </button>
      <button
        class="flex size-[38px] shrink-0 items-center justify-center rounded-full text-white disabled:opacity-40"
        :style="{ backgroundColor: mode === 'note' ? '#b45309' : '#1b2a4a' }"
        :disabled="(!quickText.trim() && !quickAttachments.length) || sending"
        :aria-label="mode === 'note' ? __('Add note') : __('Send reply')"
        @mousedown.prevent
        @click="sendQuick"
      >
        <LucideArrowUp class="size-4.5" />
      </button>
    </div>
    <TypingIndicator :ticketId="tid" />
  </div>
</template>

<script setup lang="ts">
import { AttachmentItem, TypingIndicator } from "@/components";
import {
  aiDraftPreview,
  buildAiReplyDraft,
  hasAiReplyDraft,
} from "@/composables/aiReplyDraft";
import { useTyping } from "@/composables/realtime";
import { useShortcut } from "@/composables/shortcuts";
import { getUserEmailInfo } from "@/composables/useUserEmailInfo";
import { showCommentBox, showEmailBox } from "@/pages/ticket/modalStates";
import { useAgentStore } from "@/stores/agent";
import { useTicketStatusStore } from "@/stores/ticketStatus";
import { __ } from "@/translation";
import { TicketSymbol } from "@/types";
import { removeAttachmentFromServer } from "@/utils";
import { useStorage } from "@vueuse/core";
import {
  Avatar,
  call,
  createResource,
  FeatherIcon,
  FileUploader,
  toast,
} from "frappe-ui";
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import LucideArrowUp from "~icons/lucide/arrow-up";
import LucideCircleCheck from "~icons/lucide/circle-check";
import LucideImagePlus from "~icons/lucide/image-plus";
import LucideMaximize2 from "~icons/lucide/maximize-2";
import LucideSparkles from "~icons/lucide/sparkles";

const emit = defineEmits(["update", "close", "expand"]);

const ticket = inject(TicketSymbol)!;
const doc = computed(() => ticket.value?.doc);
// Keyed by ticket name in the parent, so tid is stable for the component's
// whole life — safe for storage keys and resources.
const tid = String(doc.value?.name ?? "");

const ticketStatusStore = useTicketStatusStore();
const userResource = getUserEmailInfo();
const { onUserType, cleanup: cleanupTyping } = useTyping(tid);

// ── Bar state ────────────────────────────────────────────────────────────
// Expanded while focused or while anything sits in it, so a half-typed reply
// never collapses out of view on blur. Same key as the phone bar on purpose:
// the two never mount together (route-level split) and a draft started on
// one width survives a resize.
const focused = ref(false);
const quickAttachments = ref<any[]>([]);
const mode = ref<"reply" | "note">("reply");
const quickText = useStorage(`pyekQuickDraft:${tid}`, "");
const quickInput = ref<HTMLTextAreaElement | null>(null);
const sending = ref(false);
const expanded = computed(
  () =>
    focused.value || !!quickText.value.trim() || !!quickAttachments.value.length
);

async function removeQuickAttachment(a: any) {
  quickAttachments.value = quickAttachments.value.filter((x) => x !== a);
  await removeAttachmentFromServer(a.name);
}

const requesterLabel = computed(
  () => doc.value?.contact || doc.value?.raised_by || ""
);
const modeLabel = computed(() =>
  mode.value === "note"
    ? __("visible to the team only")
    : requesterLabel.value
    ? `${__("to")} ${requesterLabel.value}`
    : ""
);
const quickPlaceholder = computed(() =>
  mode.value === "note"
    ? __("Internal note — team only")
    : requesterLabel.value
    ? `${__("Reply to")} ${requesterLabel.value}…`
    : __("Write a reply…")
);

function setMode(m: "reply" | "note") {
  mode.value = m;
  nextTick(() => quickInput.value?.focus());
}

function autogrow() {
  const el = quickInput.value;
  if (!el) return;
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 120) + "px";
  updateMentionFragment();
}

function escapeBar() {
  quickInput.value?.blur();
}

// ── Keyboard shortcuts (pick #5) ─────────────────────────────────────────
// r/c focus the bar in reply/note mode; Shift+R opens the full editor.
// CommunicationArea skips its own r/c registration when the bar is present
// (quick-bar prop), so these are the only bindings. All three stand down
// while either full editor is open — those own the screen then. useShortcut
// already refuses to fire while an input has focus, so Esc-in-textarea and
// Shift+R-while-typing behave as typing, not commands.
function focusBar(m: "reply" | "note") {
  if (showEmailBox.value || showCommentBox.value) return;
  setMode(m);
}
useShortcut("r", () => focusBar("reply"));
useShortcut("c", () => focusBar("note"));
useShortcut({ key: "r", shift: true }, () => {
  if (showEmailBox.value || showCommentBox.value) return;
  expandToEditor();
});

// ── @mentions (forked verbatim from MobileReplyFlow) ─────────────────────
const agentStore = useAgentStore();
const mentionFragment = ref<string | null>(null);
let mentionTokenStart = -1;
const mentionedAgents = ref<{ label: string; email: string }[]>([]);

function updateMentionFragment() {
  const el = quickInput.value;
  if (!el) {
    mentionFragment.value = null;
    return;
  }
  const upToCaret = el.value.slice(0, el.selectionStart ?? el.value.length);
  const m = upToCaret.match(/(^|\s)@([\w.'-]{0,30})$/);
  if (!m) {
    mentionFragment.value = null;
    mentionTokenStart = -1;
    return;
  }
  mentionTokenStart = upToCaret.length - m[2].length - 1;
  mentionFragment.value = m[2].toLowerCase();
}

const mentionMatches = computed(() => {
  if (mentionFragment.value === null) return [];
  const f = mentionFragment.value;
  return (agentStore.agents.data || [])
    .filter((a: any) => a.user && a.user !== (window as any).agent)
    .filter(
      (a: any) =>
        !f ||
        a.agent_name?.toLowerCase().includes(f) ||
        a.user?.toLowerCase().includes(f)
    )
    .slice(0, 5);
});

function pickMention(a: any) {
  const el = quickInput.value;
  if (!el || mentionTokenStart < 0) return;
  const caret = el.selectionStart ?? el.value.length;
  const label = a.agent_name;
  quickText.value =
    quickText.value.slice(0, mentionTokenStart) +
    "@" +
    label +
    " " +
    quickText.value.slice(caret);
  mentionedAgents.value = [
    ...mentionedAgents.value.filter((m) => m.email !== a.user),
    { label, email: a.user },
  ];
  mentionFragment.value = null;
  mentionTokenStart = -1;
  nextTick(() => {
    autogrow();
    el.focus();
  });
}

// Only people whose "@Name" still exists in the final text get notified.
function activeMentions(text: string) {
  const seen = new Set<string>();
  return mentionedAgents.value.filter((m) => {
    if (seen.has(m.email) || !text.includes("@" + m.label)) return false;
    seen.add(m.email);
    return true;
  });
}

function mentionHtml(text: string): string {
  let html = textToHtml(text);
  for (const m of activeMentions(text)) {
    const token = escapeHtml("@" + m.label);
    html = html
      .split(token)
      .join(
        `<span class="mention" data-type="mention" data-id="${m.email}" data-label="${escapeHtml(m.label)}">${token}</span>`
      );
  }
  return html;
}

watch(quickText, (val, old) => {
  if (val !== old && val) onUserType();
  nextTick(autogrow);
});

onMounted(() => {
  // Same lazy fetch CommentTextEditor does — the store doesn't auto-load.
  const list: any = agentStore.agents;
  if (!list.loading && !list.data?.length && !list.list?.promise) {
    list.fetch();
  }
});
onBeforeUnmount(() => {
  if (armTimer) clearTimeout(armTimer);
  if (toastTimer) clearTimeout(toastTimer);
  cleanupTyping();
});

// ── AI draft chip ────────────────────────────────────────────────────────
const aiDraftAvailable = computed(() => hasAiReplyDraft(doc.value));
const showAiChip = computed(
  () =>
    mode.value === "reply" && !quickText.value.trim() && aiDraftAvailable.value
);
const aiPreview = computed(() =>
  aiDraftAvailable.value ? aiDraftPreview(buildAiReplyDraft(doc.value)) : ""
);
function useAiDraft() {
  quickText.value = buildAiReplyDraft(doc.value);
  nextTick(() => {
    autogrow();
    quickInput.value?.focus();
  });
}

// ── Full-editor escape (pick #3) ─────────────────────────────────────────
// Desktop's escape hatch is the EXISTING EmailEditor, not the phone's
// full-screen composer. The typed text rides along as HTML; the parent opens
// the editor and inserts it.
function expandToEditor() {
  const carry = quickText.value.trim();
  quickText.value = "";
  nextTick(autogrow);
  emit("expand", carry ? textToHtml(carry) : "");
}

// ── Sending (same proven endpoints as the phone bar) ─────────────────────
function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function textToHtml(t: string): string {
  return t
    .trim()
    .split(/\n{2,}/)
    .map((p) => `<p>${escapeHtml(p).replace(/\n/g, "<br>")}</p>`)
    .join("");
}

const signatureHtml = computed(() =>
  userResource.data?.email_signature
    ? `<br>${userResource.data.email_signature}`
    : ""
);

const out = {
  message: ref(""),
  to: ref(""),
  attachments: ref<string[]>([]),
};
let pendingReplyMentions: { label: string; email: string }[] = [];
let pendingReplyMessage = "";

const sendMail = createResource({
  url: "run_doc_method",
  makeParams: () => ({
    dt: "HD Ticket",
    dn: tid,
    method: "reply_via_agent",
    args: {
      attachments: out.attachments.value,
      to: out.to.value,
      cc: "",
      bcc: "",
      message: out.message.value,
    },
  }),
  onSuccess: () => {
    sending.value = false;
    // Reply mentions: no server-side mention pass exists for Communications,
    // so create the HD Notifications here — the doctype's own after_insert
    // does the push (and respects per-agent prefs). Fire-and-forget.
    for (const m of pendingReplyMentions) {
      call("frappe.client.insert", {
        doc: {
          doctype: "HD Notification",
          notification_type: "Mention",
          user_from: (window as any).agent,
          user_to: m.email,
          reference_ticket: tid,
          message: pendingReplyMessage,
        },
      }).catch(() => {});
    }
    pendingReplyMentions = [];
    mentionedAgents.value = [];
    quickText.value = "";
    quickAttachments.value = [];
    nextTick(autogrow);
    afterReplySent();
  },
  onError: () => {
    sending.value = false;
    toast.error(__("Could not send the reply."));
  },
  debounce: 300,
});

function sendQuick() {
  const text = quickText.value.trim();
  // A screenshot with no words is a legitimate reply.
  if ((!text && !quickAttachments.value.length) || sending.value) return;
  if (mode.value === "note") {
    sendNote(text);
    return;
  }
  pendingReplyMentions = activeMentions(text);
  pendingReplyMessage = text ? textToHtml(text) : "";
  out.message.value = (text ? textToHtml(text) : "") + signatureHtml.value;
  out.to.value = doc.value?.raised_by || "";
  out.attachments.value = quickAttachments.value.map((x) => x.name);
  if (!out.to.value) {
    toast.warning(__("This ticket has no requester email to reply to."));
    return;
  }
  sending.value = true;
  sendMail.submit();
}

function sendNote(text: string) {
  sending.value = true;
  createResource({
    url: "run_doc_method",
    makeParams: () => ({
      dt: "HD Ticket",
      dn: tid,
      method: "new_comment",
      // new_comment wants the file OBJECTS (it reads .file_url), unlike
      // reply_via_agent which wants names. Mentions ride as the desktop
      // tiptap markup — HDTicketComment.after_insert extracts them and
      // pushes/emails the mentioned agents server-side.
      args: {
        content: text ? mentionHtml(text) : "",
        attachments: quickAttachments.value,
      },
    }),
    onSuccess: () => {
      sending.value = false;
      quickText.value = "";
      quickAttachments.value = [];
      mentionedAgents.value = [];
      mode.value = "reply";
      nextTick(autogrow);
      emit("update");
    },
    onError: () => {
      sending.value = false;
      toast.error(__("Could not add the note."));
    },
  }).submit();
}

// ── After a reply goes out ───────────────────────────────────────────────
// Open → Waiting on Customer, same rule as every other reply path. NO
// self-assign here: acting-claims-it is phone-only by design (Mark,
// 2026-08-14 — "Desktop replies are untouched").
const WAITING_STATUS = "Waiting on Customer";

function afterReplySent() {
  emit("update");
  moveToWaiting();
  showToast();
}

function moveToWaiting() {
  if (doc.value?.status !== "Open") return;
  if (!ticketStatusStore.getStatus(WAITING_STATUS)?.enabled) return;
  ticket.value.setValue.submit(
    { status: WAITING_STATUS },
    { onSuccess: () => emit("update") }
  );
}

// ── Close (pick #4: arm, then the parent's resolution-aware close) ──────
const closeArmed = ref(false);
let armTimer: ReturnType<typeof setTimeout> | null = null;

const canClose = computed(() => {
  const status = doc.value?.status;
  if (!status) return false;
  return ticketStatusStore.getStatus(status)?.category !== "Resolved";
});

function tapClose() {
  if (!closeArmed.value) {
    closeArmed.value = true;
    if (armTimer) clearTimeout(armTimer);
    armTimer = setTimeout(() => (closeArmed.value = false), 3500);
    return;
  }
  if (armTimer) clearTimeout(armTimer);
  closeArmed.value = false;
  hideToast();
  emit("close");
}

// ── After-send toast ─────────────────────────────────────────────────────
const toastVisible = ref(false);
let toastTimer: ReturnType<typeof setTimeout> | null = null;
function showToast() {
  toastVisible.value = true;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (toastVisible.value = false), 6000);
}
function hideToast() {
  toastVisible.value = false;
  if (toastTimer) clearTimeout(toastTimer);
}
function closeFromToast() {
  hideToast();
  emit("close");
}
</script>
