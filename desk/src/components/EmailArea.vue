<template>
  <div
    :id="`communication-${name}`"
    v-bind="$attrs"
    class="grow cursor-pointer bg-surface-base rounded-md text-base leading-6 transition-all duration-300 ease-in-out border border-outline-gray-2"
  >
    <!-- Collapsed: everything but the newest message on a multi-message ticket.
         One line each, so the latest reply is on screen when the ticket opens
         and the history above it stays scannable. -->
    <div
      v-if="collapsed"
      class="flex items-center gap-2 min-w-0"
      @click="emit('expand')"
    >
      <span class="shrink-0">{{ sender.full_name || "Guest" }}</span>
      <span class="truncate text-p-sm text-ink-gray-5 flex-1 min-w-0">
        {{ preview }}
      </span>
      <Tooltip :text="dateFormat(creation, dateTooltipFormat)">
        <span class="shrink-0 text-xs md:text-sm text-ink-gray-5">
          {{ timeAgo(creation) }}
        </span>
      </Tooltip>
    </div>

    <template v-else>
      <div
        class="flex items-center justify-between gap-2"
        :class="isMobileView && 'items-start'"
      >
        <!-- email design for mobile -->
        <div v-if="isMobileView" class="flex items-center gap-2 text-sm">
          <div class="leading-tight">
            <p>{{ sender.full_name || "Guest" }}</p>
            <Tooltip :text="dateFormat(creation, dateTooltipFormat)">
              <p class="text-xs md:text-sm text-ink-gray-5">
                {{ timeAgo(creation) }}
              </p>
            </Tooltip>
            <p
              class="sm:flex hidden text-sm text-ink-gray-5"
              v-if="sender.name"
            >
              {{ "<" + sender.name + ">" }}
            </p>
          </div>
        </div>
        <!-- email design for desktop -->
        <div v-else class="flex items-center gap-1">
          <span>{{ sender.full_name || "Guest" }}</span>
          <span
            class="sm:flex hidden text-sm text-ink-gray-5"
            v-if="sender.name"
            >{{ "<" + sender.name + ">" }}</span
          >
        </div>

        <div class="flex gap-2 items-center">
          <div class="gap-0.5 flex items-center">
            <Badge
              v-if="status.label && !ticket?.doc?.via_customer_portal"
              :label="__(status.label)"
              variant="subtle"
              :theme="status.color"
              class="mr-1.5"
            />
            <Tooltip
              :text="dateFormat(creation, dateTooltipFormat)"
              v-if="!isMobileView"
            >
              <p class="text-xs md:text-sm text-ink-gray-5">
                {{ timeAgo(creation) }}
              </p>
            </Tooltip>
          </div>
          <div class="flex items-center gap-1">
            <Button :tooltip="__('Reply')" variant="ghost" @click="reply">
              <template #icon>
                <ReplyIcon class="text-ink-gray-7" />
              </template>
            </Button>
            <Button
              :tooltip="__('Reply All')"
              variant="ghost"
              @click="replyAll"
            >
              <template #icon>
                <ReplyAllIcon class="text-ink-gray-7" />
              </template>
            </Button>
            <Dropdown
              v-if="showSplitOption"
              :placement="'right'"
              :options="[
                {
                  label: 'Split Ticket',
                  icon: LucideSplit,
                  onClick: () => (showSplitModal = true),
                },
              ]"
            >
              <Button
                icon="lucide-more-horizontal"
                class="!text-ink-gray-7"
                variant="ghost"
              />
            </Dropdown>
          </div>
        </div>
      </div>
      <!-- <div class="text-sm leading-5 text-ink-gray-5">
      {{ subject }}
    </div> -->
      <div class="text-p-sm text-ink-gray-5">
        <template
          v-for="(val, label) in { To: to, cc: cc, bcc: bcc }"
          :key="label"
        >
          <span v-if="val" class="mr-1.5">
            <span class="mr-1 text-ink-gray-7">{{ label }}:</span>
            <span> {{ normalizeAndFilter(val).join(", ") }}</span>
          </span>
        </template>
      </div>
      <div class="border-0 border-t my-3 border-outline-elevation-2 !-mx-3" />
      <!-- A short machine alert is ~4% text by weight: 12k of table markup for
         four lines. Rendering those lines directly turns a 500px iframe with
         its own scrollbar into four lines. Anything longer, and anything from
         a person, keeps its original HTML. -->
      <div
        v-if="compactLines?.length && !showOriginalEmail"
        class="flex flex-col"
      >
        <p
          v-for="(line, i) in compactLines"
          :key="i"
          class="text-p-sm text-ink-gray-7"
          :class="i === 0 && 'font-medium text-ink-gray-8'"
        >
          {{ line }}
        </p>
        <button
          class="mt-2 self-start text-p-sm text-ink-gray-5 hover:text-ink-gray-7 underline underline-offset-2"
          @click="showOriginalEmail = true"
        >
          {{ __("View original") }}
        </button>
      </div>
      <EmailContent v-else :content="content" />
      <div v-if="attachments?.length" class="flex flex-wrap items-center gap-2">
        <AttachmentItem
          v-for="a in visibleAttachments"
          :key="a.name || a.file_url"
          :label="a.file_name"
          :url="a.file_url"
        />
        <button
          v-if="noiseAttachments.length"
          class="text-p-sm text-ink-gray-5 hover:text-ink-gray-7 underline underline-offset-2"
          @click="showNoisyAttachments = !showNoisyAttachments"
        >
          <template v-if="showNoisyAttachments">
            {{ __("hide signature images") }}
          </template>
          <template v-else>
            + {{ noiseAttachments.length }}
            {{ __("from signatures & quoted replies") }}
          </template>
        </button>
      </div>
    </template>
  </div>
  <TicketSplitModal
    v-model="showSplitModal"
    :ticket_id="name"
    :communication_id="name"
  />
</template>

<script setup lang="ts">
import { AttachmentItem } from "@/components";
import { helpdeskSupportEmails } from "@/composables/replyRecipients";
import { useScreenSize } from "@/composables/screen";
import { getUserEmailInfo } from "@/composables/useUserEmailInfo";
import { useAuthStore } from "@/stores/auth";
import { TicketSymbol } from "@/types";
import { dateFormat, dateTooltipFormat, timeAgo } from "@/utils";
import { Dropdown } from "frappe-ui";
import { storeToRefs } from "pinia";
import { computed, inject, ref } from "vue";
import LucideSplit from "~icons/lucide/split";
import { ReplyAllIcon, ReplyIcon } from "./icons";
import TicketSplitModal from "./ticket/TicketSplitModal.vue";

const props = defineProps({
  activity: {
    type: Object,
    required: true,
  },
  showSplitOption: {
    type: Boolean,
    default: false,
  },
  collapsed: {
    type: Boolean,
    default: false,
  },
});

const {
  sender,
  to,
  cc,
  bcc,
  creation,
  subject,
  attachments,
  content,
  name,
  deliveryStatus,
  compactLines,
} = props.activity;

const showOriginalEmail = ref(false);

const emit = defineEmits(["reply", "expand"]);
const ticket = inject(TicketSymbol)!;

// One line of the message for the collapsed row. compactLines is already the
// distilled version of a machine alert; for anything else, take the text out
// of the HTML — style and script blocks first, or an Outlook mail would
// preview as a wall of CSS.
const preview = computed(() => {
  if (compactLines?.length) return compactLines[0];

  const stripped = (content || "")
    .replace(/<(style|script|head)\b[^>]*>[\s\S]*?<\/\1>/gi, " ")
    .replace(/<!--[\s\S]*?-->/g, " ")
    .replace(/<[^>]+>/g, " ");
  const doc = new DOMParser().parseFromString(stripped, "text/html");
  return (doc.body.textContent || "").replace(/\s+/g, " ").trim().slice(0, 160);
});

// The backend flags signature graphics, tracking pixels and images quoted back
// from an earlier reply. Nothing is discarded — a thread that re-embeds one
// logo on every quote can show sixteen chips holding four distinct images, so
// the noisy ones fold behind a count instead of burying the real attachment.
const showNoisyAttachments = ref(false);
const realAttachments = computed(() =>
  (attachments || []).filter((a) => !a.is_noise)
);
const noiseAttachments = computed(() =>
  (attachments || []).filter((a) => a.is_noise)
);
const visibleAttachments = computed(() =>
  showNoisyAttachments.value
    ? [...realAttachments.value, ...noiseAttachments.value]
    : realAttachments.value
);

const auth = storeToRefs(useAuthStore());

const { isMobileView } = useScreenSize();

const showSplitModal = ref(false);

const status = computed(() => {
  let _status = deliveryStatus;
  let indicator_color = "red";
  if (["Sent", "Clicked"].includes(_status)) {
    indicator_color = "green";
  } else if (["Sending", "Scheduled"].includes(_status)) {
    indicator_color = "orange";
  } else if (["Opened", "Read"].includes(_status)) {
    indicator_color = "blue";
  } else if (_status == "Error") {
    indicator_color = "red";
  }
  return { label: _status, color: indicator_color };
});

const normalizeAndFilter = (
  field: string | string[],
  valuesToExclude: string[] = []
) => {
  let arr = [];
  let current = "";
  let inQuotes = false;
  if (typeof field === "string") {
    for (let char of field) {
      if (char === '"') {
        inQuotes = !inQuotes;
        current += char;
      } else if (char === "," && !inQuotes) {
        arr.push(current.trim());
        current = "";
      } else {
        current += char;
      }
    }
    if (current) arr.push(current.trim());
  } else {
    arr = field || [];
  }
  return arr.filter(Boolean).filter((item) => !valuesToExclude.includes(item));
};

const reply = () => {
  const user = auth.user.value;
  emit("reply", {
    content: content,
    to: user === sender.name ? to : sender.name,
  });
};

// PYEK: the helpdesk's own send addresses (help.pyek@/pos.pyek@ ...). Reply All
// otherwise carries the shared inbox the customer emailed into CC, which copies
// the helpdesk on itself. Strip them (case-insensitive; handles "Name <email>").
const userEmailInfo = getUserEmailInfo();
// helpdeskSupportEmails, not just the personal outgoing list: agents without
// User Email rows get [] there, which let the shared inbox survive Reply All
// (found live on 0493, 2026-08-20).
const supportEmails = computed(() =>
  helpdeskSupportEmails(userEmailInfo.data)
);
const stripSupport = (list: string[]) => {
  if (!supportEmails.value.length) return list;
  return list.filter((item) => {
    const s = String(item).toLowerCase();
    return !supportEmails.value.some((addr) => s.includes(addr));
  });
};

const replyAll = () => {
  const user = auth.user.value;
  const exclude = [user, sender.name];
  const filteredTo = stripSupport(normalizeAndFilter(to, exclude));
  const filteredCc = stripSupport(normalizeAndFilter(cc, exclude));
  const filteredBcc = stripSupport(normalizeAndFilter(bcc, exclude));

  let _to, _cc, _bcc;

  if (user === sender.name) {
    // User is the sender, reply to all original recipients
    _to = filteredTo.join(", ");
    _cc = filteredCc;
    _bcc = filteredBcc;
  } else {
    // User is a recipient, reply to sender with all other recipients in cc
    _to = sender.name;
    _cc = [...filteredTo, ...filteredCc];
    _bcc = filteredBcc;
  }

  emit("reply", {
    content: content,
    to: _to,
    cc: _cc.filter(Boolean),
    bcc: _bcc.filter(Boolean),
  });
};

// TODO: Implement reply functionality using this way instead of emit drillup
// function reply(email, reply_all = false) {
//   emailBox.toggleEmailBox();
//   let editor = emailBox.editor;
//   let message = email.content;
//   let recipients = sender.name;
//   editor.toEmails = [email.sender];
//   editor.cc = editor.bcc = false;
//   editor.ccEmails = [];
//   editor.bccEmails = [];
//   console.log(recipients);

//   if (!email.subject.startsWith("Re:")) {
//     editor.subject = `Re: ${email.subject}`;
//   } else {
//     editor.subject = email.subject;
//   }

//   if (reply_all) {
//     let cc = email.cc?.split(",").map((r) => r.trim());
//     let bcc = email.bcc?.split(",").map((r) => r.trim());

//     if (cc?.length) {
//       recipients = recipients.filter((r) => !cc?.includes(r));
//       cc.push(...recipients);
//     } else {
//       cc = recipients;
//     }

//     editor.cc = cc ? true : false;
//     editor.bcc = bcc ? true : false;

//     editor.ccEmails = cc;
//     editor.bccEmails = bcc;
//   }

//   let repliedMessage = `<blockquote>${message}</blockquote>`;

//   editor.editor
//     .chain()
//     .clearContent()
//     .insertContent("<p>.</p>")
//     .updateAttributes("paragraph", { class: "reply-to-content" })
//     .insertContent(repliedMessage)
//     .focus("all")
//     .insertContentAt(0, { type: "paragraph" })
//     .focus("start")
//     .run();
// }
</script>

<style>
.email-content {
  max-width: 100%;
}
.email-content > * {
  display: flex;
  flex-direction: column;
  flex-wrap: nowrap;
}
</style>
