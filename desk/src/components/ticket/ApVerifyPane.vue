<template>
  <!-- AP invoice-verify pane: the invoice PDF pinned beside the AI-extracted fields
       so Nedra checks them side by side without switching windows. Rendered only on
       AP tickets (the "Invoice" tab is AP-only); no-ops otherwise. -->
  <div v-if="isAP" class="flex h-full min-h-0 flex-col md:flex-row">
    <!-- Invoice PDF (left / top on mobile) -->
    <div
      class="flex min-h-0 flex-col border-outline-gray-2 md:flex-1 md:border-r"
      :class="isMobileView ? 'h-[45vh] border-b' : ''"
    >
      <div
        class="flex shrink-0 items-center justify-between gap-2 border-b border-outline-gray-2 px-4 py-2"
      >
        <span class="flex min-w-0 items-center gap-2 text-sm text-ink-gray-6">
          <LucideFileText class="size-4 shrink-0" />
          <span class="truncate">{{ invoiceName || __("Invoice") }}</span>
        </span>
        <a
          v-if="invoiceUrl"
          :href="invoiceUrl"
          target="_blank"
          class="shrink-0 text-ink-gray-5 hover:text-ink-gray-8"
          :aria-label="__('Open invoice in a new tab')"
        >
          <LucideExternalLink class="size-4" />
        </a>
      </div>
      <div class="min-h-0 flex-1 bg-surface-gray-2">
        <iframe
          v-if="invoiceUrl"
          :src="invoiceUrl"
          class="h-full w-full"
          :title="__('Invoice preview')"
        />
        <div
          v-else
          class="flex h-full flex-col items-center justify-center gap-2 px-6 text-center text-ink-gray-5"
        >
          <LucideFileX class="size-6" />
          <span class="text-sm">{{ __("No invoice attachment found on this ticket.") }}</span>
        </div>
      </div>
    </div>

    <!-- Extracted fields + actions (right / bottom on mobile) -->
    <div class="flex min-h-0 flex-col overflow-y-auto md:w-[320px] md:shrink-0">
      <div class="flex flex-col gap-4 p-4">
        <!-- Header: vendor + park -->
        <div class="flex items-center justify-between gap-2">
          <span class="truncate text-lg font-medium text-ink-gray-9">
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

        <div class="text-xs text-ink-gray-5">
          {{ __("Check each field against the invoice, then confirm.") }}
        </div>

        <!-- Fields -->
        <div class="flex flex-col gap-1.5 text-base">
          <div class="flex items-center justify-between">
            <span class="text-ink-gray-5">{{ __("Amount") }}</span>
            <span class="font-medium text-ink-gray-9">{{ amountLabel }}</span>
          </div>
          <div v-if="invoiceNumber" class="flex items-center justify-between">
            <span class="text-ink-gray-5">{{ __("Invoice #") }}</span>
            <span class="text-ink-gray-8">{{ invoiceNumber }}</span>
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
          <div v-if="docType" class="flex items-center justify-between">
            <span class="text-ink-gray-5">{{ __("Doc type") }}</span>
            <span class="text-ink-gray-8">{{ docType }}</span>
          </div>
          <div v-if="receivedDate" class="flex items-center justify-between">
            <span class="text-ink-gray-5">{{ __("Received") }}</span>
            <span class="text-ink-gray-8">{{ receivedDate }}</span>
          </div>
        </div>

        <!-- Needs-review / duplicate banners (hidden once verified) -->
        <div
          v-if="isNeedsReview && !isVerified"
          class="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm"
          style="background-color: #fffbeb; color: #b45309"
        >
          <LucideTriangleAlert class="size-4 shrink-0" />
          {{ __("Needs review — verify fields before posting") }}
        </div>
        <div
          v-if="isDuplicate"
          class="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm"
          style="background-color: #fef2f2; color: #b91c1c"
        >
          <LucideTriangleAlert class="size-4 shrink-0" />
          {{ __("Possible duplicate invoice") }}
        </div>

        <!-- Intacct filename -->
        <div
          v-if="filename"
          class="rounded-lg border border-outline-gray-2 px-2.5 py-2"
        >
          <p class="mb-1 text-xs text-ink-gray-5">{{ __("Intacct filename") }}</p>
          <code class="block truncate text-sm text-ink-gray-8">{{ filename }}</code>
        </div>
      </div>

      <!-- Actions pinned at the bottom of the field column -->
      <div
        class="mt-auto flex flex-col gap-2 border-t border-outline-gray-2 p-4"
      >
        <a
          v-if="invoiceUrl"
          :href="invoiceUrl"
          :download="filename || undefined"
          class="flex w-full items-center justify-center gap-2 rounded-lg border border-outline-gray-2 py-2 text-base-medium text-ink-gray-8 hover:bg-surface-gray-2"
        >
          <LucideDownload class="size-4" />
          {{ __("Download for Intacct") }}
        </a>

        <button
          v-if="!isVerified"
          class="flex w-full items-center justify-center gap-2 rounded-lg py-2 text-base-medium text-white disabled:opacity-60"
          style="background-color: #16a34a"
          :disabled="verifying"
          @click="markVerified"
        >
          <LucideCheck class="size-4" />
          {{ verifying ? __("Saving…") : __("Looks right — mark verified") }}
        </button>
        <div
          v-else
          class="flex items-center justify-center gap-2 rounded-lg py-2 text-base-medium"
          style="background-color: #f0fdf4; color: #15803d"
        >
          <LucideCircleCheck class="size-4" />
          {{ verifiedLabel }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { parkColor, parkLabel } from "@/config/parks";
import { useScreenSize } from "@/composables/screen";
import { useAuthStore } from "@/stores/auth";
import { ActivitiesSymbol, TicketSymbol } from "@/types";
import { __ } from "@/translation";
import { call, createResource, dayjs, toast } from "frappe-ui";
import { computed, inject, ref, watch } from "vue";
import LucideFileText from "~icons/lucide/file-text";
import LucideFileX from "~icons/lucide/file-x";
import LucideExternalLink from "~icons/lucide/external-link";
import LucideDownload from "~icons/lucide/download";
import LucideCheck from "~icons/lucide/check";
import LucideCircleCheck from "~icons/lucide/circle-check";
import LucideTriangleAlert from "~icons/lucide/triangle-alert";

const ticketRef = inject(TicketSymbol)!;
const activities = inject(ActivitiesSymbol, undefined);
const { isMobileView } = useScreenSize();
const auth = useAuthStore();

const ticket = computed<Record<string, any>>(() => ticketRef.value?.doc || {});
const isAP = computed(() => "ap_vendor" in ticket.value);

const vendor = computed(() => ticket.value.ap_vendor || "");
const park = computed(() => parkLabel(ticket.value.pyek_property));
const invoiceNumber = computed(() => ticket.value.ap_invoice_number || "");
const docType = computed(() => ticket.value.ap_doc_type || "");

const amountLabel = computed(() => {
  const n = Number(ticket.value.ap_amount);
  if (!ticket.value.ap_amount || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(n);
});

const fmt = (d?: string) => (d ? dayjs(d).format("MM/DD/YYYY") : "");
const invoiceDate = computed(() => fmt(ticket.value.ap_invoice_date));
const dueDate = computed(() => fmt(ticket.value.pyek_requested_due_date));
const receivedDate = computed(() => fmt(ticket.value.ap_received_date));
const isOverdue = computed(
  () =>
    !!ticket.value.pyek_requested_due_date &&
    ticket.value.status_category !== "Resolved" &&
    dayjs(ticket.value.pyek_requested_due_date).isBefore(dayjs().startOf("day"))
);

// Machine fields the detail payload doesn't carry — self-fetch them once.
const extra = createResource({
  url: "frappe.client.get_value",
  makeParams: () => ({
    doctype: "HD Ticket",
    filters: { name: ticket.value.name },
    fieldname: [
      "ap_invoice_file",
      "ap_proposed_filename",
      "ap_duplicate",
      "ap_needs_review",
      "ap_verified",
      "ap_verified_by",
      "ap_verified_on",
    ],
  }),
  auto: computed(() => isAP.value && !!ticket.value.name),
});

const isNeedsReview = computed(() => Number(extra.data?.ap_needs_review) === 1);
const isDuplicate = computed(() => Number(extra.data?.ap_duplicate) === 1);

// Invoice file: prefer the enricher's exact pointer; fall back to the largest PDF
// attached to the ticket's emails so the pane still works before the pointer is set.
const fallbackInvoice = computed<{ url: string; name: string } | null>(() => {
  const comms = activities?.value?.data?.communications || [];
  const files: any[] = [];
  for (const c of comms) for (const a of c.attachments || []) files.push(a);
  const pdfs = files.filter((f) =>
    String(f.file_name || f.file_url || "").toLowerCase().endsWith(".pdf")
  );
  const pool = pdfs.length ? pdfs : files;
  if (!pool.length) return null;
  pool.sort((a, b) => (b.file_size || 0) - (a.file_size || 0));
  return { url: pool[0].file_url, name: pool[0].file_name };
});

const invoiceUrl = computed(
  () => extra.data?.ap_invoice_file || fallbackInvoice.value?.url || ""
);
const invoiceName = computed(() => {
  const u = extra.data?.ap_invoice_file;
  if (u) return String(u).split("/").pop();
  return fallbackInvoice.value?.name || "";
});

// Intacct filename with the park token swapped to the current pyek_property
// (matches the ApInvoiceCard logic, so the downloaded file is named correctly).
const filename = computed(() => {
  const stored = extra.data?.ap_proposed_filename as string | undefined;
  if (!stored) return "";
  const code = ticket.value.pyek_property;
  if (!code || !stored.includes("_")) return stored;
  return code + stored.slice(stored.indexOf("_"));
});

// --- verification state + action ---
const localVerified = ref(false);
const localVerifiedBy = ref("");
const localVerifiedOn = ref("");
watch(
  () => extra.data,
  (d) => {
    if (d && Number(d.ap_verified) === 1) {
      localVerified.value = true;
      localVerifiedBy.value = d.ap_verified_by || "";
      localVerifiedOn.value = d.ap_verified_on || "";
    }
  }
);
const isVerified = computed(() => localVerified.value);
const verifiedLabel = computed(() => {
  const who = (localVerifiedBy.value || "").split("@")[0];
  const when = localVerifiedOn.value ? dayjs(localVerifiedOn.value).format("MM/DD/YYYY") : "";
  if (who && when) return __("Verified by {0} · {1}").replace("{0}", who).replace("{1}", when);
  return __("Verified");
});

const verifying = ref(false);
async function markVerified() {
  if (verifying.value || !ticket.value.name) return;
  verifying.value = true;
  const now = dayjs().format("YYYY-MM-DD HH:mm:ss");
  try {
    await call("frappe.client.set_value", {
      doctype: "HD Ticket",
      name: ticket.value.name,
      fieldname: {
        ap_verified: 1,
        ap_verified_by: auth.userId,
        ap_verified_on: now,
      },
    });
    localVerified.value = true;
    localVerifiedBy.value = auth.userId;
    localVerifiedOn.value = now;
    toast.success(__("Marked verified"));
  } catch (e) {
    toast.error(__("Couldn't save. Try again."));
  } finally {
    verifying.value = false;
  }
}
</script>
