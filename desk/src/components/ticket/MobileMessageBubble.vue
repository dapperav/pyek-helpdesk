<template>
  <!-- One email as an iMessage-style bubble (Mark, 2026-08-17: "mimic what an
       iMessage chat looks like as much as possible"). Incoming: avatar beside
       a gray tail-cornered bubble, sender name in small gray above. Outgoing:
       iMessage blue, white text, sender avatar on the RIGHT (a departure from
       strict iMessage — Mark, later that day: "so it looks like we are
       replying back and forth with someone"). Time and the Original escape
       live UNDER the bubble like iMessage's Delivered line; image attachments
       render as media previews inside the bubble. -->
  <div
    v-if="!showOriginal"
    class="flex w-full gap-1.5"
    :class="out ? 'justify-end' : 'justify-start'"
  >
    <Avatar
      v-if="!out"
      class="mb-5 shrink-0 self-end"
      size="md"
      :label="senderName"
      :image="senderImage"
    />
    <div
      class="flex flex-col"
      :class="[out ? 'items-end' : 'items-start', widthClass]"
    >
      <span
        v-if="showName"
        class="mb-0.5 text-[11px] text-ink-gray-5"
        :class="out ? 'me-3' : 'ms-3'"
        >{{ senderName }}</span
      >
      <div
        class="rounded-2xl px-3.5 py-2"
        :class="
          out
            ? 'rounded-br-md text-white'
            : 'rounded-bl-md bg-surface-gray-2 text-ink-gray-9'
        "
        :style="out ? { backgroundColor: '#0a84ff' } : {}"
      >
        <div
          v-if="text"
          class="whitespace-pre-wrap break-words text-p-sm leading-relaxed"
        >
          {{ text }}
        </div>
        <!-- Screenshots and photos as media, the iMessage way. -->
        <div
          v-if="imageAttachments.length"
          class="flex flex-col gap-1.5"
          :class="text ? 'mt-1.5' : ''"
        >
          <a
            v-for="a in imageAttachments"
            :key="a.file_url"
            :href="a.file_url"
            target="_blank"
            rel="noopener"
          >
            <img
              :src="a.file_url"
              :alt="a.file_name"
              class="max-h-64 max-w-full rounded-xl object-cover"
              loading="lazy"
            />
          </a>
        </div>
        <div
          v-if="fileAttachments.length"
          class="flex flex-wrap gap-1.5"
          :class="text || imageAttachments.length ? 'mt-1.5' : ''"
        >
          <AttachmentItem
            v-for="a in fileAttachments"
            :key="a.file_url"
            :label="a.file_name"
            :url="a.file_url"
          />
        </div>
      </div>
      <div
        class="mt-0.5 flex items-center gap-1.5 text-[11px] text-ink-gray-4"
        :class="out ? 'me-1' : 'ms-1'"
      >
        <span>{{ when }}</span>
        <!-- This bubble was mined out of someone's forward/quote chain
             (TicketAgentActivities expands email.chain); the tag is the only
             mark of how it arrived. -->
        <span v-if="activity.forwardedBy"
          >· ↪ {{ __("forwarded by") }} {{ activity.forwardedBy }}</span
        >
        <span v-if="activity.bubbleTruncated">· {{ __("trimmed") }}</span>
        <span v-if="hiddenAttachmentCount"
          >· {{ hiddenAttachmentCount }} {{ __("in original") }}</span
        >
        <span v-if="deliveryLabel">· {{ deliveryLabel }}</span>
        <button
          class="underline underline-offset-2"
          @click="showOriginal = true"
        >
          {{ __("Original") }}
        </button>
      </div>
    </div>
    <Avatar
      v-if="out"
      class="mb-5 shrink-0 self-end"
      size="md"
      :label="senderName"
      :image="senderImage"
    />
  </div>
  <div v-else class="w-full rounded-xl border border-outline-gray-2">
    <div class="flex justify-end px-3 pt-1.5">
      <button
        class="text-xs text-ink-gray-5 underline underline-offset-2"
        @click="showOriginal = false"
      >
        {{ __("Back to bubble") }}
      </button>
    </div>
    <!-- A chain bubble's full content lives only inside the email it was
         extracted from — its Original shows that parent email. -->
    <EmailArea
      :activity="activity.chainParent || activity"
      :collapsed="false"
      :show-split-option="false"
      class="py-2 px-3"
      @reply="(e) => emit('reply', e)"
    />
  </div>
</template>

<script setup lang="ts">
import { AttachmentItem } from "@/components";
import EmailArea from "@/components/EmailArea.vue";
import { useUserStore } from "@/stores/user";
import { __ } from "@/translation";
import { TicketContactSymbol } from "@/types";
import { htmlToText } from "@/utils";
import { Avatar, dayjs } from "frappe-ui";
import { computed, inject, ref } from "vue";

const props = defineProps({
  activity: {
    type: Object,
    required: true,
  },
  // Only the newest outgoing message wears the delivery tag, like iMessage's
  // single "Delivered" under the latest sent bubble.
  showDelivery: {
    type: Boolean,
    default: false,
  },
  // Phone default; desktop passes the iMessage-on-Mac cap (65% of the pane
  // but never wider than 560px — Mark's pick, 2026-08-18).
  widthClass: {
    type: String,
    default: "max-w-[78%]",
  },
});
const emit = defineEmits(["reply"]);

const { getUser } = useUserStore();
const showOriginal = ref(false);

const out = computed(() => !!props.activity.outgoing);
const senderName = computed(
  () => props.activity.sender?.full_name || props.activity.sender?.name || ""
);
// Agents resolve through the user store; external requesters have no User
// record, but often have a Contact photo (the same Contact.image the ticket
// cards use) — fall back to it when the sender IS this ticket's contact.
const ticketContact = inject(TicketContactSymbol, null);
const senderImage = computed(() => {
  const userImage = getUser(props.activity.sender?.name)?.user_image;
  if (userImage) return userImage;
  const c: any = (ticketContact as any)?.value?.data;
  if (c?.image && c?.email_id === props.activity.sender?.name) return c.image;
  return undefined;
});
// Incoming always names the sender (ticket threads are group chats — the
// requester, CC'd people, Echo); your own messages don't need your name, a
// teammate's outgoing does.
const showName = computed(
  () =>
    !out.value ||
    (!!props.activity.sender?.name &&
      props.activity.sender.name !== (window as any).agent)
);

const text = computed(() => {
  const lines = props.activity.bubbleLines;
  if (lines?.length) return lines.join("\n");
  // The whole email WAS the forward: its content renders as the extracted
  // chain bubbles above this one. Falling through to htmlToText here would
  // re-flatten that entire chain back into this bubble.
  if (props.activity.hasChain) return __("(forwarded without comment)");
  // No server extraction (e.g. an image-only email): client-side strip so a
  // TEXT bubble is never silently blank — unless there's media to show.
  const stripped = htmlToText(props.activity.content || "").trim();
  if (stripped) return stripped.slice(0, 800);
  return imageAttachments.value.length || fileAttachments.value.length
    ? ""
    : __("(no text — tap Original)");
});

const IMAGE_RE = /\.(png|jpe?g|gif|webp|bmp|heic|heif)$/i;
const visibleAttachments = computed(
  () => (props.activity.attachments || []).filter((a: any) => !a.is_noise)
);
const imageAttachments = computed(() =>
  visibleAttachments.value.filter((a: any) =>
    IMAGE_RE.test(a.file_name || a.file_url || "")
  )
);
const fileAttachments = computed(() =>
  visibleAttachments.value.filter(
    (a: any) => !IMAGE_RE.test(a.file_name || a.file_url || "")
  )
);
const hiddenAttachmentCount = computed(
  () => (props.activity.attachments || []).filter((a: any) => a.is_noise).length
);

const DELIVERY_LABELS: Record<string, string> = {
  Sent: __("Delivered"),
  Read: __("Read"),
  Opened: __("Opened"),
  Bounced: __("Bounced"),
  Error: __("Failed"),
};
const deliveryLabel = computed(() =>
  out.value && props.showDelivery
    ? DELIVERY_LABELS[props.activity.deliveryStatus] || null
    : null
);

const when = computed(() => {
  const d = dayjs(props.activity.creation);
  const days = dayjs().diff(d, "day");
  return days >= 1 ? d.format("MMM D, h:mm A") : d.format("h:mm A");
});
</script>
