<template>
  <!-- The phone's reply flow (Mark's picks, 2026-08-15): a chat-style quick bar
       as the default path, a full-screen native composer as the escalation, an
       AI-draft chip bridging the enricher into the bar, and an optional
       "Close ticket?" toast after a reply goes out. Replaces the desktop
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
      <!-- @mention picker (Mark, 2026-08-17: "when typing @ it shows people I
           can at… and I want them to get a push"). Appears while the token
           under the caret is @something with agent matches. mousedown.prevent
           — same blur-collapse trap as every transient control here. -->
      <div
        v-if="mentionMatches.length"
        class="mb-1.5 overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-base shadow-lg"
      >
        <button
          v-for="a in mentionMatches"
          :key="a.user"
          class="flex w-full items-center gap-2 px-3 py-2 text-left active:bg-surface-gray-2"
          @mousedown.prevent
          @click="pickMention(a)"
        >
          <Avatar size="sm" :label="a.agent_name" :image="a.user_image" />
          <span class="text-sm text-ink-gray-8">{{ a.agent_name }}</span>
          <span class="ms-auto truncate text-xs text-ink-gray-4">{{
            a.user
          }}</span>
        </button>
      </div>
      <!-- Photo/screenshot chips: uploaded already, sent with the message. -->
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
        <!-- Reply mode: the "to …" line is a button that opens the recipient
             editor — reply-all is the default, pruning/adding is one tap. -->
        <button
          v-if="mode === 'reply'"
          class="flex min-w-0 items-center gap-1 text-xs text-ink-gray-5"
          @mousedown.prevent
          @click="recipientsBarOpen = !recipientsBarOpen"
        >
          <span class="truncate">{{ modeLabel }}</span>
          <LucidePencil class="size-3 shrink-0" />
        </button>
        <span v-else class="truncate text-xs text-ink-gray-5">{{
          modeLabel
        }}</span>
      </div>
      <!-- Recipient editor: kept open by `recipientsBarOpen` (it holds the
           bar expanded through the blur its own inputs cause). -->
      <div
        v-if="expanded && recipientsBarOpen && mode === 'reply'"
        class="mb-1.5 flex flex-col gap-1 rounded-xl border border-outline-gray-2 bg-surface-base px-3 py-2 shadow-md"
      >
        <div class="flex items-center gap-2">
          <span class="w-6 shrink-0 text-xs text-ink-gray-4">{{
            __("To")
          }}</span>
          <EmailMultiSelect
            v-model="quickTo"
            class="flex-1"
            scope="contact"
            variant="ghost"
            allow-custom-email
            :validate="validateEmailWithZod"
            :custom-email-label="__('Add to recipients')"
          />
        </div>
        <div class="flex items-center gap-2">
          <span class="w-6 shrink-0 text-xs text-ink-gray-4">{{
            __("Cc")
          }}</span>
          <EmailMultiSelect
            v-model="quickCc"
            class="flex-1"
            scope="contact"
            variant="ghost"
            allow-custom-email
            :validate="validateEmailWithZod"
            :custom-email-label="__('Add to recipients')"
          />
        </div>
      </div>
      <div class="flex items-end gap-1.5 pb-1.5">
        <!-- Close: two taps on purpose — the first arms it ("Close?"), the
             second commits. Sets status CLOSED (Mark, 2026-08-17: "that is
             the typical way we mark things when we are done"), skipping the
             desktop resolution-note prompt just like the old Resolve did.
             Hidden while typing; send is the action then. -->
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
          :disabled="closing"
          @click="tapClose"
        >
          <template v-if="closeArmed">{{ __("Close?") }}</template>
          <LucideCircleCheck v-else class="size-4.5" />
        </button>
        <!-- Photo from the phone (Mark, 2026-08-17: screenshots). Unrestricted
             file input on iOS shows the Photo Library / Take Photo / Choose
             File sheet, which is exactly the right picker. Expanded-only —
             the collapsed row keeps its three controls. -->
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
              :aria-label="__('Add photo')"
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
          :disabled="(!quickText.trim() && !quickAttachments.length) || sending"
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
      {{ __("Sent · Close ticket?") }}
    </span>
    <button
      class="rounded-lg px-3 py-1 text-sm font-semibold text-[#04120c]"
      style="background: #2fb383"
      :disabled="closing"
      @click="closeFromToast"
    >
      {{ __("Close") }}
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
import {
  recipientSummary,
  replyAllFromCommunications,
} from "@/composables/replyRecipients";
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
import { useAgentStore } from "@/stores/agent";
import { useStorage } from "@vueuse/core";
import {
  Avatar,
  call,
  createResource,
  FeatherIcon,
  FileUploader,
  toast,
} from "frappe-ui";
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
import LucideImagePlus from "~icons/lucide/image-plus";
import LucideMaximize2 from "~icons/lucide/maximize-2";
import LucidePaperclip from "~icons/lucide/paperclip";
import LucidePencil from "~icons/lucide/pencil";
import LucideSparkles from "~icons/lucide/sparkles";
import LucideX from "~icons/lucide/x";

const emit = defineEmits(["update"]);

const props = defineProps({
  // Raw Communication rows from the ticket's activities — the bar derives
  // its reply-all default from the newest one (Mark, 2026-08-20: "when I
  // reply it actually reply all instead").
  communications: {
    type: Array,
    default: () => [],
  },
});

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
const quickAttachments = ref<any[]>([]);
const expanded = computed(
  () =>
    focused.value ||
    recipientsBarOpen.value ||
    !!quickText.value.trim() ||
    !!quickAttachments.value.length
);

async function removeQuickAttachment(a: any) {
  quickAttachments.value = quickAttachments.value.filter((x) => x !== a);
  await removeAttachmentFromServer(a.name);
}

// ── Quick bar ────────────────────────────────────────────────────────────
const mode = ref<"reply" | "note">("reply");
const quickText = useStorage(`pyekQuickDraft:${tid}`, "");
const quickInput = ref<HTMLTextAreaElement | null>(null);
const sending = ref(false);

// ── Recipients (reply-all by default, editable in place) ────────────────
// Defaults track the thread's newest email until the agent edits the set;
// after that the edits are theirs for this screen's lifetime — a growing
// thread must not silently re-add someone who was deliberately removed.
const recipientsBarOpen = ref(false);
const recipientsEdited = ref(false);
const quickTo = ref<string[]>([]);
const quickCc = ref<string[]>([]);
let recipientsSyncing = false;

const supportEmails = computed(() =>
  (userResource.data?.outgoing_emails ?? [])
    .map((e: any) => (e.email_id || "").toLowerCase())
    .filter(Boolean)
);
const replyAllDefault = computed(() =>
  replyAllFromCommunications(
    props.communications as any[],
    String((window as any).agent || ""),
    supportEmails.value,
    doc.value?.raised_by || ""
  )
);
watch(
  replyAllDefault,
  (v) => {
    if (recipientsEdited.value) return;
    recipientsSyncing = true;
    quickTo.value = [...v.to];
    quickCc.value = [...v.cc];
    nextTick(() => (recipientsSyncing = false));
  },
  { immediate: true }
);
watch(
  [quickTo, quickCc],
  () => {
    if (!recipientsSyncing) recipientsEdited.value = true;
  },
  { deep: true }
);

const requesterLabel = computed(
  () => doc.value?.contact || doc.value?.raised_by || ""
);
const recipientsLabel = computed(
  () =>
    recipientSummary({ to: quickTo.value, cc: quickCc.value }) ||
    requesterLabel.value
);
const modeLabel = computed(() =>
  mode.value === "note"
    ? __("visible to the team only")
    : recipientsLabel.value
    ? `${__("to")} ${recipientsLabel.value}`
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

// ── @mentions ────────────────────────────────────────────────────────────
// The bar is a plain textarea, so the picker is hand-rolled: while the token
// under the caret is "@something", agents matching it are offered; picking
// one inserts "@Agent Name" as plain text and remembers who it refers to.
// Notes convert those to the desktop tiptap mention markup on send (the
// server's extract_mentions handles push + email from there); replies keep
// plain text in the customer-facing email and create the Mention
// notifications directly after the send lands.
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

// Only people whose "@Name" still exists in the final text get notified —
// a picked-then-deleted mention must not ping.
function activeMentions(text: string) {
  const seen = new Set<string>();
  return mentionedAgents.value.filter((m) => {
    if (seen.has(m.email) || !text.includes("@" + m.label)) return false;
    seen.add(m.email);
    return true;
  });
}

function mentionHtml(text: string): string {
  // Escape first, then swap each @Label for the exact span the desktop
  // tiptap mention emits — extract_mentions() and the desktop chip both key
  // on span[data-type="mention"] with data-id/data-label.
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
  // Same lazy fetch CommentTextEditor does — the store doesn't auto-load.
  const list: any = agentStore.agents;
  if (!list.loading && !list.data?.length && !list.list?.promise) {
    list.fetch();
  }
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
    // Reply-to-a-specific-email (the thread's reply arrows): quote it.
    quotedHtml.value = payload.content;
    quoteExpanded.value = false;
  }
  if (payload.to) {
    // An explicit recipient set (reply arrows, or the quick bar's edited
    // reply-all set) always wins.
    toEmailsM.value = asList(payload.to);
    ccEmailsM.value = asList(payload.cc);
    bccEmailsM.value = asList(payload.bcc);
  } else if (
    toEmailsM.value.join(",") === (doc.value?.raised_by || "") &&
    !ccEmailsM.value.length &&
    !bccEmailsM.value.length
  ) {
    // Composer still on its requester-only default: seed the current
    // reply-all set instead.
    toEmailsM.value = [...quickTo.value];
    ccEmailsM.value = [...quickCc.value];
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
      // Reply mentions: no server-side mention pass exists for
      // Communications, so create the HD Notifications here — the doctype's
      // own after_insert does the push (and respects per-agent prefs).
      // Fire-and-forget: the reply is already out.
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

let pendingReplyMentions: { label: string; email: string }[] = [];
let pendingReplyMessage = "";

function sendQuick() {
  const text = quickText.value.trim();
  // A screenshot with no words is a legitimate reply.
  if ((!text && !quickAttachments.value.length) || sending.value) return;
  if (mode.value === "note") {
    sendNote(text);
    return;
  }
  out.origin.value = "quick";
  pendingReplyMentions = activeMentions(text);
  pendingReplyMessage = text ? textToHtml(text) : "";
  out.message.value = (text ? textToHtml(text) : "") + signatureHtml.value;
  out.to.value = quickTo.value.join(",") || doc.value?.raised_by || "";
  out.cc.value = quickCc.value.join(",");
  out.bcc.value = "";
  out.attachments.value = quickAttachments.value.map((x) => x.name);
  if (!out.to.value) {
    toast.warning(__("This ticket has no requester email to reply to."));
    return;
  }
  recipientsBarOpen.value = false;
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

// ── Close (bar icon + toast share this) ──────────────────────────────────
// Sets status CLOSED, not Resolved — closing is how this team marks done
// (Mark, 2026-08-17). The desktop resolution-note prompt is deliberately
// skipped, same as the old one-tap Resolve was.
const closing = ref(false);
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
  closeTicket();
}

async function closeTicket() {
  if (closing.value) return;
  closing.value = true;
  try {
    // Acting = taking it: closing an unassigned ticket claims it first.
    if (!parseAssign(doc.value?._assign).length) {
      await selfAssignTicket(tid);
    }
    await ticket.value.setValue.submit({ status: "Closed" });
    toastVisible.value = false;
    if (toastTimer) clearTimeout(toastTimer);
    toast.success(__("Ticket closed."));
    emit("update");
  } catch {
    toast.error(__("Could not close the ticket."));
  } finally {
    closing.value = false;
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
  if (!d || !canClose.value) return null;
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
const closeFromToast = closeTicket;

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
