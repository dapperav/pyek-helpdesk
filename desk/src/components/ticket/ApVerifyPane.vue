<template>
  <!-- AP invoice-verify pane: a big, fit-width view of the invoice PDF so AP can
       read it without zooming. The extracted fields + Download/Verify actions live
       in the right sidebar card (ApInvoiceCard). Rendered only on AP tickets. -->
  <div v-if="isAP" class="flex h-full min-h-0 flex-col">
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

    <!-- Invoice switcher — only when the email carried more than one. The enricher
         reads every attachment but writes only the primary into the ticket's fields,
         so before this the other invoices were invisible here. Each chip shows that
         invoice's OWN amount, which is the thing Nedra is reconciling. -->
    <div
      v-if="invoices.length > 1"
      class="flex shrink-0 gap-1.5 overflow-x-auto border-b border-outline-gray-2 px-4 py-2"
    >
      <!-- Selected pill takes the sidebar navy (--surface-sidebar #1b2a4a) so "which
           invoice am I looking at" reads at a glance and matches the app's brand
           anchor; the rest sit in a light blue of the same family, which keeps them
           legible as buttons rather than dead chips. -->
      <button
        v-for="(inv, i) in invoices"
        :key="inv.fileUrl"
        class="flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs transition-colors"
        :style="
          i === selected
            ? { backgroundColor: '#1b2a4a', color: '#ffffff' }
            : { backgroundColor: '#dbeafe', color: '#1d4ed8' }
        "
        :title="inv.fileName"
        @click="selected = i"
      >
        <span>{{ __("Invoice") }} {{ i + 1 }}</span>
        <span v-if="inv.amount !== null" class="font-medium">{{ money(inv.amount) }}</span>
        <!-- Amber on white is unreadable against the navy, so lighten it when selected. -->
        <LucideTriangleAlert
          v-if="!inv.readable"
          class="size-3"
          :style="{ color: i === selected ? '#fbbf24' : '#b45309' }"
          :title="__('Could not be read automatically')"
        />
      </button>
    </div>
    <div class="min-h-0 flex-1 bg-surface-gray-2">
      <iframe
        v-if="invoiceUrl"
        :src="viewerUrl"
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
</template>

<script setup lang="ts">
import { ActivitiesSymbol, TicketSymbol } from "@/types";
import { __ } from "@/translation";
import { createResource } from "frappe-ui";
import { computed, inject, ref, watch } from "vue";
import { useIsAp } from "@/composables/useIsAp";
import { useApInvoices, useHasApInvoicesField } from "@/composables/useApInvoices";
import LucideFileText from "~icons/lucide/file-text";
import LucideFileX from "~icons/lucide/file-x";
import LucideExternalLink from "~icons/lucide/external-link";
import LucideTriangleAlert from "~icons/lucide/triangle-alert";

const ticketRef = inject(TicketSymbol)!;
const activities = inject(ActivitiesSymbol, undefined);

const ticket = computed<Record<string, any>>(() => ticketRef.value?.doc || {});
const isAP = useIsAp(() => ticketRef.value?.doc);
const hasInvoicesField = useHasApInvoicesField();

// Machine pointer to the exact PDF the fields came from — not a template field, so
// self-fetch it. Falls back to the largest attached PDF if the pointer isn't set yet.
const extra = createResource({
  url: "frappe.client.get_value",
  makeParams: () => ({
    doctype: "HD Ticket",
    filters: { name: ticket.value.name },
    // ap_invoices only once the enricher has created it — see useHasApInvoicesField.
    fieldname: [
      "ap_invoice_file",
      ...(hasInvoicesField.value ? ["ap_invoices"] : []),
    ],
  }),
  auto: computed(() => isAP.value && !!ticket.value.name),
});

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

// Every invoice on the ticket (one element for the ordinary single-invoice case).
const invoices = useApInvoices(
  () => ticket.value,
  () => extra.data,
  () => fallbackInvoice.value
);
// Reset to the primary whenever the ticket or its invoice set changes, so switching
// tickets can't leave the pane pointing at an index that no longer exists.
const selected = ref(0);
watch(
  () => [ticket.value?.name, invoices.value.length],
  () => {
    const i = invoices.value.findIndex((v) => v.primary);
    selected.value = i >= 0 ? i : 0;
  },
  { immediate: true }
);

const current = computed(() => invoices.value[selected.value] || null);
const invoiceUrl = computed(() => current.value?.fileUrl || "");
const invoiceName = computed(() => current.value?.fileName || "");

const money = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

// Open the PDF fit-to-width with the thumbnail/nav pane collapsed so it fills the
// pane and Nedra never has to zoom. (view/navpanes/pagemode are best-effort hints the
// browser's PDF viewer may or may not honor; fit-width is the important one.)
const viewerUrl = computed(() =>
  invoiceUrl.value ? `${invoiceUrl.value}#view=FitH&navpanes=0&pagemode=none` : ""
);
</script>
