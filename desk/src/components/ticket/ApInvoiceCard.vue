<template>
  <!-- AP-only card: renders only when the ticket carries AP data (ap_vendor is a
       template field present on the AP site, absent on IT/HR). Shows where the email
       came from, the ready-to-use Intacct filename with one-click copy, and a
       duplicate warning. The filename + duplicate flag aren't in the detail payload,
       so they're fetched here (only on the AP site). -->
  <div v-if="isAP" class="flex flex-col gap-2.5 border-b px-6 py-3">
    <!-- From: where the email derived from -->
    <div class="flex flex-col gap-1">
      <div class="text-xs font-medium uppercase tracking-wide text-ink-gray-5">From</div>
      <div class="truncate text-sm text-ink-gray-8" :title="sender">{{ sender }}</div>
      <div class="flex flex-wrap items-center gap-1.5">
        <span
          v-if="park"
          class="rounded border border-outline-gray-3 px-1.5 py-px text-[10px] font-medium leading-4 text-ink-gray-6"
        >{{ park }}</span>
        <span v-if="vendor" class="text-xs text-ink-gray-6">{{ vendor }}</span>
      </div>
    </div>

    <!-- Duplicate warning (near-duplicate: same invoice #, different amount) -->
    <div
      v-if="showDuplicate"
      class="flex items-start gap-2 rounded-md px-3 py-2 text-sm"
      style="background: #fbeaea; color: #a32d2d"
    >
      <LucideCopy class="mt-0.5 size-4 shrink-0" />
      <span>Possible duplicate — an invoice with this number is already in the queue. Check before paying.</span>
    </div>

    <!-- Intacct filename + one-click copy -->
    <div v-if="filename" class="flex items-center">
      <div class="w-[126px] shrink-0 text-sm text-ink-gray-5">Intacct filename</div>
      <div class="flex min-w-0 flex-1 items-center gap-1">
        <span
          class="min-w-0 flex-1 truncate font-mono text-sm text-ink-gray-8"
          :title="filename"
        >{{ filename }}</span>
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
import { Button, createResource } from "frappe-ui";
import { computed, onMounted, watch } from "vue";
import LucideCopy from "~icons/lucide/copy";

const props = defineProps<{ ticket: Record<string, any> }>();

// Present on the AP site (ap_vendor is a template field there); absent on IT/HR.
const isAP = computed(() => "ap_vendor" in (props.ticket || {}));
const vendor = computed(() => props.ticket?.ap_vendor || "");
const park = computed(() => props.ticket?.pyek_property || "");
const sender = computed(
  () => props.ticket?.raised_by || props.ticket?.contact || "—"
);

// The filename + duplicate flag aren't in the detail payload — fetch them, but only
// on the AP site (so IT/HR never query columns that don't exist there).
const apData = createResource({ url: "frappe.client.get_value" });
function loadAp() {
  if (!isAP.value || !props.ticket?.name) return;
  apData.submit({
    doctype: "HD Ticket",
    filters: props.ticket.name,
    fieldname: JSON.stringify(["ap_proposed_filename", "ap_duplicate"]),
  });
}
onMounted(loadAp);
watch(() => props.ticket?.name, loadAp);

const filename = computed(() => apData.data?.ap_proposed_filename || "");
const showDuplicate = computed(() => !!apData.data?.ap_duplicate);
</script>
