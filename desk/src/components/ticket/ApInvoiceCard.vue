<template>
  <!-- AP invoice working card (mobile + desktop ticket detail). Renders only for
       AP tickets (the ap_vendor field is present); on IT/HR it renders nothing,
       so it's safe on the shared component. At-a-glance invoice summary, an
       editable park (fixes mislabels + rewrites the Intacct filename), and the
       copyable Intacct filename. -->
  <div v-if="isAP" class="px-5 pt-4">
    <div class="rounded-xl border border-outline-gray-2 bg-surface-white p-3.5">
      <!-- Header: vendor + editable park -->
      <div class="mb-2.5 flex items-center justify-between gap-2">
        <span class="truncate text-base-medium text-ink-gray-9">
          {{ vendor || __("Invoice") }}
        </span>
        <div class="flex shrink-0 items-center gap-1.5">
          <span
            class="size-2 shrink-0 rounded-full"
            :style="{ backgroundColor: parkColor(parkLabel(park)) }"
          />
          <select
            :value="park"
            :aria-label="__('Park')"
            class="rounded border border-outline-gray-3 bg-surface-white py-0.5 pl-1.5 pr-1 text-xs font-medium text-ink-gray-7"
            @change="onParkChange"
          >
            <option v-for="p in parkOptions" :key="p" :value="p">{{ p || "—" }}</option>
          </select>
          <span v-if="saved" class="text-xs" style="color: #16a34a">{{ __("Saved") }}</span>
        </div>
      </div>

      <!-- Fields -->
      <div class="flex flex-col gap-1.5 text-base">
        <div class="flex items-center justify-between">
          <span class="text-ink-gray-5">{{ __("Amount") }}</span>
          <span class="font-medium text-ink-gray-9">{{ amountLabel }}</span>
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

      <!-- Intacct filename (rewrites its park token when the park changes) -->
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

// --- Editable park -----------------------------------------------------------
// The AP entity codes. `park` is the raw pyek_property value (a code), kept as a
// local ref so the dropdown can change it; the enricher only touches un-enriched
// tickets, so a manual fix here sticks.
const PARK_OPTIONS = ["TTH", "TTA", "CBB", "CBC", "CBV", "DTL", "PYK"];
const park = ref<string>("");
watch(
  () => props.ticket?.pyek_property,
  (v) => (park.value = v || ""),
  { immediate: true }
);
// Show the current value even if it isn't one of the standard codes (older data).
const parkOptions = computed(() => {
  const opts = [...PARK_OPTIONS];
  if (park.value && !opts.includes(park.value)) opts.unshift(park.value);
  if (!park.value) opts.unshift("");
  return opts;
});

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
    fieldname: ["ap_proposed_filename", "ap_duplicate"],
  }),
  auto: computed(
    () => isAP.value && !!props.ticket?.name && !props.ticket?.ap_proposed_filename
  ),
});
// Local, editable copy of the filename so a park change can rewrite it in place.
const filename = ref<string>("");
watch(
  () => props.ticket?.ap_proposed_filename || extra.data?.ap_proposed_filename,
  (v) => {
    if (v) filename.value = v as string;
  },
  { immediate: true }
);
const isDuplicate = computed(
  () => Number(props.ticket?.ap_duplicate ?? extra.data?.ap_duplicate) === 1
);

// --- Persist a park correction + rewrite the filename's park token -----------
const saveRes = createResource({ url: "frappe.client.set_value" });
const saved = ref(false);
async function onParkChange(e: Event) {
  const newCode = (e.target as HTMLSelectElement).value;
  if (newCode === park.value) return;
  park.value = newCode;
  const update: Record<string, string> = { pyek_property: newCode };
  // The Intacct filename is `PARK_InvoiceDate_Vendor_Amount`; the park is the
  // first underscore-delimited token, so swap just that (also cleans stale
  // tokens like a leftover CBV_).
  if (newCode && filename.value && filename.value.includes("_")) {
    filename.value = newCode + filename.value.slice(filename.value.indexOf("_"));
    update.ap_proposed_filename = filename.value;
  }
  try {
    await saveRes.submit({
      doctype: "HD Ticket",
      name: props.ticket.name,
      fieldname: update,
    });
    saved.value = true;
    setTimeout(() => (saved.value = false), 1600);
  } catch (e) {
    // Leave the UI showing the attempted value; the agent can retry.
  }
}

const copied = ref(false);
function copyFilename() {
  if (!filename.value || !navigator.clipboard) return;
  navigator.clipboard.writeText(filename.value);
  copied.value = true;
  setTimeout(() => (copied.value = false), 1400);
}
</script>
