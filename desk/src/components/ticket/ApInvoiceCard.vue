<template>
  <!-- AP-only card: renders only when the ticket carries AP invoice data, so it
       is invisible on the IT/HR sites (where these fields don't exist). Shows a
       duplicate-invoice warning and the ready-to-use Intacct filename with a
       one-click copy. -->
  <div
    v-if="showDuplicate || filename"
    class="flex flex-col gap-2.5 border-b px-6 py-3"
  >
    <div
      v-if="showDuplicate"
      class="flex items-start gap-2 rounded-md px-3 py-2 text-sm"
      style="background: #fbeaea; color: #a32d2d"
    >
      <LucideCopy class="mt-0.5 size-4 shrink-0" />
      <span
        >Possible duplicate — an invoice with this number is already in the
        queue. Check before paying.</span
      >
    </div>

    <div v-if="filename" class="flex items-center">
      <div class="w-[126px] shrink-0 text-sm text-ink-gray-5">
        Intacct filename
      </div>
      <div class="flex min-w-0 flex-1 items-center gap-1">
        <span
          class="min-w-0 flex-1 truncate font-mono text-sm text-ink-gray-8"
          :title="filename"
          >{{ filename }}</span
        >
        <Button
          variant="ghost"
          icon="copy"
          aria-label="Copy filename"
          @click="copyToClipboard(filename, 'Filename copied to clipboard')"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { copyToClipboard } from "@/utils";
import { Button } from "frappe-ui";
import { computed } from "vue";
import LucideCopy from "~icons/lucide/copy";

const props = defineProps<{ ticket: Record<string, any> }>();
const filename = computed(() => props.ticket?.ap_proposed_filename || "");
const showDuplicate = computed(() => !!props.ticket?.ap_duplicate);
</script>
