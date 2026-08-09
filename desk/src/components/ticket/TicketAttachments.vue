<template>
  <div v-if="items.length" class="mx-6 md:mx-5 mb-4">
    <div
      class="rounded-lg border border-outline-gray-2 bg-surface-base overflow-hidden"
    >
      <div class="flex items-center gap-2 px-3 py-2.5">
        <LucidePaperclip class="size-3.5 text-ink-gray-5" />
        <span class="text-base-semibold text-ink-gray-8 select-none">
          {{ __("Attachments") }}
        </span>
        <span
          class="rounded-full bg-surface-gray-3 px-1.5 text-xs font-semibold text-ink-gray-7"
        >
          {{ items.length }}
        </span>
        <span class="flex-1" />
        <span v-if="hiddenCount" class="text-p-sm text-ink-gray-5">
          {{ hiddenCount }} {{ __("hidden") }}
        </span>
        <Button
          variant="ghost"
          :tooltip="collapsed ? __('Show preview') : __('Hide preview')"
          @click="collapsed = !collapsed"
        >
          <template #icon>
            <LucideChevronDown
              class="size-4 text-ink-gray-5 transition-transform"
              :class="{ '-rotate-90': collapsed }"
            />
          </template>
        </Button>
      </div>

      <template v-if="!collapsed">
        <!-- Only worth a switcher when there is something to switch between;
             17 of 270 tickets have more than one real attachment. -->
        <div v-if="items.length > 1" class="flex flex-wrap gap-1.5 px-3 pb-2.5">
          <button
            v-for="(a, i) in items"
            :key="a.name || a.file_url"
            class="inline-flex max-w-[220px] items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs"
            :class="
              i === current
                ? 'border-outline-gray-3 bg-surface-gray-2 text-ink-gray-9'
                : 'border-outline-gray-2 bg-surface-base text-ink-gray-7'
            "
            @click="current = i"
          >
            <!-- `bg-ink-*` generates nothing: the ink group is mapped to
                 textColor only. Surface tokens are the theme-aware fill. -->
            <span
              class="size-1.5 shrink-0 rounded-full"
              :class="i === current ? 'bg-surface-blue-5' : 'bg-surface-gray-5'"
            />
            <span class="truncate">{{ a.file_name }}</span>
          </button>
        </div>

        <div class="border-t border-outline-gray-1">
          <img
            v-if="isImage(active)"
            :src="active.file_url"
            :alt="active.file_name"
            class="block h-[380px] w-full bg-surface-gray-2 object-contain"
          />
          <div
            v-else
            class="flex h-[380px] flex-col items-center justify-center gap-2 bg-surface-gray-2"
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
            class="flex items-center gap-2.5 border-t border-outline-gray-1 px-3 py-2"
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
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { useStorage } from "@vueuse/core";
import { computed, ref, watch } from "vue";
import LucideChevronDown from "~icons/lucide/chevron-down";
import LucidePaperclip from "~icons/lucide/paperclip";

interface Attachment {
  name?: string;
  file_name: string;
  file_url: string;
  file_size?: number;
  is_noise?: boolean;
}

const props = defineProps<{
  activities: { attachments?: Attachment[] }[];
}>();

// Ticket-wide rather than per-email: the point is to answer "what did they
// send us" without reading the thread first. Deduped across emails, because
// the same image legitimately appears on the original and every quote.
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

// New key, not a renamed default on an existing one: useStorage's mergeDefaults
// only fills ABSENT keys, so reusing a key would strand existing users.
const collapsed = useStorage("ticketAttachmentsCollapsed", false);

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
