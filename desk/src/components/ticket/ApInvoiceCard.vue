<template>
  <!-- AP invoice working card (mobile + desktop ticket detail). Renders only for
       AP tickets (the ap_vendor field is present); on IT/HR it renders nothing.
       Park is READ-ONLY here — it's edited on the Property field in Details; this
       card watches that field and rewrites the Intacct filename to match. Also hosts
       the invoice-verify actions: download-pre-named + mark-verified-and-assign. -->
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

      <!-- Actions -->
      <div class="mt-3 flex flex-col gap-2">
      <!-- Download the invoice already named for Intacct (same-origin: the browser
           saves it with this name, so no manual rename). Solid-blue primary CTA —
           this is the action Nedra takes on every invoice. -->
      <a
        v-if="invoiceUrl"
        :href="invoiceUrl"
        :download="downloadName || undefined"
        class="flex w-full items-center justify-center gap-2 rounded-lg py-2 text-base-medium text-white"
        style="background-color: #2563eb"
      >
        <LucideDownload class="size-4" />
        {{ __("Download for Intacct") }}
      </a>

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

      <!-- Verify — decoupled from assign. Explicit "Click to mark verified" label:
           a plain "Mark verified" read as an already-done status at a glance.
           Becomes the "Verified by …" pill once stamped. -->
      <div
        v-if="isVerified"
        class="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm"
        style="background-color: #f0fdf4; color: #15803d"
      >
        <LucideCircleCheck class="size-4 shrink-0" />
        <span class="truncate">{{ verifiedLabel }}</span>
      </div>
      <button
        v-else
        class="flex w-full items-center justify-center gap-2 rounded-lg border py-2 text-base-medium disabled:opacity-60"
        style="border-color: #16a34a; color: #15803d"
        :disabled="verifying"
        @click="markVerified()"
      >
        <LucideCheck class="size-4" />
        {{ verifying ? __("Saving…") : __("Click to mark verified") }}
      </button>

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

      <!-- View the invoice PDF (mobile only — jumps to the Emails tab where
           attachments live; on desktop the Invoice tab already shows it). -->
      <button
        v-if="isMobileView"
        class="flex w-full items-center justify-center gap-2 rounded-lg border border-outline-gray-2 py-2 text-base-medium text-ink-gray-8 active:bg-surface-gray-2"
        @click="$emit('view-pdf')"
      >
        <LucideFileText class="size-4" />
        {{ __("View invoice") }}
      </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { parkColor, parkLabel } from "@/config/parks";
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
import { computed, inject, ref, watch } from "vue";
import { useIsAp } from "@/composables/useIsAp";
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

// The Intacct filename shown/copied ALWAYS reflects the current park (edited on
// the Property field): swap the stored name's first (park) token to the current
// pyek_property. Purely COMPUTED — NO write — so it never races the Property
// field's own save.
const filename = computed(() => {
  const stored = storedFilename.value;
  if (!stored) return "";
  const code = props.ticket?.pyek_property;
  if (!code || !stored.includes("_")) return stored;
  return code + stored.slice(stored.indexOf("_"));
});
// Download needs ONE clean name: multi-invoice emails store a joined
// "name1 ; name2", so take the primary (first) segment before swapping the park.
const downloadName = computed(() => {
  const first = (storedFilename.value || "").split(" ; ")[0].trim();
  if (!first) return "";
  const code = props.ticket?.pyek_property;
  if (!code || !first.includes("_")) return first;
  return code + first.slice(first.indexOf("_"));
});

// Exact attachment the fields were read from (for the download link).
const invoiceUrl = computed(() => extra.data?.ap_invoice_file || "");

const copied = ref(false);
function copyFilename() {
  if (!filename.value || !navigator.clipboard) return;
  navigator.clipboard.writeText(filename.value);
  copied.value = true;
  setTimeout(() => (copied.value = false), 1400);
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
  const who = (localVerifiedBy.value || "").split("@")[0];
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

async function assignOne(agent: { name: string; label: string }) {
  if (!props.ticket?.name) return;
  assignOpen.value = false;
  try {
    await call("frappe.desk.form.assign_to.add", {
      doctype: "HD Ticket",
      name: props.ticket.name,
      assign_to: [agent.name],
      // Email the assignee (from ap@, an allowed sender — the send is queued
      // async, so it never blocks the assignment). Skip emailing yourself.
      notify: agent.name === auth.userId ? 0 : 1,
    });
    finishAssigned(agent);
  } catch (e) {
    // Belt-and-suspenders: the assignment persists before the notification step,
    // so if it actually landed, treat as success even if the notify errored.
    try {
      await assignees?.value?.reload?.();
    } catch {}
    if ((assignees?.value?.data || []).some((a: any) => a.name === agent.name)) {
      finishAssigned(agent);
    } else {
      toast.error(__("Couldn't assign. Try again."));
    }
  }
}
</script>
