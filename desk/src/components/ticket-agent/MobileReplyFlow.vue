<template>
  <!-- The phone's reply flow (Mark's picks, 2026-08-15): a chat-style quick bar
       as the default path, a full-screen native composer as the escalation, an
       AI-draft chip bridging the enricher into the bar, and an optional
       "Resolve ticket?" toast after a reply goes out. Replaces the desktop
       EmailEditor sheet on mobile entirely — and with it the module-level
       showEmailBox state whose open/closed value used to leak across tickets.
       Multi-root on purpose; every root carries its own v-show (v-show on a
       fragment component silently does nothing — the act bar learned that). -->

  <!-- ── Persistent composer bar (Mark, 2026-08-17: "the reply button needs
       to sit at the bottom of the screen always… like a normal texting app").
       Fixed to the real screen bottom — position:sticky only pins when the
       content overflows, which is how the old act bar floated mid-screen on
       short threads. Slim [resolve][input][send] row at rest; focusing the
       input expands it into the full quick bar (Note toggle, AI chip,
       full-composer escape). "Take it" is gone: sending claims the ticket,
       and assignment lives in the header. -->
  <div v-show="!composeOpen" class="fixed inset-x-0 bottom-0 z-[55]">
    <!-- SLA pill: floats only when the deadline is close enough to act on
         (within a day, or breached less than a day ago). -->
    <div v-show="slaPill" class="mb-1.5 flex justify-center">
      <span
        class="rounded-full px-2.5 py-0.5 text-xs font-medium shadow"
        :class="slaPill?.cls"
        >{{ slaPill?.text }}</span
      >
    </div>
    <!-- AI draft chip: appears with the expanded bar, fills the input on tap,
         and is ignorable. Only for drafts grounded in an enricher branch.
         mousedown.prevent everywhere below: these controls exist only while
         `expanded` is true, and a bare mousedown would blur the input,
         collapse the bar, and remove the control before its click lands. -->
    <button
      v-if="expanded && showAiChip"
      class="mx-3 mb-2 flex w-auto items-center gap-2 rounded-xl border border-outline-gray-2 bg-surface-base px-3 py-2 text-left shadow-lg"
      @mousedown.prevent
      @click="useAiDraft"
    >
      <LucideSparkles class="size-4 shrink-0 text-ink-gray-6" />
      <span class="flex-1 truncate text-sm text-ink-gray-7">{{
        aiPreview
      }}</span>
      <span class="shrink-0 text-sm font-semibold text-ink-gray-9">{{
        __("Use")
      }}</span>
    </button>

    <div class="border-t bg-surface-base px-2.5 pt-1.5" :style="quickBarStyle">
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
      </div>
      <div class="flex items-end gap-1.5 pb-1.5">
        <!-- Resolve: two taps on purpose — the first arms it ("Resolve?"),
             the second commits. A bare single-tap next to the keyboard zone
             invites accidents. Hidden while typing; send is the action then. -->
        <button
          v-if="!expanded && canResolve"
          class="flex h-[38px] shrink-0 items-center justify-center rounded-full border transition-colors"
          :class="
            resolveArmed
              ? 'border-transparent px-3 text-sm font-semibold text-white'
              : 'w-[38px] border-outline-gray-2 bg-surface-base text-ink-green-3'
          "
          :style="resolveArmed ? { backgroundColor: '#2fb383' } : {}"
          :aria-label="__('Resolve')"
          :disabled="resolving"
          @click="tapResolve"
        >
          <template v-if="resolveArmed">{{ __("Resolve?") }}</template>
          <LucideCircleCheck v-else class="size-4.5" />
        </button>
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
        />
        <button
          v-if="expanded"
          class="flex h-[38px] w-9 shrink-0 items-center justify-center text-ink-gray-5"
          :aria-label="__('Full composer')"
          @mousedown.prevent
          @click="expandFromQuick"
        >
          <LucideMaximize2 class="size-4.5" />
        </button>
        <button
          class="flex size-[38px] shrink-0 items-center justify-center rounded-full text-white disabled:opacity-40"
          :style="{ backgroundColor: mode === 'note' ? '#b45309' : '#1b2a4a' }"
          :disabled="!quickText.trim() || sending"
          :aria-label="mode === 'note' ? __('Add note') : __('Send reply')"
          @mousedown.prevent
          @click="sendQuick"
        >
          <LucideArrowUp class="size-4.5" />
        </button>
      </div>
    </div>
  </div>

  <!-- ── Full composer ─────────────────────────────────────────────────── -->
  <Transition name="pyek-compose">
    <div
      v-show="composeOpen"
      class="fixed inset-0 z-[70] flex flex-col bg-surface-base"
    >
      <div
        class="flex shrink-0 items-center gap-3 px-3 py-2.5 text-white"
        style="
          background: #1b2a4a;
          padding-top: max(env(safe-area-inset-top, 0px), 10px);
        "
      >
        <button
          class="flex size-8 items-center justify-center"
          :aria-label="__('Close')"
          @click="closeCompose"
        >
          <LucideX class="size-5" />
        </button>
        <span class="text-base font-semibold">{{ __("Reply") }}</span>
        <button
          class="ms-auto rounded-full bg-white px-4 py-1.5 text-sm font-semibold text-[#1b2a4a] disabled:opacity-50"
          :disabled="sending"
          @click="submitCompose"
        >
          {{ sending ? __("Sending…") : __("Send") }}
        </button>
      </div>

      <Editor
        ref="editorRef"
        v-model="newEmail"
        :placeholder="__('Write your reply…')"
        :editable="true"
        :extensions="extensions"
        :upload-function="(file: any) => uploadFunction(file, 'HD Ticket', tid)"
      >
        <template #default>
          <div class="flex min-h-0 flex-1 flex-col">
            <!-- Recipients: one collapsed line, tap to unfold — the phone
                 answer to the desktop's permanent From/To/CC/BCC stack. -->
            <div class="border-b">
              <button
                class="flex w-full items-center gap-1.5 px-4 py-2.5 text-sm"
                @click="recipientsOpen = !recipientsOpen"
              >
                <span class="text-ink-gray-4">{{ __("To") }}</span>
                <span class="truncate text-ink-gray-8">{{
                  toEmailsM[0] || "—"
                }}</span>
                <span v-if="extraRecipientCount" class="text-ink-gray-4">
                  · +{{ extraRecipientCount }}
                </span>
                <LucideChevronRight
                  class="ms-auto size-4 shrink-0 text-ink-gray-4 transition-transform"
                  :class="recipientsOpen ? 'rotate-90' : ''"
                />
              </button>
              <div v-if="recipientsOpen" class="flex flex-col gap-1 px-4 pb-2.5">
                <div class="flex items-center gap-2">
                  <span class="w-8 shrink-0 text-xs text-ink-gray-4">{{
                    __("To")
                  }}</span>
                  <EmailMultiSelect
                    v-model="toEmailsM"
                    class="flex-1"
                    scope="contact"
                    variant="ghost"
                    allow-custom-email
                    :validate="validateEmailWithZod"
                    :custom-email-label="__('Add to recipients')"
                  />
                </div>
                <div class="flex items-center gap-2">
                  <span class="w-8 shrink-0 text-xs text-ink-gray-4">{{
                    __("Cc")
                  }}</span>
                  <EmailMultiSelect
                    v-model="ccEmailsM"
                    class="flex-1"
                    scope="contact"
                    variant="ghost"
                    allow-custom-email
                    :validate="validateEmailWithZod"
                    :custom-email-label="__('Add to recipients')"
                  />
                </div>
                <div class="flex items-center gap-2">
                  <span class="w-8 shrink-0 text-xs text-ink-gray-4">{{
                    __("Bcc")
                  }}</span>
                  <EmailMultiSelect
                    v-model="bccEmailsM"
                    class="flex-1"
                    scope="contact"
                    variant="ghost"
                    allow-custom-email
                    :validate="validateEmailWithZod"
                    :custom-email-label="__('Add to recipients')"
                  />
                </div>
              </div>
            </div>
            <div class="border-b px-4 py-2.5 text-sm text-ink-gray-4">
              {{ __("Subject") }}
              <span class="text-ink-gray-8">Re: {{ subject }}</span>
            </div>

            <!-- Body + quoted content share the scroller so a long reply and a
                 long thread both stay reachable. -->
            <div class="min-h-0 flex-1 overflow-y-auto">
              <EditorContent
                :class="[
                  'prose-sm max-w-full px-4 py-3',
                  getFontFamily(newEmail),
                  '[&_p.reply-to-content]:hidden',
                ]"
              />
              <div v-if="quotedHtml" class="mx-4 mb-3">
                <button
                  class="mb-1 rounded bg-surface-gray-2 px-2 py-0.5 text-xs text-ink-gray-5"
                  @click="quoteExpanded = !quoteExpanded"
                >
                  ···
                </button>
                <div
                  v-if="quoteExpanded"
                  class="prose !max-w-full border-s-4 border-outline-gray-2 ps-3 text-sm"
                  v-html="quotedHtml"
                />
              </div>
            </div>

            <div
              v-if="attachments.length"
              class="flex flex-wrap gap-2 border-t px-4 py-2"
            >
              <AttachmentItem
                v-for="a in attachments"
                :key="a.file_url"
                :label="a.file_name"
                :url="!['MOV', 'MP4'].includes(a.file_type) ? a.file_url : null"
              >
                <template #suffix>
                  <FeatherIcon
                    class="h-3.5"
                    name="x"
                    @click.self.stop="removeAttachment(a)"
                  />
                </template>
              </AttachmentItem>
            </div>

            <!-- Big touch targets first, formatting second. -->
            <div class="shrink-0 border-t px-3 pt-2" :style="composeToolsStyle">
              <div class="mb-2 flex gap-2">
                <FileUploader
                  class="flex-1"
                  :upload-args="{
                    doctype: 'HD Ticket',
                    docname: tid,
                    private: true,
                  }"
                  @success="(f) => attachments.push(f)"
                >
                  <template #default="{ openFileSelector, uploading }">
                    {{ void (isUploading = uploading) }}
                    <button
                      class="flex w-full flex-col items-center gap-1 rounded-xl border border-outline-gray-2 bg-surface-gray-1 py-2 text-xs font-medium text-ink-gray-7"
                      :disabled="uploading"
                      @click="openFileSelector()"
                    >
                      <LucidePaperclip class="size-4.5" />
                      {{ __("Attach") }}
                    </button>
                  </template>
                </FileUploader>
                <button
                  class="flex flex-1 flex-col items-center gap-1 rounded-xl border border-outline-gray-2 bg-surface-gray-1 py-2 text-xs font-medium text-ink-gray-7"
                  @click="showSavedReplies = true"
                >
                  <SavedReplyIcon class="size-4.5" />
                  {{ __("Saved replies") }}
                </button>
                <button
                  v-if="aiDraftAvailable"
                  class="flex flex-1 flex-col items-center gap-1 rounded-xl border border-outline-gray-2 bg-surface-gray-1 py-2 text-xs font-medium text-ink-gray-7"
                  @click="insertAiDraft"
                >
                  <LucideSparkles class="size-4.5" />
                  {{ __("AI draft") }}
                </button>
              </div>
              <div class="overflow-x-auto pb-2">
                <EditorFixedMenu :items="mobileToolbar" />
              </div>
            </div>
          </div>
        </template>
      </Editor>
    </div>
  </Transition>

  <!-- ── After-send resolve prompt ─────────────────────────────────────── -->
  <div
    v-show="toastVisible"
    class="fixed left-1/2 z-[80] flex -translate-x-1/2 items-center gap-2.5 rounded-xl px-3.5 py-2 shadow-xl"
    style="background: #123d2e; bottom: calc(var(--pyek-nav-h, 0px) + 76px)"
  >
    <span class="whitespace-nowrap text-sm font-medium text-white">
      {{ __("Sent · Resolve ticket?") }}
    </span>
    <button
      class="rounded-lg px-3 py-1 text-sm font-semibold text-[#04120c]"
      style="background: #2fb383"
      :disabled="resolving"
      @click="resolveFromToast"
    >
      {{ __("Resolve") }}
    </button>
  </div>

  <SavedRepliesSelectorModal
    v-model="showSavedReplies"
    doctype="HD Ticket"
    :ticketId="tid"
    @apply="applySavedReply"
  />
</template>

<script setup lang="ts">
import { AttachmentItem, SavedRepliesSelectorModal } from "@/components";
import { buildEditorExtensions } from "@/components/editor/config";
import EmailMultiSelect from "@/components/EmailMultiSelect.vue";
import SavedReplyIcon from "@/components/icons/SavedReplyIcon.vue";
import {
  aiDraftPreview,
  buildAiReplyDraft,
  hasAiReplyDraft,
} from "@/composables/aiReplyDraft";
import { useTyping } from "@/composables/realtime";
import { parseAssign, selfAssignTicket } from "@/composables/selfAssign";
import { getUserEmailInfo } from "@/composables/useUserEmailInfo";
import { useTicketStatusStore } from "@/stores/ticketStatus";
import { __ } from "@/translation";
import { TicketSymbol } from "@/types";
import {
  getFontFamily,
  isContentEmpty,
  removeAttachmentFromServer,
  uploadFunction,
  validateEmailWithZod,
} from "@/utils";
import { useStorage } from "@vueuse/core";
import { createResource, FeatherIcon, FileUploader, toast } from "frappe-ui";
import {
  Bold,
  BulletList,
  Editor,
  EditorContent,
  EditorFixedMenu,
  InsertImage,
  InsertLink,
  Italic,
  OrderedList,
} from "frappe-ui/editor";
import {
  computed,
  inject,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import LucideArrowUp from "~icons/lucide/arrow-up";
import LucideChevronRight from "~icons/lucide/chevron-right";
import LucideCircleCheck from "~icons/lucide/circle-check";
import LucideMaximize2 from "~icons/lucide/maximize-2";
import LucidePaperclip from "~icons/lucide/paperclip";
import LucideSparkles from "~icons/lucide/sparkles";
import LucideX from "~icons/lucide/x";

const emit = defineEmits(["update"]);

const ticket = inject(TicketSymbol)!;
const doc = computed(() => ticket.value?.doc);
// The parent keys this component by ticket name, so the id is stable for the
// component's whole life — safe to snapshot for storage keys and resources.
const tid = String(doc.value?.name ?? "");
const subject = computed(() => doc.value?.subject ?? "");

const ticketStatusStore = useTicketStatusStore();
const userResource = getUserEmailInfo();
const { onUserType, cleanup: cleanupTyping } = useTyping(tid);

// ── Bar state (component-local: nothing here survives this ticket) ──
// The bar is ALWAYS rendered; `expanded` is presentation, not existence.
// Expanded while focused or while a draft sits in the box, so a half-typed
// reply never collapses out of view on blur.
const composeOpen = ref(false);
const focused = ref(false);
const expanded = computed(() => focused.value || !!quickText.value.trim());

// ── Quick bar ────────────────────────────────────────────────────────────
const mode = ref<"reply" | "note">("reply");
const quickText = useStorage(`pyekQuickDraft:${tid}`, "");
const quickInput = ref<HTMLTextAreaElement | null>(null);
const sending = ref(false);

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
}
watch(quickText, (val, old) => {
  if (val !== old && val) onUserType();
  nextTick(autogrow);
});

// Entry points that used to open the overlay (the contact header's email
// icon) now just focus the always-present bar.
function openQuick() {
  mode.value = "reply";
  nextTick(() => {
    autogrow();
    quickInput.value?.focus();
  });
}

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

// ── Keyboard clearance ───────────────────────────────────────────────────
// iOS keyboards OVERLAY the viewport (interactive-widget was removed in PR
// 132), so a bottom-fixed bar must lift itself by the covered height.
// visualViewport is the only honest signal; innerHeight alone never changes.
const kbdInset = ref(0);
function updateKbdInset() {
  const vv = window.visualViewport;
  if (!vv) return;
  kbdInset.value = Math.max(
    0,
    Math.round(window.innerHeight - vv.height - vv.offsetTop)
  );
}
onMounted(() => {
  window.visualViewport?.addEventListener("resize", updateKbdInset);
  window.visualViewport?.addEventListener("scroll", updateKbdInset);
});
onBeforeUnmount(() => {
  window.visualViewport?.removeEventListener("resize", updateKbdInset);
  window.visualViewport?.removeEventListener("scroll", updateKbdInset);
  if (slaTimer) clearInterval(slaTimer);
  if (armTimer) clearTimeout(armTimer);
  if (toastTimer) clearTimeout(toastTimer);
  cleanupTyping();
});
const quickBarStyle = computed(() => ({
  paddingBottom:
    kbdInset.value > 0
      ? `${kbdInset.value}px`
      : "max(var(--pyek-nav-h, 0px), env(safe-area-inset-bottom, 0px))",
}));
const composeToolsStyle = computed(() => ({
  paddingBottom:
    kbdInset.value > 0
      ? `${kbdInset.value}px`
      : "max(env(safe-area-inset-bottom, 0px), 8px)",
}));

// ── Full composer ────────────────────────────────────────────────────────
const extensions = buildEditorExtensions();
const mobileToolbar = [
  Bold,
  Italic,
  BulletList,
  OrderedList,
  InsertLink,
  InsertImage,
];
const editorRef = ref<any>(null);
const composeDraft = useStorage<string | null>(`pyekComposeDraft:${tid}`, null);
const newEmail = ref<string | null>(composeDraft.value);
const recipientsOpen = ref(false);
const toEmailsM = ref<string[]>(doc.value?.raised_by ? [doc.value.raised_by] : []);
const ccEmailsM = ref<string[]>([]);
const bccEmailsM = ref<string[]>([]);
const quotedHtml = ref<string | null>(null);
const quoteExpanded = ref(false);
const attachments = ref<any[]>([]);
const isUploading = ref(false);
const showSavedReplies = ref(false);

const extraRecipientCount = computed(
  () =>
    Math.max(0, toEmailsM.value.length - 1) +
    ccEmailsM.value.length +
    bccEmailsM.value.length
);

const signatureHtml = computed(() =>
  userResource.data?.email_signature
    ? `<br>${userResource.data.email_signature}`
    : ""
);

watch(newEmail, (val, old) => {
  if (val !== old && val) onUserType();
  composeDraft.value = val;
});

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

interface ComposePayload {
  carryText?: string;
  content?: string;
  to?: string[] | string;
  cc?: string[] | string;
  bcc?: string[] | string;
}
function asList(v: string[] | string | undefined): string[] {
  if (!v) return [];
  return (typeof v === "string" ? v.split(",") : v)
    .map((s) => s.trim())
    .filter(Boolean);
}

function openCompose(payload: ComposePayload = {}) {
  if (payload.carryText?.trim()) {
    newEmail.value = textToHtml(payload.carryText) + signatureHtml.value;
  } else if (isContentEmpty(newEmail.value)) {
    newEmail.value = signatureHtml.value || "<p></p>";
  }
  if (payload.content) {
    // Reply-to-a-specific-email (the thread's reply arrows): quote it and
    // honor its recipient set, exactly like the desktop path did.
    quotedHtml.value = payload.content;
    quoteExpanded.value = false;
    if (payload.to) toEmailsM.value = asList(payload.to);
    ccEmailsM.value = asList(payload.cc);
    bccEmailsM.value = asList(payload.bcc);
  }
  quickInput.value?.blur();
  composeOpen.value = true;
  nextTick(() => editorRef.value?.editor?.commands?.focus("start"));
}
function closeCompose() {
  // Keeps the draft (persisted per ticket) — closing is not discarding.
  composeOpen.value = false;
}
function expandFromQuick() {
  const carry = quickText.value;
  quickText.value = "";
  openCompose({ carryText: carry });
}

function applySavedReply(template: string) {
  editorRef.value?.editor?.chain().focus("start").insertContent(template).run();
}
function insertAiDraft() {
  editorRef.value?.editor
    ?.chain()
    .focus("start")
    .insertContent(textToHtml(buildAiReplyDraft(doc.value)))
    .run();
}
async function removeAttachment(a: any) {
  attachments.value = attachments.value.filter((x) => x !== a);
  await removeAttachmentFromServer(a.name);
}

// ── Sending ──────────────────────────────────────────────────────────────
const out = {
  message: ref(""),
  to: ref(""),
  cc: ref(""),
  bcc: ref(""),
  attachments: ref<string[]>([]),
  origin: ref<"quick" | "compose">("quick"),
};

const sendMail = createResource({
  url: "run_doc_method",
  makeParams: () => ({
    dt: "HD Ticket",
    dn: tid,
    method: "reply_via_agent",
    args: {
      attachments: out.attachments.value,
      to: out.to.value,
      cc: out.cc.value,
      bcc: out.bcc.value,
      message: out.message.value,
    },
  }),
  onSuccess: () => {
    sending.value = false;
    if (out.origin.value === "quick") {
      quickText.value = "";
      nextTick(autogrow);
    } else {
      newEmail.value = null;
      composeDraft.value = null;
      quotedHtml.value = null;
      attachments.value = [];
      composeOpen.value = false;
    }
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
  if (!text || sending.value) return;
  if (mode.value === "note") {
    sendNote(text);
    return;
  }
  out.origin.value = "quick";
  out.message.value = textToHtml(text) + signatureHtml.value;
  out.to.value = doc.value?.raised_by || "";
  out.cc.value = "";
  out.bcc.value = "";
  out.attachments.value = [];
  if (!out.to.value) {
    toast.warning(__("This ticket has no requester email to reply to."));
    return;
  }
  sending.value = true;
  sendMail.submit();
}

function submitCompose() {
  if (sending.value || isUploading.value) return;
  if (isContentEmpty(newEmail.value) && !quotedHtml.value) {
    toast.warning(__("Write something first."));
    return;
  }
  if (
    !toEmailsM.value.length &&
    !ccEmailsM.value.length &&
    !bccEmailsM.value.length
  ) {
    toast.warning(__("Add at least one recipient (To, Cc, or Bcc)."));
    return;
  }
  out.origin.value = "compose";
  out.message.value =
    (newEmail.value || "") +
    (quotedHtml.value
      ? `<p class="reply-to-content"></p><blockquote>${quotedHtml.value}</blockquote>`
      : "");
  out.to.value = toEmailsM.value.join(",");
  out.cc.value = ccEmailsM.value.join(",");
  out.bcc.value = bccEmailsM.value.join(",");
  out.attachments.value = attachments.value.map((x) => x.name);
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
      args: { content: textToHtml(text), attachments: [] },
    }),
    onSuccess: () => {
      sending.value = false;
      quickText.value = "";
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
const WAITING_STATUS = "Waiting on Customer";

function afterReplySent() {
  emit("update");
  const d = doc.value;
  if (!d) return;
  // Acting = taking it (Mark, 2026-08-14): a reply from the phone claims an
  // unassigned ticket. Fire-and-forget — the reply is already out.
  if (!parseAssign(d._assign).length) {
    selfAssignTicket(String(d.name))
      .then(() => emit("update"))
      .catch(() => {});
  }
  moveToWaiting();
  showToast();
}

function moveToWaiting() {
  const current = doc.value?.status;
  if (current !== "Open") return;
  if (!ticketStatusStore.getStatus(WAITING_STATUS)?.enabled) return;
  ticket.value.setValue.submit(
    { status: WAITING_STATUS },
    { onSuccess: () => emit("update") }
  );
}

// ── Resolve (bar icon + toast share this) ────────────────────────────────
const resolving = ref(false);
const resolveArmed = ref(false);
let armTimer: ReturnType<typeof setTimeout> | null = null;

const canResolve = computed(() => {
  const status = doc.value?.status;
  if (!status) return false;
  return ticketStatusStore.getStatus(status)?.category !== "Resolved";
});

function tapResolve() {
  if (!resolveArmed.value) {
    resolveArmed.value = true;
    if (armTimer) clearTimeout(armTimer);
    armTimer = setTimeout(() => (resolveArmed.value = false), 3500);
    return;
  }
  if (armTimer) clearTimeout(armTimer);
  resolveArmed.value = false;
  resolveTicket();
}

async function resolveTicket() {
  if (resolving.value) return;
  resolving.value = true;
  try {
    // Acting = taking it: resolving an unassigned ticket claims it first.
    if (!parseAssign(doc.value?._assign).length) {
      await selfAssignTicket(tid);
    }
    await ticket.value.setValue.submit({ status: "Resolved" });
    toastVisible.value = false;
    if (toastTimer) clearTimeout(toastTimer);
    toast.success(__("Ticket resolved."));
    emit("update");
  } catch {
    toast.error(__("Could not resolve the ticket."));
  } finally {
    resolving.value = false;
  }
}

// ── SLA pill ─────────────────────────────────────────────────────────────
// Ticks every 30s so the countdown moves while the screen stays open. Only
// shows when the deadline is actionable-close: due within a day, or breached
// less than a day ago (an older breach is history, not a call to action).
const now = ref(Date.now());
let slaTimer: ReturnType<typeof setInterval> | null = null;
onMounted(() => {
  slaTimer = setInterval(() => (now.value = Date.now()), 30_000);
});

function parseFrappeDate(value: string): number {
  return new Date(value.replace(" ", "T")).getTime();
}
function fmtSpan(ms: number): string {
  const mins = Math.max(1, Math.round(ms / 60_000));
  if (mins < 60) return `${mins}m`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

const slaPill = computed(() => {
  const d = doc.value;
  if (!d || !canResolve.value) return null;
  const target =
    !d.first_responded_on && d.response_by
      ? { by: d.response_by, verb: __("Reply") }
      : d.resolution_by
      ? { by: d.resolution_by, verb: __("Resolve") }
      : null;
  if (!target) return null;
  const diff = parseFrappeDate(target.by) - now.value;
  if (diff >= 0 && diff < 24 * 3600_000) {
    return {
      text: `${target.verb} ${__("due in")} ${fmtSpan(diff)}`,
      cls:
        diff < 2 * 3600_000
          ? "bg-surface-amber-2 text-ink-amber-6"
          : "bg-surface-gray-2 text-ink-gray-7",
    };
  }
  if (diff < 0 && -diff <= 24 * 3600_000) {
    return {
      text: `${target.verb} ${__("overdue")} ${fmtSpan(-diff)}`,
      cls: "bg-surface-red-1 text-ink-red-6",
    };
  }
  return null;
});

// ── Resolve toast ────────────────────────────────────────────────────────
const toastVisible = ref(false);
let toastTimer: ReturnType<typeof setTimeout> | null = null;
function showToast() {
  toastVisible.value = true;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (toastVisible.value = false), 6000);
}
const resolveFromToast = resolveTicket;

defineExpose({ openQuick, openCompose });
</script>

<style scoped>
.pyek-compose-enter-active,
.pyek-compose-leave-active {
  transition: transform 0.25s cubic-bezier(0.2, 0.8, 0.3, 1), opacity 0.2s ease;
}
.pyek-compose-enter-from,
.pyek-compose-leave-to {
  transform: translateY(24px);
  opacity: 0;
}
@media (prefers-reduced-motion: reduce) {
  .pyek-compose-enter-active,
  .pyek-compose-leave-active {
    transition: none;
  }
}
</style>
