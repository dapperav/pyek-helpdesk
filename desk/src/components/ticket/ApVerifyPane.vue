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
      <div class="flex shrink-0 items-center gap-2">
        <!-- PYEK: zoom is a per-agent choice, not a fixed default. See the
             ZOOM_PREF_KEY comment in the script for why. -->
        <Dropdown v-if="invoiceUrl" :options="zoomOptions" placement="bottom-end">
          <Button variant="ghost" :label="zoomLabel(zoom)">
            <template #prefix>
              <LucideSearch class="size-3.5" />
            </template>
          </Button>
        </Dropdown>
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
      <!-- Keyed on zoom: a hash-only src change does not reload an iframe, so
           the element is recreated instead. Held back until the stored zoom has
           loaded, so a large PDF is never fetched twice at two zoom levels. -->
      <iframe
        v-if="invoiceUrl && zoomReady"
        :key="zoom"
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
import { Button, call, createResource, Dropdown } from "frappe-ui";
import { computed, inject, ref, watch } from "vue";
import { useIsAp } from "@/composables/useIsAp";
import {
  normalizeFileUrl,
  useApInvoices,
  useHasApInvoicesField,
  useInlineAttachmentUrls,
} from "@/composables/useApInvoices";
import LucideFileText from "~icons/lucide/file-text";
import LucideFileX from "~icons/lucide/file-x";
import LucideExternalLink from "~icons/lucide/external-link";
import LucideTriangleAlert from "~icons/lucide/triangle-alert";
import LucideSearch from "~icons/lucide/search";

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

// Files the thread embeds in its own body — signature logos and the like.
const inlineUrls = useInlineAttachmentUrls(() => activities?.value);

const fallbackInvoice = computed<{ url: string; name: string } | null>(() => {
  const comms = activities?.value?.data?.communications || [];
  const files: any[] = [];
  for (const c of comms) for (const a of c.attachments || []) files.push(a);
  const pdfs = files.filter((f) =>
    String(f.file_name || f.file_url || "").toLowerCase().endsWith(".pdf")
  );
  // No PDF on the thread is exactly when this used to surface a logo: the pool fell
  // back to every file, largest first, and a signature image outweighs a 1 KB one.
  // Same normaliser as the inline set: these URLs carry a ?fid= query (the real
  // 1205 body links image00180f934.png?fid=a32e55d), so a raw compare never matches.
  const others = files.filter(
    (f) => !inlineUrls.value.has(normalizeFileUrl(f.file_url))
  );
  const pool = pdfs.length ? pdfs : others;
  if (!pool.length) return null;
  pool.sort((a, b) => (b.file_size || 0) - (a.file_size || 0));
  return { url: pool[0].file_url, name: pool[0].file_name };
});

// Every invoice on the ticket (one element for the ordinary single-invoice case).
const invoices = useApInvoices(
  () => ticket.value,
  () => extra.data,
  () => fallbackInvoice.value,
  () => inlineUrls.value
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

// PYEK: how zoomed the invoice opens, remembered per agent.
//
// This pane used to hard-code #view=FitH — fit-to-page-width — so that the invoice
// filled the pane and Nedra never had to zoom. The catch is that fit-width is
// relative to the pane: in a tall narrow column a letter-size invoice is scaled up
// to around 170%, which is what Corey was reopening the tab into every time.
//
// Rather than swap one forced default for another and hand Nedra the opposite
// complaint, the zoom is a per-agent setting. "Fit width" is still one of the
// choices — it just isn't imposed on everyone — and the default for an agent who
// has never touched it is 90%, which is what Corey asked for.
const ZOOM_PREF_KEY = "ap_invoice_zoom";
const DEFAULT_ZOOM = "90";
const ZOOM_CHOICES = ["fit", "50", "75", "90", "100", "125", "150", "200"];

const zoom = ref(DEFAULT_ZOOM);
// Gates the iframe so the PDF isn't loaded once at the default and again at the
// stored zoom. Set on success *and* failure — a preference we can't read must not
// leave the pane permanently blank.
const zoomReady = ref(false);
let zoomRequested = false;

const zoomLabel = (value: string) =>
  value === "fit" ? __("Fit width") : `${value}%`;

const zoomPreferences = createResource({
  url: "helpdesk.api.user_preference.get_user_preferences",
  auto: false,
  onSuccess: (data: Record<string, string>) => {
    const stored = data?.[ZOOM_PREF_KEY];
    if (stored && ZOOM_CHOICES.includes(stored)) zoom.value = stored;
    zoomReady.value = true;
  },
  onError: () => {
    zoomReady.value = true;
  },
});

// The script runs on every ticket, but only AP tickets render this pane — so wait
// for isAP rather than firing the request for IT tickets that will never show it.
watch(
  isAP,
  (val) => {
    if (!val || zoomRequested) return;
    zoomRequested = true;
    zoomPreferences.fetch();
  },
  { immediate: true }
);

const zoomOptions = computed(() =>
  ZOOM_CHOICES.map((value) => ({
    label: zoomLabel(value),
    onClick: () => setZoom(value),
  }))
);

function setZoom(value: string) {
  if (value === zoom.value) return;
  zoom.value = value;
  call("helpdesk.api.user_preference.set_user_preference", {
    key: ZOOM_PREF_KEY,
    value,
  }).catch((e) => {
    // The pane is already at the new zoom; only the memory of it is lost.
    console.error("Failed to save invoice zoom", e);
  });
}

// navpanes/pagemode are best-effort hints the browser's PDF viewer may or may not
// honor; the zoom/view parameter is the one that matters.
const viewerUrl = computed(() => {
  if (!invoiceUrl.value) return "";
  const mode = zoom.value === "fit" ? "view=FitH" : `zoom=${zoom.value}`;
  return `${invoiceUrl.value}#${mode}&navpanes=0&pagemode=none`;
});
</script>
