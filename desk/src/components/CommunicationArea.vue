<template>
  <div class="comm-area">
    <div
      class="flex justify-between gap-3 border-t px-6 md:px-5 py-4 md:py-2.5"
    >
      <div class="flex gap-1.5 items-center">
        <Button
          ref="sendEmailRef"
          variant="ghost"
          label="Reply"
          :class="[
            showEmailBox ? '!bg-surface-gray-4 hover:!bg-surface-gray-3' : '',
          ]"
          @click="toggleEmailBox()"
        >
          <template #prefix>
            <EmailIcon class="h-4" />
          </template>
        </Button>
        <Button
          variant="ghost"
          label="Comment"
          :class="[
            showCommentBox ? '!bg-surface-gray-4 hover:!bg-surface-gray-3' : '',
          ]"
          @click="toggleCommentBox()"
        >
          <template #prefix>
            <CommentIcon class="h-4" />
          </template>
        </Button>
        <TypingIndicator :ticketId="ticketId" />
      </div>
    </div>
    <Transition name="slide">
      <div
        v-show="showEmailBox"
        ref="emailBoxRef"
        @keydown.ctrl.enter.capture.stop="submitEmail"
        @keydown.meta.enter.capture.stop="submitEmail"
        @keydown.esc.capture.stop="showEmailBox = false"
      >
        <div class="overflow-hidden">
          <EmailEditor
            ref="emailEditorRef"
            :label="
              isMobileView
                ? 'Reply'
                : isMac
                ? 'Reply (⌘ + ⏎)'
                : 'Reply (Ctrl + ⏎)'
            "
            allow-reply-and-close
            placeholder="Hi John, we are looking into this issue."
            :ticketId="ticketId"
            :to-emails="toEmails"
            :cc-emails="ccEmails"
            :bcc-emails="bccEmails"
            @submit="onEmailSent"
            @discard="
              () => {
                showEmailBox = false;
              }
            "
          />
        </div>
      </div>
    </Transition>
    <Transition name="slide">
      <div
        v-show="showCommentBox"
        ref="commentBoxRef"
        @keydown.ctrl.enter.capture.stop="submitComment"
        @keydown.meta.enter.capture.stop="submitComment"
        @keydown.esc.capture.stop="showCommentBox = false"
      >
        <div class="overflow-hidden">
          <CommentTextEditor
            ref="commentTextEditorRef"
            :label="
              isMobileView
                ? 'Comment'
                : isMac
                ? 'Comment (⌘ + ⏎)'
                : 'Comment (Ctrl + ⏎)'
            "
            :ticketId="ticketId"
            :editable="showCommentBox"
            :doctype="doctype"
            placeholder="@John could you please look into this?"
            @submit="
              () => {
                showCommentBox = false;
                emit('update');
              }
            "
            @discard="
              () => {
                showCommentBox = false;
              }
            "
          />
        </div>
      </div>
    </Transition>
    <TicketResolutionModal
      v-model="showResolutionDialog"
      @closed="emit('update')"
    />
  </div>
</template>

<script setup lang="ts">
import { CommentTextEditor, EmailEditor, TypingIndicator } from "@/components";
import { CommentIcon, EmailIcon } from "@/components/icons/";
import TicketResolutionModal from "@/components/ticket-agent/TicketResolutionModal.vue";
import { useDevice } from "@/composables";
import { useScreenSize } from "@/composables/screen";
import { useShortcut } from "@/composables/shortcuts";
import { showCommentBox, showEmailBox } from "@/pages/ticket/modalStates";
import { useTicketStatusStore } from "@/stores/ticketStatus";
import { TicketSymbol } from "@/types";
import { onClickOutside } from "@vueuse/core";
import { inject, ref, watch } from "vue";

const emit = defineEmits(["update"]);
const content = defineModel("content");
const { isMac } = useDevice();
const { isMobileView } = useScreenSize();
let doc = defineModel();
// let doc = inject(TicketSymbol)?.value.doc
const emailEditorRef = ref(null);
const commentTextEditorRef = ref(null);
const emailBoxRef = ref(null);
const commentBoxRef = ref(null);

function toggleEmailBox() {
  if (showCommentBox.value) {
    showCommentBox.value = false;
  }
  showEmailBox.value = !showEmailBox.value;
}

function toggleCommentBox() {
  if (showEmailBox.value) {
    showEmailBox.value = false;
  }
  showCommentBox.value = !showCommentBox.value;
}

const ticket = inject(TicketSymbol, null);
const ticketStatusStore = useTicketStatusStore();
const showResolutionDialog = ref(false);

const WAITING_STATUS = "Waiting on Customer";

// Replying is the moment the ball changes court, and nothing was recording
// that: every human ticket sat in Open or Closed with nothing in between, so
// the queue couldn't tell "waiting on them" from "nobody has touched this".
function onEmailSent(opts: { close?: boolean } = {}) {
  showEmailBox.value = false;
  emit("update");

  if (!ticket?.value?.doc) return;
  if (opts.close) {
    closeAfterReply();
  } else {
    moveToWaiting();
  }
}

function closeAfterReply() {
  // Same rule the status dropdown uses: ask once, and don't nag if a
  // resolution is already recorded. The reply has already gone out either
  // way, so skipping the dialog still closes the ticket.
  if (!ticket.value.doc.pyek_resolution) {
    showResolutionDialog.value = true;
    return;
  }
  setStatus("Closed");
}

function moveToWaiting() {
  const current = ticket.value.doc.status;
  if (current === WAITING_STATUS) return;

  // Only from Open. Escalated and On Hold are states somebody chose
  // deliberately, and a reply on a Resolved/Closed ticket shouldn't silently
  // reopen it.
  if (current !== "Open") return;

  // Don't write a status that has been disabled out from under us.
  if (!ticketStatusStore.getStatus(WAITING_STATUS)?.enabled) return;

  setStatus(WAITING_STATUS);
}

function setStatus(status: string) {
  ticket.value.setValue.submit(
    { status },
    {
      onSuccess() {
        emit("update");
      },
    }
  );
}

function submitEmail() {
  if (emailEditorRef.value.submitMail()) {
    emit("update");
  }
}

function submitComment() {
  if (commentTextEditorRef.value.submitComment()) {
    emit("update");
  }
}

function splitIfString(str: string | string[]) {
  if (typeof str === "string") {
    return str.split(",");
  }
  return str;
}

function replyToEmail(data: object) {
  showEmailBox.value = true;

  emailEditorRef.value.addToReply(
    data.content,
    splitIfString(data.to),
    splitIfString(data.cc),
    splitIfString(data.bcc)
  );
}

const props = defineProps({
  doctype: {
    type: String,
    default: "HD Ticket",
  },
  ticketId: {
    type: String,
    default: null,
  },
  toEmails: {
    type: Array,
    default: () => [],
  },
  ccEmails: {
    type: Array,
    default: () => [],
  },
  bccEmails: {
    type: Array,
    default: () => [],
  },
});

watch(
  () => showEmailBox.value,
  (value) => {
    if (value) {
      emailEditorRef.value?.editor?.commands?.focus("start");
    }
  }
);

watch(
  () => showCommentBox.value,
  (value) => {
    if (value) {
      commentTextEditorRef.value?.editor?.commands?.focus();
    }
  }
);

useShortcut("r", () => {
  toggleEmailBox();
});
useShortcut("c", () => {
  toggleCommentBox();
});

defineExpose({
  replyToEmail,
  toggleEmailBox,
  toggleCommentBox,
  editor: emailEditorRef,
});

const IGNORED_SELECTORS = [
  ".tippy-box",
  ".tippy-content",
  ".PopoverContent",
  '[role="dialog"]',
  '[role="menu"]',
  ".dialog-overlay",
];

onClickOutside(
  emailBoxRef,
  () => {
    if (showEmailBox.value) {
      showEmailBox.value = false;
    }
  },
  {
    ignore: IGNORED_SELECTORS,
  }
);

onClickOutside(
  commentBoxRef,
  () => {
    if (showCommentBox.value) {
      showCommentBox.value = false;
    }
  },
  {
    ignore: IGNORED_SELECTORS,
  }
);
</script>

<style>
@media screen and (max-width: 640px) {
  .comm-area {
    width: 100vw;
  }
}

.slide-enter-active,
.slide-leave-active {
  display: grid;
  transition: grid-template-rows 0.25s ease;
}
.slide-enter-from,
.slide-leave-to {
  grid-template-rows: 0fr;
}
.slide-enter-to,
.slide-leave-from {
  grid-template-rows: 1fr;
}
</style>
