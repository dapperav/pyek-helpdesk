<template>
  <ActivityHeader :title="title" />

  <div
    v-if="!items.length"
    class="flex flex-1 flex-col items-center justify-center gap-3 text-ink-gray-4"
  >
    <LucidePaperclip class="size-7.5" />
    <span class="text-lg-medium text-ink-gray-8">
      {{ __("No attachments") }}
    </span>
    <!-- Say so explicitly rather than showing a bare empty state: on a ticket
         whose every image was a signature, "nothing here" and "we hid it all"
         look identical, and only one of them is worth a second look. -->
    <span v-if="hiddenCount" class="text-p-sm text-ink-gray-5">
      {{ hiddenCount }}
      {{ __("signature and quoted images were filtered out") }}
    </span>
  </div>

  <div v-else class="flex min-h-0 flex-1 flex-col px-6 pb-4 md:px-5">
    <div v-if="items.length > 1" class="flex flex-wrap gap-1.5 pb-3">
      <button
        v-for="(a, i) in items"
        :key="a.name || a.file_url"
        class="inline-flex max-w-[240px] items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs"
        :class="
          i === current
            ? 'border-outline-gray-3 bg-surface-gray-2 text-ink-gray-9'
            : 'border-outline-gray-2 bg-surface-base text-ink-gray-7'
        "
        @click="current = i"
      >
        <!-- `bg-ink-*` generates nothing: the ink group is mapped to textColor
             only. Surface tokens are the theme-aware fill. -->
        <span
          class="size-1.5 shrink-0 rounded-full"
          :class="i === current ? 'bg-surface-blue-5' : 'bg-surface-gray-5'"
        />
        <span class="truncate">{{ a.file_name }}</span>
      </button>
    </div>

    <div
      class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-base"
    >
      <img
        v-if="isImage(active)"
        :src="active.file_url"
        :alt="active.file_name"
        class="min-h-0 w-full flex-1 bg-surface-gray-2 object-contain"
      />
      <div
        v-else
        class="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 bg-surface-gray-2"
      >
        <div
          class="rounded-md border border-outline-gray-3 bg-surface-base px-3.5 py-2.5 text-sm font-semibold tracking-wide text-ink-gray-7"
        >
          {{ extension(active) }}
        </div>
        <span class="text-p-sm text-ink-gray-5">
          {{ __("No inline preview — open to view") }}
        </span>
      </div>

      <div
        class="flex shrink-0 items-center gap-2.5 border-t border-outline-gray-1 px-3 py-2"
      >
        <span class="truncate text-sm text-ink-gray-8">
          {{ active.file_name }}
        </span>
        <span class="shrink-0 text-p-sm text-ink-gray-5">
          {{ readableSize(active) }}
        </span>
        <span class="flex-1" />
        <a :href="active.file_url" target="_blank" rel="noopener">
          <Button variant="outline" :label="__('Open')" />
        </a>
        <a :href="active.file_url" :download="active.file_name">
          <Button variant="outline" :label="__('Download')" />
        </a>
      </div>
    </div>

    <div v-if="hiddenCount" class="shrink-0 pt-2 text-p-sm text-ink-gray-5">
      {{ hiddenCount }}
      {{ __("signature and quoted images hidden") }}
    </div>
  </div>
</template>

<script setup lang="ts">
import ActivityHeader from "@/components/ticket/ActivityHeader.vue";
import { Button } from "frappe-ui";
import { computed, ref, watch } from "vue";
import LucidePaperclip from "~icons/lucide/paperclip";

interface Attachment {
  name?: string;
  file_name: string;
  file_url: string;
  file_size?: number;
  is_noise?: boolean;
}

const props = withDefaults(
  defineProps<{
    activities: { attachments?: Attachment[] }[];
    title?: string;
  }>(),
  { title: "Attachments" }
);

// Ticket-wide, deduped: the point of a dedicated tab is to answer "what did
// they send us" without reading the thread. The same image legitimately
// appears on the original and on every quote of it.
const items = computed<Attachment[]>(() => {
  const out: Attachment[] = [];
  const seen = new Set<string>();
  for (const a of props.activities.flatMap((c) => c.attachments || [])) {
    if (a.is_noise) continue;
    const key = a.file_url || a.name || "";
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(a);
  }
  return out;
});

const hiddenCount = computed(
  () =>
    props.activities.flatMap((c) => c.attachments || []).filter((a) => a.is_noise)
      .length
);

const current = ref(0);
watch(items, () => (current.value = 0));
const active = computed(() => items.value[current.value] || items.value[0]);

const IMAGE = /\.(png|jpe?g|gif|webp|bmp|svg)$/i;
const isImage = (a?: Attachment) => !!a && IMAGE.test(a.file_name || "");
const extension = (a?: Attachment) =>
  (a?.file_name || "").split(".").pop()?.toUpperCase() || "FILE";

function readableSize(a?: Attachment) {
  const n = a?.file_size || 0;
  if (!n) return "";
  if (n >= 1048576) return `${(n / 1048576).toFixed(1)} MB`;
  if (n >= 1024) return `${Math.round(n / 1024)} KB`;
  return `${n} B`;
}
</script>
