<template>
  <!-- AP invoice working card (mobile + desktop ticket detail). Renders only for
       AP tickets (the ap_vendor field is present); on IT/HR it renders nothing.
       Park is READ-ONLY here — it's edited on the Property field in Details; this
       card watches that field and rewrites the Intacct filename to match. -->
  <div v-if="isAP" class="px-5 pt-4">
    <div class="rounded-xl border border-outline-gray-2 bg-surface-white p-3.5">
      <!-- Header: vendor + park (read-only) -->
      <div class="mb-2.5 flex items-center justify-between gap-2">
        <span class="truncate text-base-medium text-ink-gray-9">
          {{ vendor || __("Invoice") }}
        </span>
        <span
          v-if="park"
          class="shrink-0 rounded-full px-2 py-0.5 text-xs font-medium text-white"
          :style="{ backgroundColor: parkColor(park) }"
        >
          {{ park }}
        </span>
      </div>

      <!-- Fields -->
      <div class="flex flex-col gap-1.5 text-base">
        <div class="flex items-center justify-between">
          <span class="text-ink-gray-5">{{ __("Amount") }}</span>
          <span class="font-medium text-ink-gray-9">{{ amountLabel }}</span>
        </div>
        <div v-if="receivedDate" class="flex items-center justify-between">
          <span class="text-ink-gray-5">{{ __("Received") }}</span>
          <span class="text-ink-gray-8">{{ receivedDate }}</span>
        </div>
        <div v-if="ticket.ap_invoice_number" class="flex items-center justify-between">
          <span class="text-ink-gray-5">{{ __("Invoice #") }}</span>
          <span class="text-ink-gray-8">{{ ticket.ap_invoice_number }}</span>
        </div>
        <div v-if="invoiceDate" class="flex items-center justify-between">
          <span class="text-ink-gray-5">{{ __("Invoice date") }}</span>
          <span class="text-ink-gray-8">{{ invoiceDate }}</span>
        </div>
        <div v-if="dueDate" class="flex items-center justify-between">
          <span class="text-ink-gray-5">{{ __("Due date") }}</span>
          <span
            :class="isOverdue ? '' : 'text-ink-gray-8'"
            :style="isOverdue ? { color: '#b91c1c' } : {}"
          >{{ dueDate }}</span>
        </div>
        <div v-if="ticket.ap_doc_type" class="flex items-center justify-between">
          <span class="text-ink-gray-5">{{ __("Doc type") }}</span>
          <span class="text-ink-gray-8">{{ ticket.ap_doc_type }}</span>
        </div>
      </div>

      <!-- Needs-review banner: the enricher flagged a low-confidence / handwritten /
           reimbursement-mismatch extraction — verify the fields before posting. -->
      <div
        v-if="isNeedsReview"
        class="mt-2.5 flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm"
        style="background-color: #fffbeb; color: #b45309"
      >
        <LucideTriangleAlert class="size-4 shrink-0" />
        {{ __("Needs review — verify fields before posting") }}
      </div>

      <!-- Duplicate / missing banner -->
      <div
        v-if="isDuplicate"
        class="mt-2.5 flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm"
        style="background-color: #fef2f2; color: #b91c1c"
      >
        <LucideTriangleAlert class="size-4 shrink-0" />
        {{ __("Possible duplicate invoice") }}
      </div>
      <div
        v-else-if="isMissing"
        class="mt-2.5 flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm"
        style="background-color: #fffbeb; color: #b45309"
      >
        <LucideFileX class="size-4 shrink-0" />
        {{ __("No invoice attached") }}
      </div>

      <!-- Intacct filename (park token follows the Property field) -->
      <div
        v-if="filename"
        class="mt-2.5 rounded-lg border border-outline-gray-2 px-2.5 py-2"
      >
        <p class="mb-1 text-xs text-ink-gray-5">{{ __("Intacct filename") }}</p>
        <div class="flex items-center gap-2">
          <code class="min-w-0 flex-1 truncate text-sm text-ink-gray-8">{{ filename }}</code>
          <button
            class="shrink-0 rounded-md p-1 text-ink-gray-6 active:bg-surface-gray-2"
            :aria-label="__('Copy filename')"
            @click="copyFilename"
          >
            <LucideCheck v-if="copied" class="size-4" style="color: #16a34a" />
            <LucideCopy v-else class="size-4" />
          </button>
        </div>
      </div>

      <!-- View the invoice PDF (mobile only — jumps to the Emails tab where
           attachments live; on desktop the conversation is already on screen). -->
      <button
        v-if="isMobileView"
        class="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-outline-gray-2 py-2 text-base-medium text-ink-gray-8 active:bg-surface-gray-2"
        @click="$emit('view-pdf')"
      >
        <LucideFileText class="size-4" />
        {{ __("View invoice") }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { parkColor, parkLabel } from "@/config/parks";
import { useScreenSize } from "@/composables/screen";
import { __ } from "@/translation";
import { createResource, dayjs } from "frappe-ui";
import { computed, ref, watch } from "vue";
import LucideTriangleAlert from "~icons/lucide/triangle-alert";
import LucideFileX from "~icons/lucide/file-x";
import LucideCopy from "~icons/lucide/copy";
import LucideCheck from "~icons/lucide/check";
import LucideFileText from "~icons/lucide/file-text";

const props = defineProps<{ ticket: Record<string, any> }>();
defineEmits<{ (e: "view-pdf"): void }>();

const { isMobileView } = useScreenSize();

// AP tickets carry ap_vendor; IT/HR don't → the whole card no-ops there.
const isAP = computed(() => props.ticket && "ap_vendor" in props.ticket);

const vendor = computed(() => props.ticket?.ap_vendor || "");
const park = computed(() => parkLabel(props.ticket?.pyek_property));

const amountLabel = computed(() => {
  const n = Number(props.ticket?.ap_amount);
  if (!props.ticket?.ap_amount || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(n);
});

const fmt = (d?: string) => (d ? dayjs(d).format("MM/DD/YYYY") : "");
const invoiceDate = computed(() => fmt(props.ticket?.ap_invoice_date));
const dueDate = computed(() => fmt(props.ticket?.pyek_requested_due_date));
// True date the sender emailed ap@ (enricher-set from the email's Date header, NOT
// Frappe's ingest time). A template field, so it's on the doc and reacts to edits.
const receivedDate = computed(() => fmt(props.ticket?.ap_received_date));
const isOverdue = computed(
  () =>
    !!props.ticket?.pyek_requested_due_date &&
    props.ticket?.status_category !== "Resolved" &&
    dayjs(props.ticket.pyek_requested_due_date).isBefore(dayjs().startOf("day"))
);

const isMissing = computed(() => Number(props.ticket?.ap_missing_invoice) === 1);

// ap_proposed_filename + ap_duplicate are enricher-set fields the detail payload
// may not include, so self-fetch them once when the filename isn't on the doc.
const extra = createResource({
  url: "frappe.client.get_value",
  makeParams: () => ({
    doctype: "HD Ticket",
    filters: { name: props.ticket?.name },
    fieldname: ["ap_proposed_filename", "ap_duplicate", "ap_needs_review"],
  }),
  auto: computed(
    () => isAP.value && !!props.ticket?.name && !props.ticket?.ap_proposed_filename
  ),
});

// Enricher review flag (not a template field, so self-fetched with the filename/dup).
const isNeedsReview = computed(
  () => Number(props.ticket?.ap_needs_review ?? extra.data?.ap_needs_review) === 1
);
// Enricher-set filename (may carry a stale park token). We display a live copy
// with the CURRENT park token swapped in — see `filename` below.
const storedFilename = ref<string>("");
watch(
  () => props.ticket?.ap_proposed_filename || extra.data?.ap_proposed_filename,
  (v) => {
    if (v) storedFilename.value = v as string;
  },
  { immediate: true }
);
const isDuplicate = computed(
  () => Number(props.ticket?.ap_duplicate ?? extra.data?.ap_duplicate) === 1
);

// The Intacct filename shown/copied ALWAYS reflects the current park (edited on
// the Property field): swap the stored name's first (park) token to the current
// pyek_property. Purely COMPUTED — NO write — so it never races the Property
// field's own save (a second write caused a "document modified" conflict). The
// park is persisted by the Property field, so this stays correct on reopen.
const filename = computed(() => {
  const stored = storedFilename.value;
  if (!stored) return "";
  const code = props.ticket?.pyek_property;
  if (!code || !stored.includes("_")) return stored;
  return code + stored.slice(stored.indexOf("_"));
});

const copied = ref(false);
function copyFilename() {
  if (!filename.value || !navigator.clipboard) return;
  navigator.clipboard.writeText(filename.value);
  copied.value = true;
  setTimeout(() => (copied.value = false), 1400);
}
</script>
