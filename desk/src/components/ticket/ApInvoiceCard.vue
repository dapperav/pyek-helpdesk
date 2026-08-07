<template>
  <!-- AP invoice working card (mobile + desktop ticket detail). Renders only for
       AP tickets (the ap_vendor field is present); on IT/HR it renders nothing.
       Park is READ-ONLY here — it's edited on the Property field in Details. The
       Intacct filename is derived live from Property/Invoice Date/Vendor/Amount, so
       correcting any of them in the sidebar renames the file straight away. Also
       hosts the invoice-verify actions: download-pre-named + mark-verified-and-assign. -->
  <div v-if="isAP" class="px-5 pt-4">
    <div class="rounded-xl border border-outline-gray-2 bg-surface-white p-3.5">
      <!-- Header: vendor + park, both editable in place. Vendor stays the card's
           title and the park stays a coloured chip, so the card keeps its shape —
           this is the layout Mark wanted preserved; only the editing changed. -->
      <div class="mb-2.5 flex items-center justify-between gap-2">
        <input
          v-if="editingVendor"
          ref="vendorInput"
          v-model="vendorDraft"
          class="min-w-0 flex-1 rounded border border-outline-gray-3 bg-surface-white px-1.5 py-0.5 text-base-medium text-ink-gray-9 outline-none focus:border-outline-gray-4"
          @keydown.enter.prevent="commitVendor"
          @keydown.esc.prevent="editingVendor = false"
          @blur="commitVendor"
        />
        <button
          v-else
          class="min-w-0 flex-1 truncate rounded px-1 -ml-1 text-left text-base-medium hover:bg-surface-gray-2"
          :class="vendor ? 'text-ink-gray-9' : 'text-ink-gray-4'"
          @click="startEditVendor"
        >
          {{ vendor || __("Set vendor") }}
        </button>

        <!-- Park chip doubles as its own picker. -->
        <Popover placement="bottom-end" :show="parkOpen" @update:show="(v) => (parkOpen = v)">
          <template #target="{ togglePopover }">
            <button
              class="shrink-0 rounded-full px-2 py-0.5 text-xs font-medium"
              :class="park ? 'text-white' : 'border border-dashed border-outline-gray-3 text-ink-gray-5'"
              :style="park ? { backgroundColor: parkColor(park) } : {}"
              @click="togglePopover()"
            >
              {{ park || __("Park") }}
            </button>
          </template>
          <template #body>
            <div class="min-w-[150px] rounded-lg bg-surface-elevation-2 p-1.5 shadow-2xl ring-1 ring-black ring-opacity-5">
              <button
                v-for="opt in parkOptions"
                :key="opt || '__blank'"
                class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-ink-gray-8 hover:bg-surface-gray-2"
                @click="setPark(opt)"
              >
                <span
                  v-if="opt"
                  class="size-2.5 shrink-0 rounded-full"
                  :style="{ backgroundColor: parkColor(opt) }"
                />
                <span class="truncate">{{ opt || __("Clear") }}</span>
                <LucideCheck
                  v-if="opt === ticket.pyek_property"
                  class="ml-auto size-4 text-ink-gray-6"
                />
              </button>
            </div>
          </template>
        </Popover>
      </div>

      <!-- Fields — every row click-to-edit, and now the ONLY place these live. The
           "Ticket Info" panel below the card showed the same nine values as editable
           form controls, so each one appeared twice (Terms and the invoice number
           three times); that panel is hidden on AP now. Rows always render, even when
           empty, because a blank "Set" is how you discover you still owe a value —
           the old card hid empty rows and the verify gate then failed for no visible
           reason. -->
      <div class="flex flex-col gap-1.5 text-base">
        <ApField :ticket="ticket" fieldname="ap_amount" :label="__('Amount')" />
        <ApField :ticket="ticket" fieldname="ap_received_date" :label="__('Received')" />
        <ApField :ticket="ticket" fieldname="ap_invoice_number" :label="__('Invoice #')" />
        <ApField :ticket="ticket" fieldname="ap_invoice_date" :label="__('Invoice date')" />
        <ApField
          :ticket="ticket"
          fieldname="pyek_requested_due_date"
          :label="__('Due date')"
          :danger="isOverdue"
        />
        <ApField :ticket="ticket" fieldname="ap_doc_type" :label="__('Doc type')" />
        <ApField
          :ticket="ticket"
          fieldname="ap_payment_terms"
          :label="__('Terms')"
          :also-set="termsSideEffects"
        />
        <ApField
          :ticket="ticket"
          fieldname="ap_missing_invoice"
          :label="__('Missing invoice')"
        />
      </div>

      <!-- Needs-review banner (hidden once verified). -->
      <div
        v-if="isNeedsReview && !isVerified"
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

      <!-- Intacct filename (derived from the current Property/Date/Vendor/Amount).
           Single-invoice tickets only. On a multi-invoice ticket this row is built
           from the TICKET's amount — on #0680, Nedra's $1,262.83 total — so it names
           no file you can actually download, and the per-invoice list below (which
           carries each receipt's own amount) is the honest answer. Showing both just
           invites "which one is that?". -->
      <div
        v-if="filename && invoices.length <= 1"
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

      <!-- Actions, in two labelled zones. Seven control blocks stacked at identical
           visual weight gave no clue where the working surface ended, so they're split
           into the files you act on every ticket and the workflow state you set
           occasionally. -->
      <div class="mt-3 flex flex-col gap-2">
      <p class="px-0.5 text-xs font-medium uppercase tracking-wide text-ink-gray-5">
        {{ __("Invoice files") }}
      </p>

      <!-- Download the invoice already named for Intacct (same-origin: the browser
           saves it with this name, so no manual rename). Solid-blue primary CTA —
           this is the action Nedra takes on every invoice. -->
      <a
        v-if="invoiceUrl && invoices.length <= 1"
        :href="invoiceUrl"
        :download="downloadName || undefined"
        class="flex w-full items-center justify-center gap-2 rounded-lg py-2 text-base-medium text-white"
        style="background-color: #2563eb"
      >
        <LucideDownload class="size-4" />
        {{ __("Download for Intacct") }}
      </a>

      <!-- Several invoices on one email: each is its own document to key into
           Intacct, so each downloads separately under its OWN park/date/vendor/amount
           name. One button saves them all; the list below downloads them one at a
           time and shows the per-invoice amount, because the ticket's ap_amount is
           only ever the primary's (or a hand-typed total) and would be the wrong
           number to stamp on the other files. -->
      <template v-else-if="invoices.length > 1">
        <button
          class="flex w-full items-center justify-center gap-2 rounded-lg py-2 text-base-medium text-white disabled:opacity-60"
          style="background-color: #2563eb"
          :disabled="downloadingAll"
          @click="downloadAll()"
        >
          <LucideDownload class="size-4" />
          {{
            downloadingAll
              ? __("Saving…")
              : __("Download all {0} for Intacct").replace("{0}", String(invoices.length))
          }}
        </button>
        <div class="flex flex-col gap-1 rounded-lg border border-outline-gray-2 p-1.5">
          <button
            v-for="(inv, i) in invoices"
            :key="inv.fileUrl"
            class="flex items-center gap-2 rounded-md px-2 py-1.5 text-left hover:bg-surface-gray-2"
            :title="inv.downloadName"
            @click="downloadOne(inv)"
          >
            <LucideDownload class="size-3.5 shrink-0 text-ink-gray-5" />
            <span class="min-w-0 flex-1 truncate text-xs text-ink-gray-7">
              {{ __("Invoice") }} {{ i + 1 }} · {{ inv.fileName }}
            </span>
            <LucideTriangleAlert
              v-if="!inv.readable"
              class="size-3.5 shrink-0"
              style="color: #b45309"
              :title="__('Could not be read automatically — check the name')"
            />
            <span
              v-if="inv.amount !== null"
              class="shrink-0 text-xs font-medium text-ink-gray-8"
            >{{ moneyLabel(inv.amount) }}</span>
          </button>
        </div>
      </template>

      <!-- Scan / attach the invoice. The enricher only auto-reads a ticket on first
           ingest, so a vendor reply that arrives WITH an invoice (on a Query /
           no-invoice ticket) is never read — Scan re-extracts the CURRENT
           attachments on demand; Attach uploads a file Nedra has, then scans it.
           Below the download + file list deliberately: those are touched on every
           ticket, these two are occasional repairs. -->
      <div class="grid grid-cols-2 gap-2">
        <button
          class="flex items-center justify-center gap-1.5 rounded-lg border border-outline-gray-2 py-2 text-base-medium text-ink-gray-8 hover:bg-surface-gray-2 disabled:opacity-60"
          :disabled="scanning"
          @click="scanInvoice()"
        >
          <LucideScanLine class="size-4" />
          {{ scanning ? __("Scanning…") : __("Scan invoice") }}
        </button>
        <button
          class="flex items-center justify-center gap-1.5 rounded-lg border border-outline-gray-2 py-2 text-base-medium text-ink-gray-8 hover:bg-surface-gray-2 disabled:opacity-60"
          :disabled="scanning"
          @click="pickInvoiceFile()"
        >
          <LucidePaperclip class="size-4" />
          {{ __("Attach") }}
        </button>
      </div>
      <input
        ref="fileInput"
        type="file"
        accept="application/pdf,image/*"
        class="hidden"
        @change="onFilePicked"
      />

      <!-- View the invoice PDF (mobile only — jumps to the Emails tab where
           attachments live; on desktop the Invoice tab already shows it). Belongs
           with the files, not down among the workflow controls. -->
      <button
        v-if="isMobileView"
        class="flex w-full items-center justify-center gap-2 rounded-lg border border-outline-gray-2 py-2 text-base-medium text-ink-gray-8 active:bg-surface-gray-2"
        @click="$emit('view-pdf')"
      >
        <LucideFileText class="size-4" />
        {{ __("View invoice") }}
      </button>

      <p class="mt-2 px-0.5 text-xs font-medium uppercase tracking-wide text-ink-gray-5">
        {{ __("Workflow") }}
      </p>

      <!-- Priority — a CTA button coloured by level (Urgent red → Low gray).
           Opens a small picker. -->
      <Popover class="w-full" placement="bottom" :show="priorityOpen" @update:show="(v) => (priorityOpen = v)">
        <template #target="{ togglePopover }">
          <button
            class="flex w-full items-center justify-between gap-2 rounded-lg py-2 px-3 text-base-medium text-white"
            :style="{ backgroundColor: priorityColor(currentPriority) }"
            @click="togglePopover()"
          >
            <span class="flex items-center gap-2">
              <LucideFlag class="size-4" />
              {{ __("Priority") }}
            </span>
            <span class="flex items-center gap-1">
              {{ currentPriority || __("Set") }}
              <LucideChevronDown class="size-4" />
            </span>
          </button>
        </template>
        <template #body>
          <div class="min-w-[180px] rounded-lg bg-surface-elevation-2 p-1.5 shadow-2xl ring-1 ring-black ring-opacity-5">
            <button
              v-for="p in priorityOptions"
              :key="p"
              class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-ink-gray-8 hover:bg-surface-gray-2"
              @click="setPriority(p)"
            >
              <span class="size-2.5 shrink-0 rounded-full" :style="{ backgroundColor: priorityColor(p) }" />
              <span class="truncate">{{ p }}</span>
              <LucideCheck v-if="p === currentPriority" class="ml-auto size-4 text-ink-gray-6" />
            </button>
            <div v-if="!priorityOptions.length" class="px-2 py-3 text-center text-sm text-ink-gray-5">
              {{ __("No priorities found") }}
            </div>
          </div>
        </template>
      </Popover>

      <!-- The Terms picker that used to sit here is gone: Terms is now an editable
           row in the field list above, carrying the same Personal Reimbursement ->
           doc type side effect. Keeping both would have left Terms on screen twice
           in a change whose whole point was removing duplicates. -->

      <!-- Verify — decoupled from assign. Light-blue CTA that becomes the green
           "Verified by …" pill once stamped. Blocked until every Ticket Info field
           is filled (invoice #/amount/date are relaxed for no-invoice tickets —
           Missing Invoice / Personal Reimbursement). -->
      <div
        v-if="isVerified"
        class="flex w-full items-center justify-center gap-1.5 rounded-lg py-2 px-3 text-base-medium"
        style="background-color: #f0fdf4; color: #15803d"
      >
        <LucideCircleCheck class="size-4 shrink-0" />
        <span>{{ verifiedLabel }}</span>
      </div>
      <template v-else>
        <button
          class="flex w-full items-center justify-center gap-2 rounded-lg py-2 px-3 text-base-medium disabled:opacity-60"
          style="background-color: #dbeafe; color: #1d4ed8"
          :disabled="verifying"
          @click="attemptVerify()"
        >
          {{ verifying ? __("Saving…") : __("Click to mark verified") }}
        </button>
        <p
          v-if="missingFields.length"
          class="px-0.5 text-xs"
          style="color: #b45309"
        >
          {{ __("Fill before verifying:") }} {{ missingFields.join(", ") }}
        </p>
      </template>

      <!-- Assign (independent of verify). Sits UNDER Verify per Nedra's layout.
           Solid-navy CTA when unassigned; once assigned it shows the person in a
           full-size row (same height as the CTAs) with a Change control — the whole
           row opens the picker. Picking someone assigns + emails them (self silent). -->
      <Popover class="w-full" placement="bottom" :show="assignOpen" @update:show="(v) => (assignOpen = v)">
        <template #target="{ togglePopover }">
          <button
            v-if="!assigneeNames.length"
            class="flex w-full items-center justify-center gap-2 rounded-lg py-2 text-base-medium text-white"
            style="background-color: #1b2a4a"
            @click="togglePopover()"
          >
            <LucideUserPlus class="size-4" />
            {{ __("Assign") }}
          </button>
          <button
            v-else
            class="flex w-full items-center justify-between gap-2 rounded-lg border border-outline-gray-2 py-2 px-3 hover:border-outline-gray-3"
            @click="togglePopover()"
          >
            <span class="flex min-w-0 items-center gap-2 text-base-medium text-ink-gray-8">
              <UserAvatar :name="assigneeNames[0]" size="sm" />
              <span class="truncate">{{ assigneeLabel }}</span>
            </span>
            <span class="shrink-0 text-xs font-medium" style="color: #2563eb">
              {{ __("Change") }}
            </span>
          </button>
        </template>
        <template #body>
          <div class="min-w-[240px] rounded-lg bg-surface-elevation-2 p-1.5 shadow-2xl ring-1 ring-black ring-opacity-5">
            <input
              v-model="agentSearch"
              :placeholder="__('Search agents…')"
              class="mb-1 w-full rounded-md border-none bg-surface-gray-2 px-2 py-1.5 text-sm outline-none focus:ring-0"
            />
            <div class="max-h-56 overflow-y-auto">
              <button
                v-for="a in agentOptions"
                :key="a.name"
                class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-ink-gray-8 hover:bg-surface-gray-2"
                @click="assignOne(a)"
              >
                <UserAvatar :name="a.name" size="sm" />
                <span class="truncate">{{ a.label }}</span>
              </button>
              <div
                v-if="!agentOptions.length"
                class="px-2 py-3 text-center text-sm text-ink-gray-5"
              >
                {{ __("No agents found") }}
              </div>
            </div>
          </div>
        </template>
      </Popover>

      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { parkColor } from "@/config/parks";
import { useScreenSize } from "@/composables/screen";
import { useAuthStore } from "@/stores/auth";
import { ActivitiesSymbol, AssigneeSymbol, TicketSymbol } from "@/types";
import { __ } from "@/translation";
import {
  Popover,
  call,
  createResource,
  createListResource,
  dayjs,
  toast,
} from "frappe-ui";
import { computed, inject, nextTick, ref, watch } from "vue";
import { getMeta } from "@/stores/meta";
import { useIsAp } from "@/composables/useIsAp";
import { useApInvoices, useHasApInvoicesField } from "@/composables/useApInvoices";
import ApField from "./ApField.vue";
import UserAvatar from "../UserAvatar.vue";
import LucideTriangleAlert from "~icons/lucide/triangle-alert";
import LucideFileX from "~icons/lucide/file-x";
import LucideCopy from "~icons/lucide/copy";
import LucideCheck from "~icons/lucide/check";
import LucideCircleCheck from "~icons/lucide/circle-check";
import LucideDownload from "~icons/lucide/download";
import LucideFileText from "~icons/lucide/file-text";
import LucideUserPlus from "~icons/lucide/user-plus";
import LucideFlag from "~icons/lucide/flag";
import LucideChevronDown from "~icons/lucide/chevron-down";
import LucideScanLine from "~icons/lucide/scan-line";
import LucidePaperclip from "~icons/lucide/paperclip";

const props = defineProps<{ ticket: Record<string, any> }>();
defineEmits<{ (e: "view-pdf"): void }>();

const { isMobileView } = useScreenSize();
const auth = useAuthStore();
// Optional: present in the ticket-detail context so we can refresh the Assignee
// widget after assigning. Absent contexts just skip the reload (assignment still
// persists via the API call).
const assignees = inject(AssigneeSymbol, undefined);
const activities = inject(ActivitiesSymbol, undefined);
// Present in the ticket-detail context (desktop + mobile) so a priority change
// updates the shared ticket doc reactively; absent contexts fall back to a plain
// set_value write below.
const ticketRes = inject(TicketSymbol, undefined);

// AP tickets carry ap_vendor; IT/HR don't → the whole card no-ops there.
const isAP = useIsAp(() => props.ticket);

const vendor = computed(() => props.ticket?.ap_vendor || "");
// parkLabel() maps blank -> "Unspecified", which is right for a read-only chip but
// wrong for a picker (it would look like a real value). Show the raw code instead.
const park = computed(() => props.ticket?.pyek_property || "");

// --- header editing (vendor + park) ---
const { getField: getTicketField } = getMeta("HD Ticket");
const parkOptions = computed(() => {
  const raw = String((getTicketField("pyek_property") as any)?.options || "").split("\n");
  const values = raw.filter((o) => o !== "");
  return raw.some((o) => o === "") ? ["", ...values] : values;
});
const parkOpen = ref(false);
function setPark(opt: string) {
  parkOpen.value = false;
  writeFields({ pyek_property: opt || null });
}

const editingVendor = ref(false);
const vendorDraft = ref("");
const vendorInput = ref<HTMLInputElement | null>(null);
function startEditVendor() {
  vendorDraft.value = vendor.value;
  editingVendor.value = true;
  nextTick(() => {
    vendorInput.value?.focus();
    vendorInput.value?.select?.();
  });
}
function commitVendor() {
  if (!editingVendor.value) return;
  editingVendor.value = false;
  const v = vendorDraft.value.trim();
  if (v === vendor.value) return;
  writeFields({ ap_vendor: v || null });
}

// Personal Reimbursement also marks the doc type so the ticket lands in the
// Reimbursements queue. Net terms leave the doc type alone.
function termsSideEffects(value: any) {
  return value === "Personal Reimbursement" ? { ap_doc_type: "Reimbursement" } : {};
}

// Shared write path for the header controls (ApField has its own copy for its rows).
function writeFields(fields: Record<string, any>) {
  const ok = () => activities?.value?.reload?.();
  const fail = () => toast.error(__("Couldn't save. Try again."));
  if (ticketRes?.value?.setValue) {
    ticketRes.value.setValue.submit(fields, { onSuccess: ok, onError: fail });
  } else {
    call("frappe.client.set_value", {
      doctype: "HD Ticket",
      name: props.ticket?.name,
      fieldname: fields,
    })
      .then(ok)
      .catch(fail);
  }
}

// The amount/date display formatters that lived here are gone — ApField renders and
// formats every one of those rows now, so keeping local copies would just be a second
// definition of the same formatting to drift out of sync.
const isOverdue = computed(
  () =>
    !!props.ticket?.pyek_requested_due_date &&
    props.ticket?.status_category !== "Resolved" &&
    dayjs(props.ticket.pyek_requested_due_date).isBefore(dayjs().startOf("day"))
);

const isMissing = computed(() => Number(props.ticket?.ap_missing_invoice) === 1);

const hasInvoicesField = useHasApInvoicesField();

// Enricher-set machine fields the detail payload doesn't carry — self-fetch them.
const extra = createResource({
  url: "frappe.client.get_value",
  makeParams: () => ({
    doctype: "HD Ticket",
    filters: { name: props.ticket?.name },
    fieldname: [
      "ap_proposed_filename",
      "ap_duplicate",
      "ap_needs_review",
      "ap_invoice_file",
      // Only once the enricher has created it — see useHasApInvoicesField.
      ...(hasInvoicesField.value ? ["ap_invoices"] : []),
      "ap_verified",
      "ap_verified_by",
      "ap_verified_on",
    ],
  }),
  auto: computed(() => isAP.value && !!props.ticket?.name),
});

const isNeedsReview = computed(
  () => Number(props.ticket?.ap_needs_review ?? extra.data?.ap_needs_review) === 1
);
const isDuplicate = computed(
  () => Number(props.ticket?.ap_duplicate ?? extra.data?.ap_duplicate) === 1
);

// The enricher writes ap_proposed_filename ONCE, at first extraction, and never
// revisits it (enrich.py fills it only when empty so a human edit is never
// clobbered), so it goes stale the moment anyone corrects a field. Kept only as a
// fallback for legacy tickets whose AP fields never populated.
const storedFilename = ref<string>("");
watch(
  () => props.ticket?.ap_proposed_filename || extra.data?.ap_proposed_filename,
  (v) => {
    if (v) storedFilename.value = v as string;
  },
  { immediate: true }
);

// Vendor token: stripped to A-Z0-9, uppercased, capped at 24 chars. Mirrors the
// enricher's _short() so a hand-typed "Suter Law" and an AI-extracted "SUTERLAW"
// produce the same token.
function vendorToken(value: unknown): string {
  const tok = String(value ?? "")
    .replace(/[^A-Za-z0-9]/g, "")
    .toUpperCase()
    .slice(0, 24);
  return tok || "VENDOR";
}

// The Intacct filename shown/copied is DERIVED from the live doc fields on every
// render, never read back from the stored value. Property, Invoice Date, Vendor
// and Amount are all human-editable in the sidebar, so a correction to any of
// them has to show up here at once; previously only the park token was live and
// the other three stayed frozen at whatever the first extraction guessed.
// Convention (Corey): ParkName_InvoiceDate_VendorName_Amount, no commas — same
// shape and same placeholders as the enricher's _filename().
// Purely COMPUTED — NO write — so it can never race a field's own save.
const filename = computed(() => {
  const code = props.ticket?.pyek_property;
  const date = props.ticket?.ap_invoice_date;
  const vend = props.ticket?.ap_vendor;
  const amt = props.ticket?.ap_amount;
  // Nothing to derive from (legacy ticket, fields never populated): show whatever
  // the enricher stored, and let the row hide itself when that's empty too.
  if (!code && !date && !vend && !amt) return storedFilename.value;
  const day = date ? dayjs(date) : null;
  const dateTok = day && day.isValid() ? day.format("MMDDYYYY") : "NODATE";
  const n = Number(amt);
  const amtTok =
    amt !== null && amt !== undefined && amt !== "" && !Number.isNaN(n)
      ? n.toFixed(2)
      : "0.00";
  return `${code || "NOPARK"}_${dateTok}_${vendorToken(vend)}_${amtTok}.pdf`;
});
// Download needs ONE clean name. The derived name is always singular, but the
// legacy fallback can still be a joined "name1 ; name2" — take the primary.
const downloadName = computed(() => filename.value.split(" ; ")[0].trim());

// Exact attachment the fields were read from (for the download link).
const invoiceUrl = computed(() => extra.data?.ap_invoice_file || "");

// --- multi-invoice download ---
// Every invoice on the ticket, each with its own Intacct name. One element for the
// ordinary single-invoice ticket, in which case the plain link above is used instead.
const invoices = useApInvoices(
  () => props.ticket,
  () => extra.data
);
const moneyLabel = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

// Same-origin /private/files URLs, so the anchor's `download` attribute is honoured
// and the browser saves the file under the Intacct name with no manual rename.
function saveAs(url: string, name: string) {
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function downloadOne(inv: { fileUrl: string; downloadName: string }) {
  saveAs(inv.fileUrl, inv.downloadName);
}

const downloadingAll = ref(false);
async function downloadAll() {
  if (downloadingAll.value) return;
  downloadingAll.value = true;
  try {
    // Staggered: browsers drop programmatic downloads fired in the same tick, and
    // Chrome's "allow multiple downloads" prompt needs the clicks spread out to
    // associate them with the gesture. 400ms is comfortably enough in practice.
    for (const inv of invoices.value) {
      saveAs(inv.fileUrl, inv.downloadName);
      await new Promise((r) => setTimeout(r, 400));
    }
    toast.success(
      __("Saved {0} invoices").replace("{0}", String(invoices.value.length))
    );
  } finally {
    downloadingAll.value = false;
  }
}

const copied = ref(false);
function copyFilename() {
  if (!filename.value || !navigator.clipboard) return;
  navigator.clipboard.writeText(filename.value);
  copied.value = true;
  setTimeout(() => (copied.value = false), 1400);
}

// --- scan / attach invoice ---
// Scan re-extracts the ticket's CURRENT attachments via the enricher (server-side
// proxy keeps the token off the browser). Attach uploads a file first, then scans.
const scanning = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);

async function reloadAfterScan() {
  // Pull the freshly-written fields back: enricher-only fields via `extra`, the
  // core ap_* fields via the shared ticket doc.
  try {
    await extra.reload();
  } catch (e) {
    /* noop */
  }
  try {
    await ticketRes?.value?.reload?.();
  } catch (e) {
    /* noop */
  }
}

async function scanInvoice() {
  if (scanning.value || !props.ticket?.name) return;
  scanning.value = true;
  try {
    const res = await call("helpdesk.api.ap_rescan.rescan", {
      ticket: props.ticket.name,
    });
    if (res?.ok) {
      await reloadAfterScan();
      toast.success(__("Invoice scanned"));
    } else {
      toast.error(res?.error || __("Scan failed. Try again."));
    }
  } catch (e) {
    toast.error(__("Scan failed. Try again."));
  } finally {
    scanning.value = false;
  }
}

function pickInvoiceFile() {
  if (scanning.value) return;
  fileInput.value?.click();
}

async function onFilePicked(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = ""; // let the same file be re-picked later
  if (!file || !props.ticket?.name) return;
  scanning.value = true;
  try {
    const form = new FormData();
    form.append("file", file, file.name);
    form.append("is_private", "1");
    form.append("doctype", "HD Ticket");
    form.append("docname", props.ticket.name);
    const r = await fetch("/api/method/upload_file", {
      method: "POST",
      headers: { "X-Frappe-CSRF-Token": (window as any).csrf_token || "" },
      body: form,
    });
    if (!r.ok) throw new Error("upload failed");
    toast.success(__("Invoice attached — scanning…"));
    const res = await call("helpdesk.api.ap_rescan.rescan", {
      ticket: props.ticket.name,
    });
    if (res?.ok) {
      await reloadAfterScan();
      toast.success(__("Invoice scanned"));
    } else {
      toast.error(res?.error || __("Attached, but the scan failed."));
    }
  } catch (err) {
    toast.error(__("Couldn't attach the file. Try again."));
  } finally {
    scanning.value = false;
  }
}

// --- verify + assign ---
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
  // Prefer the agent's proper display name ("Nedra Kennedy") over the email
  // local-part; the pill is full-width now so the whole label + date fits.
  const who =
    displayName(localVerifiedBy.value) ||
    (localVerifiedBy.value || "").split("@")[0];
  const when = localVerifiedOn.value ? dayjs(localVerifiedOn.value).format("MM/DD/YYYY") : "";
  if (who && when) return __("Verified by {0} · {1}").replace("{0}", who).replace("{1}", when);
  return __("Verified");
});

const verifying = ref(false);
async function markVerified() {
  if (verifying.value || !props.ticket?.name || isVerified.value) return;
  verifying.value = true;
  const now = dayjs().format("YYYY-MM-DD HH:mm:ss");
  try {
    await call("frappe.client.set_value", {
      doctype: "HD Ticket",
      name: props.ticket.name,
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

// --- payment terms ---
// Editing moved to the Terms row in the field list (ApField owns the picker, the
// optimistic relabel and the Personal Reimbursement -> doc type side effect). This
// just reads the saved value for the verify gate and the reimbursement check below.
const currentTerms = computed(() => props.ticket?.ap_payment_terms || "");

// --- verify gate ---
// The same fields shown in the "Ticket Info" panel must be filled before a ticket
// can be marked verified. Invoice-specific fields (invoice #, amount, invoice date)
// are relaxed for tickets that legitimately have no invoice — Missing Invoice or a
// Personal Reimbursement.
const REQUIRED_FIELDS: {
  field: string;
  label: string;
  invoiceOnly?: boolean;
}[] = [
  { field: "pyek_property", label: __("Property") },
  { field: "ap_received_date", label: __("Received Date") },
  { field: "ap_invoice_date", label: __("Invoice Date"), invoiceOnly: true },
  { field: "pyek_requested_due_date", label: __("Requested Due Date") },
  { field: "ap_doc_type", label: __("AP Doc Type") },
  { field: "ap_vendor", label: __("Vendor") },
  { field: "ap_invoice_number", label: __("Invoice Number"), invoiceOnly: true },
  { field: "ap_amount", label: __("Amount"), invoiceOnly: true },
  { field: "ap_payment_terms", label: __("Payment Terms") },
];
const isReimbursement = computed(
  () =>
    currentTerms.value === "Personal Reimbursement" ||
    props.ticket?.ap_doc_type === "Reimbursement"
);
const relaxInvoiceFields = computed(
  () => isMissing.value || isReimbursement.value
);
function fieldFilled(field: string): boolean {
  // Payment terms is optimistic-aware; everything else reads the doc.
  if (field === "ap_payment_terms") return !!currentTerms.value;
  const v = props.ticket?.[field];
  if (field === "ap_amount")
    return v !== null && v !== undefined && v !== "" && Number(v) > 0;
  return v !== null && v !== undefined && String(v).trim() !== "";
}
const missingFields = computed(() =>
  REQUIRED_FIELDS.filter(
    (f) => !(f.invoiceOnly && relaxInvoiceFields.value)
  )
    .filter((f) => !fieldFilled(f.field))
    .map((f) => f.label)
);
function attemptVerify() {
  if (verifying.value || isVerified.value) return;
  if (missingFields.value.length) {
    toast.error(
      __("Fill these fields before verifying: {0}").replace(
        "{0}",
        missingFields.value.join(", ")
      )
    );
    return;
  }
  markVerified();
}

// --- priority (moved up from the Details card into a CTA button) ---
const priorityOpen = ref(false);
// Optimistic value so the button relabels/recolours instantly on pick.
const optimisticPriority = ref("");
const currentPriority = computed(
  () => optimisticPriority.value || props.ticket?.priority || ""
);
const priorityRes = createListResource({
  doctype: "HD Ticket Priority",
  fields: ["name"],
  pageLength: 20,
  auto: true,
});
const priorityOptions = computed(() =>
  (priorityRes.data || []).map((p: any) => p.name)
);
const PRIORITY_COLORS: Record<string, string> = {
  Urgent: "#dc2626",
  High: "#ea580c",
  Medium: "#d97706",
  Low: "#64748b",
};
function priorityColor(p: string) {
  return PRIORITY_COLORS[p] || "#64748b";
}
async function setPriority(name: string) {
  priorityOpen.value = false;
  if (!name || !props.ticket?.name || name === currentPriority.value) return;
  const prev = optimisticPriority.value;
  optimisticPriority.value = name; // instant relabel/recolour
  const ok = () => {
    toast.success(__("Priority set to {0}").replace("{0}", name));
    activities?.value?.reload?.();
  };
  const fail = () => {
    optimisticPriority.value = prev; // revert to the real value
    toast.error(__("Couldn't update priority. Try again."));
  };
  // Prefer the shared ticket resource so ticket.doc stays in sync everywhere
  // (its onError signals a failed save — await alone wouldn't); fall back to a
  // direct write if this card renders without the resource.
  if (ticketRes?.value?.setValue) {
    ticketRes.value.setValue.submit(
      { priority: name },
      { onSuccess: ok, onError: fail }
    );
  } else {
    try {
      await call("frappe.client.set_value", {
        doctype: "HD Ticket",
        name: props.ticket.name,
        fieldname: { priority: name },
      });
      ok();
    } catch (e) {
      fail();
    }
  }
}

const assignOpen = ref(false);
// Optimistic assignee for instant feedback before the assignees resource reloads.
const optimisticAssignee = ref<{ name: string; label: string } | null>(null);
const agentSearch = ref("");

// Current assignee(s), shown in the card so it's obvious who owns the ticket
// (mirrors the Details Assignee widget). Reads the shared assignees resource when
// present, else the optimistic value just set from the picker.
const assigneeNames = computed(() => {
  const names = (assignees?.value?.data || [])
    .map((a: any) => a.name)
    .filter(Boolean);
  if (names.length) return names;
  return optimisticAssignee.value ? [optimisticAssignee.value.name] : [];
});
const assigneeLabel = computed(() => {
  const d = assignees?.value?.data || [];
  if (d.length === 1) return displayName(d[0].name);
  if (d.length > 1) return __("{0} assignees").replace("{0}", String(d.length));
  return optimisticAssignee.value ? optimisticAssignee.value.label : "";
});
// Resolve an assignee email to the agent's display name. Match on the linked
// user OR the agent name (they differ for agents on the @pyek.com/@pyekgroup.com
// alias split); fall back to the email's local part.
function displayName(email: string): string {
  if (!email) return "";
  const a = (agentResource.data || []).find(
    (x: any) => (x.user || x.name) === email
  );
  return (a && a.agent_name) || String(email).split("@")[0];
}
const agentResource = createListResource({
  doctype: "HD Agent",
  fields: ["name", "agent_name", "user"],
  filters: { is_active: true },
  pageLength: 50,
  auto: true,
});
const agentOptions = computed(() => {
  const q = agentSearch.value.trim().toLowerCase();
  return (agentResource.data || [])
    // Assign to the agent's LINKED USER, not the HD Agent name — some agents'
    // name (@pyekgroup.com) differs from their real User (@pyek.com), and
    // assignment (ToDo.allocated_to → User) fails on the name. `user` is the
    // account they actually log in as, so My queue resolves correctly too.
    .map((a: any) => ({ name: a.user || a.name, label: a.agent_name || a.name }))
    .filter((a) => !q || a.label.toLowerCase().includes(q) || a.name.toLowerCase().includes(q));
});

function finishAssigned(agent: { name: string; label: string }) {
  optimisticAssignee.value = agent;
  toast.success(__("Assigned to {0}").replace("{0}", agent.label));
  assignees?.value?.reload?.();
  activities?.value?.reload?.();
}

// Routing to an approver moves the ticket to "Pending Approval" so it leaves
// Nedra's All Open working queue and lands in the approval queue. Self-assign
// (keeping it to work) does NOT change the status. Non-fatal: the assignment has
// already succeeded, so a failed status write just leaves the old status.
function setPendingApproval() {
  if (!props.ticket?.name) return;
  if (ticketRes?.value?.setValue) {
    ticketRes.value.setValue.submit({ status: "Pending Approval" });
  } else {
    call("frappe.client.set_value", {
      doctype: "HD Ticket",
      name: props.ticket.name,
      fieldname: { status: "Pending Approval" },
    }).catch(() => {});
  }
}

async function assignOne(agent: { name: string; label: string }) {
  if (!props.ticket?.name) return;
  assignOpen.value = false;
  const toOther = agent.name !== auth.userId;
  try {
    await call("frappe.desk.form.assign_to.add", {
      doctype: "HD Ticket",
      name: props.ticket.name,
      assign_to: [agent.name],
      // Email the assignee (from ap@, an allowed sender — the send is queued
      // async, so it never blocks the assignment). Skip emailing yourself.
      notify: toOther ? 1 : 0,
    });
    if (toOther) setPendingApproval();
    finishAssigned(agent);
  } catch (e) {
    // Belt-and-suspenders: the assignment persists before the notification step,
    // so if it actually landed, treat as success even if the notify errored.
    try {
      await assignees?.value?.reload?.();
    } catch {}
    if ((assignees?.value?.data || []).some((a: any) => a.name === agent.name)) {
      if (toOther) setPendingApproval();
      finishAssigned(agent);
    } else {
      toast.error(__("Couldn't assign. Try again."));
    }
  }
}
</script>
