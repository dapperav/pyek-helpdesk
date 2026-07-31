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
import { computed, inject } from "vue";
import { useIsAp } from "@/composables/useIsAp";
import LucideFileText from "~icons/lucide/file-text";
import LucideFileX from "~icons/lucide/file-x";
import LucideExternalLink from "~icons/lucide/external-link";

const ticketRef = inject(TicketSymbol)!;
const activities = inject(ActivitiesSymbol, undefined);

const ticket = computed<Record<string, any>>(() => ticketRef.value?.doc || {});
const isAP = useIsAp(() => ticketRef.value?.doc);

// Machine pointer to the exact PDF the fields came from — not a template field, so
// self-fetch it. Falls back to the largest attached PDF if the pointer isn't set yet.
const extra = createResource({
  url: "frappe.client.get_value",
  makeParams: () => ({
    doctype: "HD Ticket",
    filters: { name: ticket.value.name },
    fieldname: ["ap_invoice_file"],
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

const invoiceUrl = computed(
  () => extra.data?.ap_invoice_file || fallbackInvoice.value?.url || ""
);
const invoiceName = computed(() => {
  const u = extra.data?.ap_invoice_file;
  if (u) return String(u).split("/").pop();
  return fallbackInvoice.value?.name || "";
});

// Open the PDF fit-to-width with the thumbnail/nav pane collapsed so it fills the
// pane and Nedra never has to zoom. (view/navpanes/pagemode are best-effort hints the
// browser's PDF viewer may or may not honor; fit-width is the important one.)
const viewerUrl = computed(() =>
  invoiceUrl.value ? `${invoiceUrl.value}#view=FitH&navpanes=0&pagemode=none` : ""
);
</script>
