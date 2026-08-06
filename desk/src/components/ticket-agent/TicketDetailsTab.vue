<template>
  <div class="flex h-full flex-col">
    <div class="shrink-0 px-4 pb-4 flex flex-col">
      <!-- User avatar with buttons -->
      <TicketContact />
      <!-- Core Fields -->
      <div class="mt-4">
        <div
          v-for="(section, index) in coreFields"
          :key="index"
          :class="
            section.group ? 'flex gap-2 items-start max-w-full mb-3' : 'mb-3'
          "
        >
          <template v-for="field in section.fields">
            <Link
              v-if="field.visible"
              :key="field.fieldname"
              :ref="(el) => setFieldRef(field.fieldname, el)"
              class="form-control-core"
              :id="field.fieldname"
              :class="section.group ? 'flex-1 min-w-0' : 'w-full'"
              :page-length="10"
              :label="field.label"
              :placeholder="field.placeholder"
              :doctype="field.doctype"
              :modelValue="field.value"
              :required="field.required"
              @update:model-value="
              (val:string) => handleFieldUpdate(field.fieldname, val,true)
            "
            />
          </template>
        </div>

        <!-- Assignee component -->
        <AssignTo />
      </div>
    </div>

    <!-- Scrollable sections: AI Assist + Ticket Info + Recent / Similar Tickets -->
    <div
      class="border-t flex-1 min-h-0 overflow-y-auto divide-y-[1px]"
      v-if="hasAI || Boolean(customFields.length) || showRecentSimilarTickets"
    >
      <!-- AI Assist (enricher output, read-only) -->
      <div v-if="hasAI">
        <Section label="AI Assist" v-model:opened="openedSections.aiAssist">
          <template #header="{ opened, toggle }">
            <div
              class="flex gap-2.5 items-center justify-between sticky top-0 bg-surface-base z-10 px-4 py-4 cursor-pointer"
              @click="toggle"
            >
              <span class="flex items-center gap-2">
                <span
                  class="grid place-items-center size-5 rounded bg-surface-gray-3 text-ink-gray-7"
                >
                  <LucideSparkles class="size-3" />
                </span>
                <span class="text-ink-gray-8 text-base-semibold select-none">
                  {{ __("AI Assist") }}
                </span>
              </span>
              <LucideChevronRight
                class="size-4 text-ink-gray-6"
                :class="{ 'rotate-90': opened }"
              />
            </div>
          </template>
          <div class="px-4 pb-4 space-y-3">
            <p
              v-if="ai.summary"
              class="text-sm text-ink-gray-7 leading-relaxed"
            >
              {{ ai.summary }}
            </p>
            <div class="space-y-1.5" v-if="aiFields.length">
              <div
                v-for="row in aiFields"
                :key="row.key"
                class="flex items-center gap-2 text-sm"
              >
                <span class="w-16 shrink-0 text-ink-gray-5">{{ row.label }}</span>
                <span
                  v-if="row.color"
                  class="inline-flex items-center gap-1.5 font-medium text-ink-gray-8 min-w-0"
                >
                  <span
                    class="size-2 rounded-full shrink-0"
                    :style="{ backgroundColor: row.color }"
                  />
                  <span class="truncate">{{ row.value }}</span>
                </span>
                <span v-else class="font-medium text-ink-gray-8 truncate">
                  {{ row.value }}
                </span>
              </div>
            </div>

            <!-- Build sheet (POS request types, Phase 2) -->
            <div
              v-if="buildSheet && buildSheet.fields.length"
              class="border-t border-outline-gray-1 pt-3 space-y-1.5"
            >
              <p
                class="text-xs font-semibold uppercase tracking-wide text-ink-gray-5"
              >
                {{ __("Build sheet") }}
              </p>
              <div
                v-for="(f, i) in buildSheet.fields"
                :key="i"
                class="flex items-start gap-2 text-sm"
              >
                <span class="w-24 shrink-0 text-ink-gray-5">{{ f.label }}</span>
                <span class="font-medium text-ink-gray-8 min-w-0 break-words">
                  {{ f.value }}
                </span>
              </div>
              <div
                v-if="buildSheet.due_date"
                class="flex items-center gap-2 text-sm"
              >
                <span class="w-24 shrink-0 text-ink-gray-5">{{ __("Due") }}</span>
                <span class="font-medium text-ink-gray-8">
                  {{ formatDate(buildSheet.due_date) }}
                </span>
                <span
                  v-if="buildSheet.urgency === 'high'"
                  class="text-xs px-1.5 py-0.5 rounded bg-surface-red-2 text-ink-red-6 font-medium"
                >
                  {{ __("Urgent") }}
                </span>
              </div>
            </div>

            <!-- IT assist: the agent's checklist for this ticket (Phase 3a/3c) -->
            <div
              v-if="itAssist?.steps?.length"
              class="border-t border-outline-gray-1 pt-3 space-y-2"
            >
              <div class="flex items-center justify-between gap-2">
                <p
                  class="text-xs font-semibold uppercase tracking-wide text-ink-gray-5"
                >
                  {{ __("Suggested steps") }}
                </p>
                <span
                  v-if="itAssist.urgency === 'high'"
                  class="text-xs px-1.5 py-0.5 rounded bg-surface-red-2 text-ink-red-6 font-medium"
                >
                  {{ __("Urgent") }}
                </span>
              </div>
              <ol class="space-y-1.5">
                <li
                  v-for="(step, i) in itAssist.steps"
                  :key="i"
                  class="flex items-start gap-2 text-sm"
                >
                  <span
                    class="grid place-items-center size-4 shrink-0 mt-px rounded-full bg-surface-gray-3 text-ink-gray-6 text-xs"
                  >
                    {{ i + 1 }}
                  </span>
                  <span class="text-ink-gray-7 min-w-0 break-words">
                    {{ step }}
                  </span>
                </li>
              </ol>
              <div
                v-if="itAssist.due_date"
                class="flex items-center gap-2 text-sm"
              >
                <span class="w-24 shrink-0 text-ink-gray-5">{{ __("By") }}</span>
                <span class="font-medium text-ink-gray-8">
                  {{ formatDate(itAssist.due_date) }}
                </span>
              </div>
            </div>

            <!-- IT assist: the access change being asked for -->
            <div
              v-if="accessRows.length"
              class="border-t border-outline-gray-1 pt-3 space-y-1.5"
            >
              <p
                class="text-xs font-semibold uppercase tracking-wide text-ink-gray-5"
              >
                {{ __("Access request") }}
              </p>
              <div
                v-for="row in accessRows"
                :key="row.key"
                class="flex items-start gap-2 text-sm"
              >
                <span class="w-24 shrink-0 text-ink-gray-5">{{ row.label }}</span>
                <span class="font-medium text-ink-gray-8 min-w-0 break-words">
                  {{ row.value }}
                </span>
              </div>
            </div>

            <!-- Completeness (both branches) -->
            <div
              v-if="missing.items.length"
              class="flex items-start gap-2 rounded bg-surface-amber-1 px-2.5 py-2 text-sm"
            >
              <LucideTriangleAlert
                class="size-4 shrink-0 text-ink-amber-6 mt-px"
              />
              <span class="text-ink-gray-7 min-w-0">
                <span class="font-medium text-ink-gray-8"
                  >{{ __("Missing") }}:</span
                >
                <template v-if="missing.inline">
                  {{ missing.items.join(", ") }} — {{ missing.hint }}
                </template>
                <template v-else>
                  {{ missing.hint }}
                  <span class="mt-1 block space-y-0.5">
                    <span
                      v-for="(item, i) in missing.items"
                      :key="i"
                      class="block break-words"
                    >
                      • {{ item }}
                    </span>
                  </span>
                </template>
              </span>
            </div>

            <!-- Buy-ticket artifact -->
            <div v-if="artifactUrls.length" class="space-y-1">
              <p
                class="text-xs font-semibold uppercase tracking-wide text-ink-gray-5"
              >
                {{ __("Buy-ticket link") }}
              </p>
              <a
                v-for="(url, i) in artifactUrls"
                :key="i"
                :href="url"
                target="_blank"
                rel="noopener"
                class="block text-sm text-ink-blue-5 hover:underline break-all"
              >
                {{ url }}
              </a>
            </div>

            <!-- Relevant internal SOPs (Phase 4b, agent-only from the backend) -->
            <div
              v-if="kbMatches.length"
              class="border-t border-outline-gray-1 pt-3 space-y-1.5"
            >
              <p
                class="text-xs font-semibold uppercase tracking-wide text-ink-gray-5"
              >
                {{ __("Relevant SOPs") }}
              </p>
              <router-link
                v-for="article in kbMatches"
                :key="article.name"
                :to="{ name: 'Article', params: { articleId: article.name } }"
                class="flex items-start gap-2 text-sm group"
              >
                <LucideBookOpen
                  class="size-4 shrink-0 mt-0.5 text-ink-gray-5"
                />
                <span class="min-w-0">
                  <span
                    class="text-ink-blue-5 group-hover:underline break-words"
                  >
                    {{ article.title }}
                  </span>
                  <span
                    v-if="article.category"
                    class="ml-1.5 text-xs text-ink-gray-5"
                  >
                    {{ article.category }}
                  </span>
                </span>
              </router-link>
            </div>

            <!-- Suggested reply (lazy, Phase 2c/3c — POS and IT) -->
            <div
              v-if="buildSheet || itAssist"
              class="border-t border-outline-gray-1 pt-3 space-y-2"
            >
              <div class="flex items-center justify-between">
                <span
                  class="text-xs font-semibold uppercase tracking-wide text-ink-gray-5"
                >
                  {{ __("Suggested reply") }}
                </span>
                <Button
                  v-if="!replyDraft"
                  :label="__('Generate')"
                  variant="subtle"
                  @click="generateReply"
                />
              </div>
              <template v-if="replyDraft">
                <div
                  class="rounded border border-outline-gray-2 bg-surface-gray-1 p-2.5 text-sm text-ink-gray-8 whitespace-pre-wrap"
                >
                  {{ replyDraft }}
                </div>
                <Button
                  :label="replyCopied ? __('Copied') : __('Copy reply')"
                  variant="subtle"
                  @click="copyReply"
                />
              </template>
            </div>
          </div>
        </Section>
      </div>

      <!-- Ticket Info (custom fields) -->
      <div v-if="Boolean(customFields.length)">
        <Section label="Ticket Info" v-model:opened="openedSections.ticketInfo">
          <template #header="{ opened, toggle }">
            <div
              class="flex gap-2.5 items-center justify-between sticky top-0 bg-surface-base z-10 px-4 py-4 cursor-pointer"
              @click="toggle"
            >
              <span class="text-ink-gray-8 text-base-semibold select-none">
                {{ __("Ticket Info") }}
              </span>
              <LucideChevronRight
                class="size-4 text-ink-gray-6"
                :class="{ 'rotate-90': opened }"
              />
            </div>
          </template>
          <div
            class="space-y-1.5 px-4 mb-2 mt-0.5"
            v-if="Boolean(customFields.length)"
          >
            <template v-for="field in customFields">
              <TicketField
                v-if="field.visible"
                :key="field.fieldname"
                :field="field"
                :value="field.value"
                @change="
                  ({ fieldname, value }) => handleFieldUpdate(fieldname, value)
                "
              />
            </template>
          </div>
        </Section>
      </div>

      <!-- Recent / Similar Tickets -->
      <template v-if="showRecentSimilarTickets">
        <div v-for="section in sections" :key="section.label">
          <Section
            :label="section.label"
            :hideLabel="section.hideLabel"
            v-model:opened="openedSections[section.key]"
          >
            <template #header="{ opened, toggle }">
              <div
                class="flex gap-2.5 items-center justify-between sticky top-0 bg-surface-base z-10 px-4 py-4 cursor-pointer"
                @click="toggle"
              >
                <Tooltip :text="section.tooltipMessage">
                  <span class="text-ink-gray-8 text-base-semibold select-none">
                    {{ __(section.label) }}
                  </span>
                </Tooltip>
                <LucideChevronRight
                  class="size-4 text-ink-gray-6"
                  :class="{ 'rotate-90': opened }"
                />
              </div>
            </template>
            <ul class="pt-0 px-4 divide-y divide-outline-gray-1 pb-4">
              <li
                v-for="t in section.tickets"
                :key="t.name"
                @click="openTicket(t.name)"
              >
                <div
                  class="-mx-2 px-2 py-3 cursor-pointer rounded hover:bg-surface-gray-2 transition-colors"
                >
                  <p class="text-sm font-base text-ink-gray-9 truncate mb-2">
                    {{ t.subject }}
                  </p>
                  <div class="flex items-center justify-between gap-2">
                    <p class="text-sm text-ink-gray-5 shrink-0">
                      {{ formatDate(t.creation as string) + " · " }}
                      <span class="">{{ "#" + t.name }}</span>
                    </p>
                    <span
                      class="text-xs px-2 py-0.5 font-base shrink-0 rounded-sm"
                      :class="getStatusColor(t.status as string)"
                    >
                      {{ t.status }}
                    </span>
                  </div>
                </div>
              </li>
            </ul>
          </Section>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Link } from "@/components";
import { parseField } from "@/composables/formCustomisation";
import { useNotifyTicketUpdate } from "@/composables/realtime";
import { useShortcut } from "@/composables/shortcuts";
import { getMeta } from "@/stores/meta";
import { useTicketStatusStore } from "@/stores/ticketStatus";
import {
  ActivitiesSymbol,
  AssigneeSymbol,
  CustomizationSymbol,
  FieldValue,
  RecentSimilarTicketsSymbol,
  TicketSymbol,
} from "@/types";
import { useStorage } from "@vueuse/core";
import { Button, dayjs, Tooltip } from "frappe-ui";
import { computed, inject, ref } from "vue";
import LucideBookOpen from "~icons/lucide/book-open";
import LucideChevronRight from "~icons/lucide/chevron-right";
import LucideSparkles from "~icons/lucide/sparkles";
import LucideTriangleAlert from "~icons/lucide/triangle-alert";
import { parkColor, parkLabel } from "@/config/parks";
import Section from "../Section.vue";
import TicketField from "../TicketField.vue";
import AssignTo from "./AssignTo.vue";
import TicketContact from "./TicketContact.vue";

const ticket = inject(TicketSymbol)!;
const assignees = inject(AssigneeSymbol)!;
const customizations = inject(CustomizationSymbol)!;
const activities = inject(ActivitiesSymbol)!;
const recentSimilarTickets = inject(RecentSimilarTicketsSymbol)!;
const { getFields, getField } = getMeta("HD Ticket");
const { notifyTicketUpdate } = useNotifyTicketUpdate(ticket.value?.name);

const dateFormat = window.date_format;
const { getStatus, colorMap } = useTicketStatusStore();

// ticket_type, priority, customer, agent_group
const coreFields = computed(() => {
  // TODO: to confirm whether customizations should apply to core fields as well
  const fieldsMeta = getFields();
  if (!fieldsMeta || fieldsMeta.length === 0) {
    return [];
  }
  const _coreFields = [
    { group: true, fields: [getField("ticket_type"), getField("priority")] },
    { group: false, fields: [getField("customer")] },
    { group: true, fields: [getField("agent_group")] },
  ];

  _coreFields.forEach((section) => {
    section.fields = section.fields.map((f) => {
      f = parseField(f, ticket.value.doc);

      // cant handle required depends on as we directly set the value in DB on change
      f["required"] = f.reqd;
      f["ref"] = f.fieldname;

      f = getFieldInFormat(f, f);
      f["visible"] = true;
      return f;
    });
  });
  return _coreFields;
});

const customFields = computed(() => {
  const fieldsMeta = getFields();
  if (!fieldsMeta || fieldsMeta.length === 0) {
    return [];
  }

  if (!customizations.value.data || customizations.value.loading) return [];
  let customFields = customizations.value.data?.custom_fields || [];
  const _coreFields = [
    "ticket_type",
    "priority",
    "customer",
    "agent_group",
    "subject",
    "status",
    // Rendered by the AI Assist panel, not as a raw JSON field in Ticket Info.
    "pyek_suggestions",
  ];
  customFields = customFields.filter((f) => !_coreFields.includes(f.fieldname));
  let _customFields = customFields
    .map((f) => {
      let fieldMeta = getField(f.fieldname);
      if (!fieldMeta) return null;

      fieldMeta = parseField(fieldMeta, ticket.value.doc);
      // cant handle required depends on as we directly set the value in DB
      fieldMeta["required"] = fieldMeta.reqd || f.required;

      return getFieldInFormat(f, fieldMeta);
    })
    .filter(Boolean);
  return _customFields;
});

const openedSections = useStorage(
  "openedSections",
  {
    aiAssist: true,
    ticketInfo: false,
    recentTickets: false,
    similarTickets: false,
  },
  localStorage,
  { mergeDefaults: true }
);

// AI Assist: the enricher-written fields, surfaced read-only (Phase 1). Wires the
// otherwise-orphaned pyek_summary and shows request type / park / category /
// system / due alongside it. Values come straight off the ticket doc.
const ai = computed(() => {
  const d = ticket.value?.doc || {};
  return {
    summary: d.pyek_summary || "",
    requestType: d.pyek_request_type || "",
    park: d.pyek_property || "",
    category: d.pyek_category || "",
    system: d.pyek_system || "",
    dueDate: d.pyek_requested_due_date || "",
  };
});

// pyek_suggestions holds one key per enricher branch: build_sheet for POS request
// types, it_assist for IT ones. Parse once; a ticket only ever has one of them.
const suggestions = computed(() => {
  const raw = ticket.value?.doc?.pyek_suggestions;
  if (!raw) return null;
  try {
    return JSON.parse(raw) || null;
  } catch {
    return null;
  }
});

// Phase 2: the POS build sheet.
const buildSheet = computed(() => suggestions.value?.build_sheet || null);

// Phase 3a: the IT action checklist — steps, the access request, what's missing.
const itAssist = computed(() => suggestions.value?.it_assist || null);

// Phase 4b: internal SOP articles matching this ticket. The backend gates these on
// is_agent() and they include Draft articles, so this only ever renders for agents.
// Returns nothing when no SOP is a genuine match, which is intended — a wrong
// suggestion is worse than none.
const kbMatches = computed(
  () => recentSimilarTickets.value?.data?.kb_matches || []
);

// Access-request rows, shown only for the parts the enricher could fill.
const accessRows = computed(() => {
  const a = itAssist.value?.access_request;
  if (!a) return [];
  return [
    { key: "action", label: __("Action"), value: a.action },
    { key: "user", label: __("User"), value: a.user },
    { key: "system", label: __("System"), value: a.system },
    { key: "scope", label: __("Scope"), value: a.scope },
  ].filter((r) => Boolean(r.value));
});

const artifactUrls = computed(() =>
  String(buildSheet.value?.artifact || "")
    .split(/\s+/)
    .map((u) => u.trim())
    .filter((u) => u.startsWith("http"))
);

const hasAI = computed(() => {
  const a = ai.value;
  return (
    Boolean(
      a.summary || a.requestType || a.park || a.category || a.system || a.dueDate
    ) ||
    Boolean(buildSheet.value) ||
    Boolean(itAssist.value) ||
    Boolean(kbMatches.value.length)
  );
});

// Completeness flag, shared by both branches. The POS build sheet returns short
// field labels ("quantity", "year") which read best on one line; the IT branch
// returns whole questions, which need their own lines — so pick by item length
// rather than hard-coding a layout per branch.
const missing = computed(() => {
  const raw = (buildSheet.value || itAssist.value)?.missing;
  const items: string[] = Array.isArray(raw) ? raw : [];
  return {
    items,
    inline: items.every((i) => i.length < 40),
    hint: buildSheet.value
      ? __("confirm before building.")
      : __("ask the requester."),
  };
});

const aiFields = computed(() => {
  const a = ai.value;
  const rows: { key: string; label: string; value: string; color?: string }[] = [];
  if (a.requestType)
    rows.push({ key: "request", label: __("Request"), value: a.requestType });
  if (a.park) {
    const label = parkLabel(a.park);
    rows.push({ key: "park", label: __("Park"), value: label, color: parkColor(label) });
  }
  if (a.category)
    rows.push({ key: "category", label: __("Category"), value: a.category });
  if (a.system)
    rows.push({ key: "system", label: __("System"), value: a.system });
  if (a.dueDate)
    rows.push({ key: "due", label: __("Due"), value: formatDate(a.dueDate) });
  return rows;
});

// Phase 2c / 3c: compose a suggested reply locally — buy-ticket links or a "here's
// what was set up" confirmation for POS, a "here's what I'm doing" for IT — and offer
// copy. Deliberately no AI call: this is assembled from what the enricher already
// wrote, so opening a ticket and clicking Generate costs nothing.
const replyDraft = ref("");
const replyCopied = ref(false);

function generateReply() {
  const bs = buildSheet.value;
  const it = itAssist.value;
  if (!bs && !it) return;
  const lines = ["Hi,", ""];
  if (bs) {
    if (artifactUrls.value.length) {
      lines.push(
        artifactUrls.value.length > 1 ? "Here are the links:" : "Here's the link:"
      );
      artifactUrls.value.forEach((u) => lines.push(u));
    } else if (bs.fields?.length) {
      lines.push("Done — here's what was set up:");
      bs.fields.forEach((f) => lines.push(`• ${f.label}: ${f.value}`));
    }
  } else if (it) {
    // Deliberately does NOT list it.steps: those are the agent's internal checklist
    // (revoking tokens, confirming approval with a system owner) and don't belong in
    // a requester-facing reply. State the outcome instead.
    const a = it.access_request;
    if (a?.system) {
      const who = a.user ? ` for ${a.user}` : "";
      const scope = a.scope ? ` (${a.scope})` : "";
      lines.push(`I'm taking care of the ${a.system} access${who}${scope}.`);
    } else {
      lines.push("Thanks for flagging this — I'm looking into it now.");
    }
  }
  const missingItems: string[] = (bs || it)?.missing || [];
  if (missingItems.length) {
    lines.push("");
    lines.push(
      `Before I can finish, could you confirm: ${missingItems.join("; ")}?`
    );
  }
  lines.push("", "Thanks!");
  replyDraft.value = lines.join("\n");
}

function copyReply() {
  if (!navigator.clipboard) return;
  navigator.clipboard.writeText(replyDraft.value).then(() => {
    replyCopied.value = true;
    setTimeout(() => (replyCopied.value = false), 1500);
  });
}

const sections = computed(() => {
  if (recentSimilarTickets.value.loading || !recentSimilarTickets.value.data) {
    return [];
  }
  const recentTickets = recentSimilarTickets.value?.data?.recent_tickets || [];
  const similarTickets =
    recentSimilarTickets.value?.data?.similar_tickets || [];
  const _sections = [];
  if (recentTickets.length) {
    _sections.push({
      key: "recentTickets" as const,
      label: "Recent Tickets",
      tooltipMessage: "Tickets recently raised by this contact/customer",
      hideLabel: false,
      tickets: recentTickets,
    });
  }
  if (similarTickets.length) {
    _sections.push({
      key: "similarTickets" as const,
      label: "Similar Tickets",
      tooltipMessage: "Tickets with similar queries",
      hideLabel: false,
      tickets: similarTickets,
    });
  }
  return _sections;
});

function getStatusColor(status: string) {
  const { color } = getStatus(status) ?? {};
  return colorMap[color] ?? colorMap["Default"];
}

function formatDate(date: string) {
  return dayjs(date).format(dateFormat.toUpperCase());
}
function openTicket(name: string) {
  let url = window.location.origin + "/helpdesk/tickets/" + name;
  window.open(url, "_blank");
}

function getFieldInFormat(fieldTemplate, fieldMeta) {
  return {
    label: fieldMeta?.label || fieldTemplate.fieldname,
    value: ticket.value.doc[fieldTemplate.fieldname],
    fieldtype: fieldMeta?.fieldtype,
    doctype: fieldMeta?.options || "",
    options: fieldMeta?.options || "",
    placeholder:
      fieldTemplate.placeholder ||
      `Enter ${fieldMeta?.label || fieldTemplate.fieldname}`,
    readonly: Boolean(fieldMeta.read_only),
    disabled: Boolean(fieldMeta.read_only),
    url_method: fieldTemplate.url_method || "",
    fieldname: fieldTemplate.fieldname,
    required: fieldTemplate.required || fieldMeta?.required || false,
    visible:
      fieldMeta.display_via_depends_on &&
      !fieldMeta.hidden &&
      (!!ticket.value.doc[fieldTemplate.fieldname] || !fieldMeta.read_only),
  };
}

const normalize = (v: string | FieldValue) =>
  v === null || v === undefined ? "" : v;

function handleFieldUpdate(
  fieldname: string,
  value: FieldValue,
  isCoreFieldUpdated = false
) {
  if (normalize(ticket.value.doc[fieldname]) == normalize(value)) return;
  if (isCoreFieldUpdated) {
    const label = getField(fieldname)?.label || fieldname;
    notifyTicketUpdate(label, value as string);
  }
  ticket.value.setValue.submit(
    { [fieldname]: value },
    {
      onSuccess: () => {
        // TODO: emit the event for notification to listeners
        if (fieldname === "agent_group") {
          assignees.value.reload();
        }
        activities.value.reload();
      },
    }

    //show error toast
  );
}

const fieldRefs = ref<Record<string, any>>({});

const setFieldRef = (fieldname: string, el: any) => {
  if (el) {
    fieldRefs.value[fieldname] = el;
  }
};

const showRecentSimilarTickets = computed(() => {
  return (
    !recentSimilarTickets.value.loading &&
    (recentSimilarTickets.value?.data?.recent_tickets?.length ||
      recentSimilarTickets.value?.data?.similar_tickets?.length)
  );
});

useShortcut("t", () => {
  fieldRefs.value?.ticket_type?.$el?.querySelector("button")?.click();
});

useShortcut("p", () => {
  fieldRefs.value?.priority?.$el?.querySelector("button")?.click();
});

useShortcut({ key: "t", shift: true }, () => {
  fieldRefs.value?.agent_group?.$el?.querySelector("button")?.click();
});
</script>

<style scoped>
:deep(.form-control-core button) {
  @apply text-base rounded h-7 py-1.5 border border-outline-gray-2 bg-surface-base placeholder-ink-gray-4 hover:border-outline-gray-3 hover:shadow-sm focus:bg-surface-base focus:border-outline-gray-4 focus:shadow-sm focus:ring-0 focus-visible:ring-0 text-ink-gray-8 transition-colors w-full dark:[color-scheme:dark];
}
:deep(.form-control-core button > div) {
  @apply truncate;
}

:deep(.form-control-core div) {
  width: 100%;
  display: flex;
}
</style>
