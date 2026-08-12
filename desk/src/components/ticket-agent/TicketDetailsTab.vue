<template>
  <!-- A rail of cards rather than full-width blocks divided by hairlines. The
       contact and the core fields used to live in a fixed block above the scroll
       area, with the rest of the ticket's fields in a separate collapsed section
       further down; they are one card now, so there is a single properties
       surface instead of two. The trade-off is that contact and assignee scroll
       with everything else, which the shorter panel makes affordable. -->
  <div class="flex h-full flex-col bg-surface-gray-1">
    <div class="flex-1 min-h-0 overflow-y-auto p-2.5 space-y-2.5">
      <!-- Details: the contact plus every editable field, in one rhythm -->
      <div class="rounded-lg border border-outline-gray-1 bg-surface-base shadow-sm">
        <Section label="Details" v-model:opened="openedSections.details">
          <template #header="{ opened, toggle }">
            <div
              class="flex items-center gap-2 px-3 py-2.5 cursor-pointer"
              @click="toggle"
            >
              <span
                class="grid place-items-center size-5 rounded bg-surface-gray-2 text-ink-gray-6"
              >
                <LucideInfo class="size-3" />
              </span>
              <span class="text-base-semibold text-ink-gray-8 select-none">
                {{ __("Details") }}
              </span>
              <LucideChevronRight
                class="ml-auto size-4 shrink-0 text-ink-gray-5"
                :class="{ 'rotate-90': opened }"
              />
            </div>
          </template>
          <div class="px-3 pb-3">
            <TicketContact />
            <div class="mt-2 border-t border-outline-gray-1 pt-2 space-y-1">
              <!-- Assignee stays its own component — it carries the agent search,
                   avatars and availability dots — but wears the same row as the
                   fields, with its outline flattened to match. -->
              <div class="flex gap-2 items-center leading-5">
                <div
                  class="w-[106px] shrink-0 truncate text-base text-ink-gray-5"
                >
                  {{ __("Assignee") }}
                </div>
                <div
                  class="assignee-row -m-0.5 min-h-[28px] flex-1 overflow-hidden p-0.5 text-base"
                >
                  <AssignTo hideLabel />
                </div>
              </div>
              <!-- Choice fields read as pills rather than form text. Wrapped
                   rather than restyled inside TicketField: that component
                   renders every custom field everywhere, and its control must
                   stay editable. Same :deep() approach as .assignee-row. -->
              <template v-for="field in detailFields">
                <div
                  v-if="field.visible"
                  :key="field.fieldname"
                  :class="pillClass(field)"
                >
                <TicketField
                  :ref="(el) => setFieldRef(field.fieldname, el)"
                  :field="field"
                  :value="field.value"
                  @change="
                    ({ fieldname, value }) =>
                      handleFieldUpdate(
                        fieldname,
                        value,
                        CORE_FIELDS.includes(fieldname)
                      )
                  "
                />
                </div>
              </template>
            </div>
          </div>
        </Section>
      </div>

      <!-- AI Assist. Extracted into its own component so the mobile ticket
           screen can mount the SAME panel rather than a copy of it.
           See AiAssistPanel.vue. -->
      <AiAssistPanel />

      <!-- Recent / Similar Tickets -->
      <template v-if="showRecentSimilarTickets">
        <div
          v-for="section in sections"
          :key="section.label"
          class="rounded-lg border border-outline-gray-1 bg-surface-base shadow-sm"
        >
          <Section
            :label="section.label"
            :hideLabel="section.hideLabel"
            v-model:opened="openedSections[section.key]"
          >
            <template #header="{ opened, toggle }">
              <div
                class="flex gap-2.5 items-center justify-between px-3 py-2.5 cursor-pointer"
                @click="toggle"
              >
                <Tooltip :text="section.tooltipMessage">
                  <span class="flex items-center gap-2">
                    <span
                      class="grid place-items-center size-5 rounded bg-surface-gray-3 text-ink-gray-7"
                    >
                      <component :is="section.icon" class="size-3" />
                    </span>
                    <span class="text-base-semibold text-ink-gray-8 select-none">
                      {{ __(section.label) }}
                    </span>
                  </span>
                </Tooltip>
                <LucideChevronRight
                  class="size-4 text-ink-gray-6"
                  :class="{ 'rotate-90': opened }"
                />
              </div>
            </template>
            <ul class="px-3 pb-3 space-y-0.5">
              <li
                v-for="t in section.tickets"
                :key="t.name"
                @click="openTicket(t.name)"
              >
                <div
                  class="-mx-2 px-2 py-2.5 cursor-pointer rounded-md hover:bg-surface-gray-2 transition-colors"
                >
                  <p
                    class="text-sm font-medium text-ink-gray-8 truncate mb-1.5"
                  >
                    {{ t.subject }}
                  </p>
                  <div class="flex items-center justify-between gap-2">
                    <p class="text-xs text-ink-gray-5 shrink-0">
                      {{ formatDate(t.creation as string) }}
                      <span class="text-ink-gray-3 px-0.5">·</span>
                      <span>{{ "#" + t.name }}</span>
                    </p>
                    <span
                      class="text-xs px-2 py-0.5 font-medium shrink-0 rounded-sm"
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
import { dayjs, Tooltip } from "frappe-ui";
import { computed, inject, ref } from "vue";
import LucideChevronRight from "~icons/lucide/chevron-right";
import LucideClock from "~icons/lucide/clock";
import LucideInfo from "~icons/lucide/info";
import LucideSearch from "~icons/lucide/search";
import AiAssistPanel from "./AiAssistPanel.vue";
import Section from "../Section.vue";
import TicketField from "../TicketField.vue";

// Only Select/Link fields get the pill; free text and dates keep looking like
// inputs, because that is what they are.
const PILL_FIELDTYPES = ["Select", "Link"];

function pillClass(field: { fieldtype?: string; fieldname?: string; value?: any }) {
  if (!PILL_FIELDTYPES.includes(field.fieldtype) || !field.value) return null;
  if (field.fieldname === "priority") {
    if (field.value === "Urgent") return ["pill-field", "pill-urgent"];
    if (field.value === "High") return ["pill-field", "pill-high"];
  }
  return "pill-field";
}
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

// Priority and Team are HD Ticket's own fields rather than custom ones, so an edit
// to either is worth announcing to anyone else viewing the ticket.
const CORE_FIELDS = ["priority", "agent_group"];

// One list for the whole Details card: the two core fields first, then the custom
// fields. Both go through TicketField, which is what makes the card a single
// rhythm — priority and agent_group used to be the only two drawn as boxed
// controls with the label stacked above, while every field below them was already
// label-left with a borderless control.
const detailFields = computed(() => {
  const fieldsMeta = getFields();
  if (!fieldsMeta || fieldsMeta.length === 0) return [];
  const core = CORE_FIELDS.map((fieldname) => {
    let meta = getField(fieldname);
    if (!meta) return null;
    meta = parseField(meta, ticket.value.doc);
    meta["required"] = meta.reqd;
    const f = getFieldInFormat({ fieldname }, meta);
    // Always shown: an unset priority or team is exactly when you need the control.
    f.visible = true;
    return f;
  }).filter(Boolean);
  return [...core, ...customFields.value];
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
    // Both rendered by the AI Assist card: the suggestions JSON is never shown
    // raw, and the summary appears there in full rather than truncated here.
    "pyek_suggestions",
    "pyek_summary",
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

// The AI panel's fold state moved out with it, onto its own "aiPanelSections" key
// (AiAssistPanel.vue explains why it must NOT share this object: useStorage writes
// the whole thing back, so two components sharing one key clobber each other's
// values). The stale aiAssist/aiDetail/aiKb entries left in anyone's localStorage
// are harmless — useStorage just ignores keys it wasn't given a default for.
const openedSections = useStorage(
  "openedSections",
  {
    details: true,
    recentTickets: false,
    similarTickets: false,
  },
  localStorage,
  { mergeDefaults: true }
);

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
      icon: LucideClock,
      tickets: recentTickets,
    });
  }
  if (similarTickets.length) {
    _sections.push({
      key: "similarTickets" as const,
      label: "Similar Tickets",
      tooltipMessage: "Tickets with similar queries",
      hideLabel: false,
      icon: LucideSearch,
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

// No "t" shortcut for ticket_type any more — that field no longer renders here,
// so the binding would have been a silent no-op.
useShortcut("p", () => {
  fieldRefs.value?.priority?.$el?.querySelector("button")?.click();
});

useShortcut({ key: "t", shift: true }, () => {
  fieldRefs.value?.agent_group?.$el?.querySelector("button")?.click();
});
</script>

<style scoped>
/* The .form-control-core rules that used to live here are gone with the boxed
   Priority/Team controls — those fields render through TicketField now, which
   brings its own quiet styling.

   AssignTo draws an outline Button. Flatten it so the assignee row matches the
   field rows either side of it, and let the outline come back on hover, which is
   the same affordance TicketField uses for "this is editable". */
/* Pill treatment for choice fields. The control keeps its own click-to-edit
   behaviour; only the resting appearance changes, and only when it holds a
   value — an empty field stays a plain "Enter Category" prompt rather than an
   empty coloured capsule. */
:deep(.pill-field .form-control > button),
:deep(.pill-field .form-control button[aria-haspopup]) {
  border-radius: 9999px;
  background: var(--surface-gray-2);
  border-color: transparent;
  padding-left: 10px;
  padding-right: 10px;
}
:deep(.pill-field .form-control > button:hover),
:deep(.pill-field .form-control button[aria-haspopup]:hover) {
  background: var(--surface-gray-3);
}
:deep(.pill-urgent .form-control > button) {
  background: var(--surface-red-2);
  color: var(--ink-red-7);
}
:deep(.pill-high .form-control > button) {
  background: var(--surface-amber-2);
  color: var(--ink-amber-7);
}

:deep(.assignee-row button) {
  border-color: transparent;
  background: transparent;
  box-shadow: none;
}
:deep(.assignee-row button:hover) {
  border-color: var(--outline-gray-2);
  background: var(--surface-gray-1);
}
</style>
