<template>
  <!-- One email as a message bubble (Mark, 2026-08-15: "like an imessage
       thread… but when sent it sends it like an email"). The bubble shows the
       server-extracted plain text (bubble_lines — quoted tails stripped, long
       mail trimmed); the real email is always one tap away and swaps this row
       to the full EmailArea, reply arrows and all. -->
  <div v-if="!showOriginal" class="flex w-full" :class="out ? 'justify-end' : 'justify-start'">
    <div
      class="max-w-[85%] rounded-2xl border px-3 py-2"
      :class="
        out
          ? 'rounded-br-md border-outline-gray-2 bg-surface-blue-2'
          : 'rounded-bl-md border-outline-gray-2 bg-surface-base shadow-sm'
      "
    >
      <!-- Incoming always names the sender; outgoing only when it isn't the
           viewer — your own texts don't need your name, a teammate's do. -->
      <div v-if="showName" class="mb-1 flex items-center gap-1.5">
        <Avatar
          size="sm"
          :label="senderName"
          :image="senderImage"
        />
        <span class="text-xs font-medium text-ink-gray-7">{{ senderName }}</span>
      </div>
      <div class="whitespace-pre-wrap break-words text-p-sm leading-relaxed text-ink-gray-9">{{
        text
      }}</div>
      <div
        v-if="visibleAttachments.length"
        class="mt-1.5 flex flex-wrap gap-1.5"
      >
        <AttachmentItem
          v-for="a in visibleAttachments"
          :key="a.file_url"
          :label="a.file_name"
          :url="a.file_url"
        />
      </div>
      <div class="mt-1 flex items-center gap-2 text-xs text-ink-gray-4" :class="out && 'justify-end'">
        <span>{{ when }}</span>
        <span v-if="activity.bubbleTruncated">· {{ __("trimmed") }}</span>
        <span v-if="hiddenAttachmentCount">· {{ hiddenAttachmentCount }} {{ __("in original") }}</span>
        <button class="underline underline-offset-2" @click="showOriginal = true">
          {{ __("Original") }}
        </button>
      </div>
    </div>
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
    <EmailArea
      :activity="activity"
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
import { htmlToText } from "@/utils";
import { Avatar, dayjs } from "frappe-ui";
import { computed, ref } from "vue";

const props = defineProps({
  activity: {
    type: Object,
    required: true,
  },
});
const emit = defineEmits(["reply"]);

const { getUser } = useUserStore();
const showOriginal = ref(false);

const out = computed(() => !!props.activity.outgoing);
const showName = computed(
  () =>
    !out.value ||
    (!!props.activity.sender?.name &&
      props.activity.sender.name !== (window as any).agent)
);
const senderName = computed(
  () =>
    props.activity.sender?.full_name || props.activity.sender?.name || ""
);
const senderImage = computed(
  () => getUser(props.activity.sender?.name)?.user_image
);

const text = computed(() => {
  const lines = props.activity.bubbleLines;
  if (lines?.length) return lines.join("\n");
  // No server extraction (e.g. an empty or image-only email): fall back to a
  // client-side strip so the bubble is never blank.
  const stripped = htmlToText(props.activity.content || "").trim();
  return stripped.slice(0, 800) || __("(no text — tap Original)");
});

// Signature furniture (is_noise from the attachment noise pass) stays out of
// the bubble; the count line says it exists, Original shows everything.
const visibleAttachments = computed(
  () => (props.activity.attachments || []).filter((a: any) => !a.is_noise)
);
const hiddenAttachmentCount = computed(
  () => (props.activity.attachments || []).filter((a: any) => a.is_noise).length
);

const when = computed(() => {
  const d = dayjs(props.activity.creation);
  const days = dayjs().diff(d, "day");
  return days >= 1 ? d.format("MMM D, h:mm A") : d.format("h:mm A");
});
</script>
