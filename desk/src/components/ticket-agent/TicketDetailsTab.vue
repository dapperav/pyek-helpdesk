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
              <span class="text-base font-semibold text-ink-gray-8 select-none">
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
              <template v-for="field in detailFields">
                <TicketField
                  v-if="field.visible"
                  :key="field.fieldname"
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
              </template>
            </div>
          </div>
        </Section>
      </div>

      <!-- AI Assist (enricher output, read-only) -->
      <div
        v-if="hasAI"
        class="rounded-lg border border-outline-gray-1 bg-surface-base shadow-sm"
      >
        <Section label="AI Assist" v-model:opened="openedSections.aiAssist">
          <template #header="{ opened, toggle }">
            <div
              class="flex gap-2.5 items-center justify-between px-3 py-2.5 cursor-pointer"
              @click="toggle"
            >
              <span class="flex items-center gap-2">
                <span
                  class="grid place-items-center size-5 rounded bg-surface-gray-3 text-ink-gray-7"
                >
                  <LucideSparkles class="size-3" />
                </span>
                <span class="text-base font-semibold text-ink-gray-8 select-none">
                  {{ __("AI Assist") }}
                </span>
              </span>
              <LucideChevronRight
                class="size-4 text-ink-gray-6"
                :class="{ 'rotate-90': opened }"
              />
            </div>
          </template>
          <div class="px-3 pb-3">
            <!-- Identity + the re-run remedy, on one line. -->
            <div class="flex items-center gap-1.5 mb-2">
              <span
                v-if="identity.primary"
                class="inline-flex items-center rounded bg-surface-gray-3 px-1.5 py-0.5 text-xs font-semibold text-ink-gray-8 truncate max-w-[170px]"
              >
                {{ identity.primary }}
              </span>
              <span
                v-if="identity.park"
                class="inline-flex items-center gap-1.5 rounded border border-outline-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-7 shrink-0"
              >
                <span
                  class="size-1.5 rounded-full shrink-0"
                  :style="{ backgroundColor: identity.parkColor }"
                />
                {{ identity.park }}
              </span>
              <Tooltip
                v-if="rerunState === 'idle'"
                :text="
                  __(
                    'Re-run the AI on this ticket. Priority and category stay as you set them.'
                  )
                "
              >
                <button
                  type="button"
                  class="ml-auto grid size-6 shrink-0 place-items-center rounded border border-outline-gray-2 text-ink-gray-5 hover:bg-surface-gray-2 hover:text-ink-gray-8 transition-colors"
                  @click="rerunAI"
                >
                  <LucideRefreshCw class="size-3" />
                </button>
              </Tooltip>
              <Tooltip
                v-else
                :text="
                  __(
                    'Queued. The enricher picks this up on its next pass and the panel updates on its own.'
                  )
                "
              >
                <span
                  class="ml-auto grid size-6 shrink-0 place-items-center rounded bg-surface-gray-2 text-ink-gray-5"
                >
                  <LucideHourglass class="size-3" />
                </span>
              </Tooltip>
            </div>

            <!-- Clamped: the full text is in the ticket body a few inches left. -->
            <p
              v-if="ai.summary"
              ref="summaryEl"
              class="text-sm text-ink-gray-7 leading-normal"
              :class="{ 'line-clamp-2': !summaryExpanded }"
            >
              {{ ai.summary }}
            </p>
            <button
              v-if="ai.summary && (summaryOverflows || summaryExpanded)"
              type="button"
              class="mt-0.5 text-xs text-ink-blue-6 hover:underline"
              @click="summaryExpanded = !summaryExpanded"
            >
              {{ summaryExpanded ? __("less") : __("more") }}
            </button>

            <div
              v-if="dueLabel"
              class="flex items-center gap-1.5 mt-1.5 text-xs text-ink-gray-6"
            >
              <LucideCalendar class="size-3 shrink-0" />
              {{ __("Due") }}
              <span class="font-semibold text-ink-gray-8">{{ dueLabel }}</span>
            </div>

            <!-- The blocker. A coloured edge reads faster than a tinted box, and a
                 single short item goes inline rather than costing a heading plus a
                 list. Longer items stay foldable so they can't push the CTA down. -->
            <div
              v-if="missing.items.length"
              class="mt-2.5 rounded-r border-l-[3px] border-outline-amber-5 bg-surface-amber-1 px-2.5 py-1.5"
            >
              <button
                type="button"
                class="flex w-full items-start gap-2 text-left"
                :class="{ 'cursor-default': missing.inline }"
                @click="missing.inline || (missingOpen = !missingOpen)"
              >
                <LucideTriangleAlert
                  class="size-3.5 shrink-0 mt-0.5 text-ink-amber-6"
                />
                <span class="text-xs leading-snug text-ink-gray-8 min-w-0">
                  {{ missing.headline }}
                </span>
                <LucideChevronRight
                  v-if="!missing.inline"
                  class="ml-auto size-3.5 shrink-0 mt-0.5 text-ink-gray-5"
                  :class="{ 'rotate-90': missingOpen }"
                />
              </button>
              <ul
                v-if="!missing.inline"
                v-show="missingOpen"
                class="mt-1 pl-5 space-y-0.5"
              >
                <li
                  v-for="(item, i) in missing.items"
                  :key="i"
                  class="flex gap-1.5 text-xs leading-snug text-ink-gray-7"
                >
                  <span class="text-ink-gray-4 shrink-0">·</span>
                  <span class="min-w-0 break-words">{{ item }}</span>
                </li>
              </ul>
            </div>

            <!-- The job, folded by default. The count is what makes a folded strip
                 worth opening — a bare label isn't. -->
            <template v-if="jobKind">
              <button
                type="button"
                class="mt-2.5 flex w-full items-center gap-2 border-t border-outline-gray-1 pt-2 pb-1 text-left"
                @click="openedSections.aiDetail = !openedSections.aiDetail"
              >
                <LucideClipboardList
                  v-if="jobKind === 'pos'"
                  class="size-3.5 shrink-0 text-ink-gray-5"
                />
                <LucideListChecks
                  v-else
                  class="size-3.5 shrink-0 text-ink-gray-5"
                />
                <span
                  class="text-xs font-semibold uppercase tracking-wide text-ink-gray-6"
                >
                  {{ jobTitle }}
                </span>
                <span
                  class="rounded-full border px-1.5 text-[10px] font-bold tabular-nums"
                  :class="
                    jobCountActive
                      ? 'border-outline-blue-2 bg-surface-blue-1 text-ink-blue-6'
                      : 'border-outline-gray-2 bg-surface-gray-2 text-ink-gray-5'
                  "
                >
                  {{ jobCount }}
                </span>
                <span
                  v-if="urgent"
                  class="rounded bg-surface-red-2 px-1.5 text-[10px] font-bold uppercase tracking-wide text-ink-red-7"
                >
                  {{ __("Urgent") }}
                </span>
                <LucideChevronRight
                  class="ml-auto size-3.5 shrink-0 text-ink-gray-5"
                  :class="{ 'rotate-90': openedSections.aiDetail }"
                />
              </button>
              <div v-show="openedSections.aiDetail" class="pb-1">
                <dl
                  v-if="jobRows.length"
                  class="grid grid-cols-[88px_minmax(0,1fr)] gap-x-2 gap-y-1.5 items-baseline"
                >
                  <template v-for="row in jobRows" :key="row.key">
                    <dt class="text-xs text-ink-gray-5 leading-snug break-words">
                      {{ row.label }}
                    </dt>
                    <dd
                      class="text-xs font-medium text-ink-gray-8 leading-snug break-words"
                    >
                      {{ row.value }}
                    </dd>
                  </template>
                </dl>
                <ul
                  v-if="steps.length"
                  class="space-y-1.5"
                  :class="{ 'mt-2': jobRows.length }"
                >
                  <li v-for="(step, i) in steps" :key="i">
                    <button
                      type="button"
                      class="group flex w-full items-start gap-2 text-left"
                      :aria-pressed="isStepDone(i)"
                      @click="toggleStep(i)"
                    >
                      <span
                        class="grid place-items-center size-4 shrink-0 mt-px rounded-full text-[9px] font-bold tabular-nums transition-colors"
                        :class="
                          isStepDone(i)
                            ? 'bg-surface-green-2 text-ink-green-7'
                            : 'bg-surface-gray-3 text-ink-gray-6 group-hover:bg-surface-gray-4'
                        "
                      >
                        <LucideCheck v-if="isStepDone(i)" class="size-2.5" />
                        <template v-else>{{ i + 1 }}</template>
                      </span>
                      <span
                        class="text-xs leading-snug min-w-0 break-words"
                        :class="
                          isStepDone(i)
                            ? 'text-ink-gray-4 line-through'
                            : 'text-ink-gray-7'
                        "
                      >
                        {{ step }}
                      </span>
                    </button>
                  </li>
                </ul>
                <div
                  v-if="jobDate"
                  class="flex items-center gap-1.5 mt-2 text-xs text-ink-gray-5"
                >
                  <LucideCalendar class="size-3 shrink-0" />
                  {{ jobDateLabel }}
                  <span class="font-medium text-ink-gray-8">{{ jobDate }}</span>
                </div>
                <a
                  v-for="(url, i) in artifactUrls"
                  :key="i"
                  :href="url"
                  target="_blank"
                  rel="noopener"
                  class="flex items-start gap-1.5 mt-2 text-xs text-ink-blue-6 hover:underline"
                >
                  <LucideExternalLink class="size-3 shrink-0 mt-0.5" />
                  <span class="min-w-0 break-all">{{ url }}</span>
                </a>
              </div>
            </template>

            <!-- Retrieved, not inferred. One line each: the ref as a tag, the title
                 truncated. Three of these used to cost more than the job itself. -->
            <template v-if="kbLoaded">
              <button
                type="button"
                class="mt-1 flex w-full items-center gap-2 border-t border-outline-gray-1 pt-2 pb-1 text-left"
                @click="openedSections.aiKb = !openedSections.aiKb"
              >
                <LucideBookOpen class="size-3.5 shrink-0 text-ink-gray-5" />
                <span
                  class="text-xs font-semibold uppercase tracking-wide text-ink-gray-6"
                >
                  {{ __("Relevant SOPs") }}
                </span>
                <span
                  class="rounded-full border px-1.5 text-[10px] font-bold tabular-nums"
                  :class="
                    kbList.length
                      ? 'border-outline-blue-2 bg-surface-blue-1 text-ink-blue-6'
                      : 'border-outline-gray-2 bg-surface-gray-2 text-ink-gray-5'
                  "
                >
                  {{ kbList.length }}
                </span>
                <LucideChevronRight
                  class="ml-auto size-3.5 shrink-0 text-ink-gray-5"
                  :class="{ 'rotate-90': openedSections.aiKb }"
                />
              </button>
              <div v-show="openedSections.aiKb" class="pb-1">
                <router-link
                  v-for="article in kbList"
                  :key="article.name"
                  :to="{ name: 'Article', params: { articleId: article.name } }"
                  class="group flex items-center gap-2 py-1 min-w-0"
                >
                  <span
                    v-if="article.ref"
                    class="shrink-0 rounded bg-surface-gray-2 px-1 font-mono text-[10px] font-semibold text-ink-gray-5"
                  >
                    {{ article.ref }}
                  </span>
                  <span
                    class="text-xs text-ink-blue-6 group-hover:underline truncate min-w-0"
                    :title="article.title"
                  >
                    {{ article.title }}
                  </span>
                </router-link>
                <p v-if="!kbList.length" class="py-1 text-xs text-ink-gray-5">
                  {{
                    __(
                      "No SOP matched. Matching is strict on purpose — a wrong procedure is worse than none."
                    )
                  }}
                </p>
              </div>
            </template>

            <!-- One CTA, and it is the actual next action: chase the missing
                 details when something's blocking, otherwise draft the reply. -->
            <template v-if="ai.summary || buildSheet || itAssist">
              <Button
                v-if="!replyDraft"
                class="w-full mt-3"
                variant="solid"
                theme="blue"
                :label="ctaLabel"
                @click="generateReply"
              />
              <template v-else>
                <div
                  class="mt-3 rounded-md border border-outline-gray-2 bg-surface-gray-1 p-2.5 text-xs leading-relaxed text-ink-gray-8 whitespace-pre-wrap"
                >
                  {{ replyDraft }}
                </div>
                <div class="flex gap-2 mt-2">
                  <Button
                    variant="solid"
                    theme="blue"
                    :label="replyCopied ? __('Copied') : __('Copy reply')"
                    @click="copyReply"
                  />
                  <Button
                    variant="ghost"
                    :label="__('Discard')"
                    @click="replyDraft = ''"
                  />
                </div>
              </template>
            </template>
          </div>
        </Section>
      </div>

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
                    <span class="text-base font-semibold text-ink-gray-8 select-none">
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
import { Button, call, dayjs, toast, Tooltip } from "frappe-ui";
import { computed, inject, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import LucideBookOpen from "~icons/lucide/book-open";
import LucideCalendar from "~icons/lucide/calendar";
import LucideCheck from "~icons/lucide/check";
import LucideChevronRight from "~icons/lucide/chevron-right";
import LucideClipboardList from "~icons/lucide/clipboard-list";
import LucideClock from "~icons/lucide/clock";
import LucideExternalLink from "~icons/lucide/external-link";
import LucideHourglass from "~icons/lucide/hourglass";
import LucideInfo from "~icons/lucide/info";
import LucideListChecks from "~icons/lucide/list-checks";
import LucideRefreshCw from "~icons/lucide/refresh-cw";
import LucideSearch from "~icons/lucide/search";
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

// aiDetail / aiKb are the AI panel's own subsections.
//
// They are deliberately NOT called aiJob / aiSops, which is what the previous
// deploy used. mergeDefaults only fills in keys that are absent, so anyone who
// already loaded that build has `aiJob: true` sitting in localStorage and would
// keep landing on a fully expanded panel — they'd never see this change. New key
// names give everyone the folded default once, and their own choice sticks after
// that. The two stale keys are harmless; useStorage just ignores them.
const openedSections = useStorage(
  "openedSections",
  {
    details: true,
    aiAssist: true,
    // Folded by default. What you land on is the ask, the blocker and the button;
    // the detail is one click away and its count says whether it's worth the click.
    aiDetail: false,
    aiKb: false,
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

// Only claim "no SOP matched" once the request has actually landed, otherwise the
// empty state flashes on every ticket open and reads as a failure.
const kbLoaded = computed(
  () =>
    !recentSimilarTickets.value.loading &&
    Boolean(recentSimilarTickets.value.data)
);

// Article titles are authored as "KB-P02 — Promo code request (…)". Splitting the
// ref out lets the title read as a title in a 360px column instead of wrapping as
// one long blob; the ref still shows, as a tag.
const kbList = computed(() =>
  kbMatches.value.map((a) => {
    const raw = String(a.title || "");
    const m = raw.match(/^\s*(KB-[A-Za-z0-9]+)\s*[—–-]\s*(.+)$/);
    return {
      name: a.name,
      ref: m ? m[1] : "",
      title: m ? m[2] : raw,
      category: a.category || "",
    };
  })
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

// The request type is the identity of the ticket, so it leads as a chip. When the
// enricher couldn't classify one (it's null on plenty of real tickets) the category
// is promoted into that slot instead — and then must not repeat in the meta line.
// Category and system deliberately aren't repeated here: both are visible,
// EDITABLE custom fields in the Ticket Info section below, so restating them
// read-only at the top of the panel cost two lines and added nothing.
const identity = computed(() => {
  const a = ai.value;
  const park = a.park ? parkLabel(a.park) : "";
  return {
    primary: a.requestType || a.category || "",
    park,
    parkColor: park ? parkColor(park) : "",
  };
});

const dueLabel = computed(() =>
  ai.value.dueDate ? formatDate(ai.value.dueDate) : ""
);

// The summary clamps to two lines — the full text is in the ticket body a few
// inches to the left. Measure rather than guess from length, so "more" never
// appears on a summary that already fits.
const summaryEl = ref<HTMLElement | null>(null);
const summaryExpanded = ref(false);
const summaryOverflows = ref(false);

function measureSummary() {
  const el = summaryEl.value;
  if (!el || summaryExpanded.value) return;
  summaryOverflows.value = el.scrollHeight - el.clientHeight > 2;
}

onMounted(() => nextTick(measureSummary));
watch(
  () => [ai.value.summary, openedSections.value.aiAssist],
  () => nextTick(measureSummary)
);

const steps = computed<string[]>(() => {
  const s = itAssist.value?.steps;
  return Array.isArray(s) ? s : [];
});

// One focal block per ticket, and which one it is says what kind of job this is:
// a POS build sheet or an IT action checklist. They are never both present.
const jobKind = computed<"pos" | "it" | null>(() => {
  if (buildSheet.value?.fields?.length) return "pos";
  if (steps.value.length || accessRows.value.length) return "it";
  return null;
});

const jobRows = computed(() => {
  if (jobKind.value === "pos") {
    return (buildSheet.value?.fields || []).map(
      (f: { label: string; value: string }, i: number) => ({
        key: `f${i}`,
        label: f.label,
        value: f.value,
      })
    );
  }
  if (jobKind.value === "it") return accessRows.value;
  return [];
});

const jobTitle = computed(() => {
  if (jobKind.value === "pos") return __("Build sheet");
  return steps.value.length ? __("Suggested steps") : __("Access request");
});

const doneCount = computed(
  () => (stepsDone.value[ticketKey.value] || []).filter((i) => i < steps.value.length).length
);

// A folded strip is only worth opening if you can see what's behind it, so the
// count is the affordance: how many fields, or how far through the checklist.
const jobCount = computed(() =>
  steps.value.length
    ? `${doneCount.value}/${steps.value.length}`
    : String(jobRows.value.length)
);

// Blue when there's something to go and do, grey once nothing's outstanding.
const jobCountActive = computed(() =>
  steps.value.length ? doneCount.value < steps.value.length : jobRows.value.length > 0
);

const urgent = computed(
  () => (buildSheet.value || itAssist.value)?.urgency === "high"
);

const jobDate = computed(() => {
  const d = (buildSheet.value || itAssist.value)?.due_date;
  return d ? formatDate(d) : "";
});

const jobDateLabel = computed(() =>
  jobKind.value === "pos" ? __("Due") : __("By")
);

// Completeness flag, shared by both branches. Names the action and counts the
// items rather than listing them bare — the same change made to the requester
// confirmation email, for the same reason: a bare list doesn't ask for anything.
// Singular and plural are separate strings so it never reads "1 details".
const missing = computed(() => {
  const raw = (buildSheet.value || itAssist.value)?.missing;
  const items: string[] = Array.isArray(raw) ? raw : [];
  const n = items.length;
  const isPos = Boolean(buildSheet.value);
  // POS returns short field labels ("start date"), which read best named inline on
  // one line. IT returns whole questions, which don't fit — those get a headline
  // and fold, so a long question can't push the CTA off screen.
  const inline = n === 1 && items[0].length <= 40;
  let headline: string;
  if (inline) {
    headline = isPos
      ? __("Needs {0} before building", [items[0]])
      : __("Ask the requester: {0}", [items[0]]);
  } else if (isPos) {
    headline =
      n === 1
        ? __("Needs 1 more detail before building")
        : __("Needs {0} details before building", [n]);
  } else {
    headline =
      n === 1
        ? __("1 question for the requester")
        : __("{0} questions for the requester", [n]);
  }
  return { items, inline, headline };
});

const missingOpen = ref(false);

// The one CTA. It is the actual next action, not a generic label: chase what's
// missing when something blocks the job, otherwise draft the reply. Either way it
// runs generateReply, which already writes the "could you confirm" line.
const ctaLabel = computed(() => {
  const n = missing.value.items.length;
  // Named for what it actually produces. With no build sheet or checklist there is
  // nothing to report back, so promising a "reply" would oversell an acknowledgement.
  if (!buildSheet.value && !itAssist.value) return __("Draft acknowledgement");
  if (!n) return __("Draft reply");
  if (buildSheet.value) {
    return n === 1
      ? __("Ask for the missing detail")
      : __("Ask for the {0} missing details", [n]);
  }
  return n === 1 ? __("Ask the question") : __("Ask the {0} questions", [n]);
});

// Which steps an agent has worked through. Deliberately local: there's no backend
// field for it, and inventing one would imply it's shared between agents when it
// isn't. Bounded so it can't grow without limit in localStorage.
const stepsDone = useStorage<Record<string, number[]>>(
  "aiStepsDone",
  {},
  localStorage,
  { mergeDefaults: true }
);

const ticketKey = computed(() => String(ticket.value?.doc?.name || ""));

function isStepDone(i: number) {
  return (stepsDone.value[ticketKey.value] || []).includes(i);
}

function toggleStep(i: number) {
  const key = ticketKey.value;
  if (!key) return;
  const current = [...(stepsDone.value[key] || [])];
  const at = current.indexOf(i);
  if (at === -1) current.push(i);
  else current.splice(at, 1);
  const next = { ...stepsDone.value, [key]: current };
  const keys = Object.keys(next);
  if (keys.length > 60) delete next[keys[0]];
  stepsDone.value = next;
}

// Re-run: the remedy when the AI extracted something wrong. It only queues work —
// a separate worker polls about once a minute — so the UI says "Queued" rather
// than spinning, and pulls the panel's data a few times so the agent doesn't have
// to reload the page to see the result.
const rerunState = ref<"idle" | "queued">("idle");
let refreshTimers: number[] = [];

function clearRefreshTimers() {
  refreshTimers.forEach((t) => clearTimeout(t));
  refreshTimers = [];
}

async function rerunAI() {
  if (rerunState.value !== "idle") return;
  const name = ticketKey.value;
  if (!name) return;
  try {
    const res = await call(
      "helpdesk.helpdesk.doctype.hd_ticket.api.rerun_ai_enrichment",
      { ticket: name }
    );
    rerunState.value = "queued";
    toast.success(
      res?.message || __("Queued — the AI will re-analyse this ticket.")
    );
    clearRefreshTimers();
    const delays = [45000, 90000, 150000];
    delays.forEach((ms, i) => {
      refreshTimers.push(
        window.setTimeout(() => {
          ticket.value?.reload?.();
          recentSimilarTickets.value?.reload?.();
          if (i === delays.length - 1) rerunState.value = "idle";
        }, ms)
      );
    });
  } catch (e: any) {
    // Frappe puts a thrown message in `messages`; a transport failure only has
    // `message`. Fall back so the agent never sees a silent no-op.
    toast.error(
      e?.messages?.[0] || e?.message || __("Could not queue an AI re-run.")
    );
  }
}

onUnmounted(clearRefreshTimers);

// Phase 2c / 3c: compose a suggested reply locally — buy-ticket links or a "here's
// what was set up" confirmation for POS, a "here's what I'm doing" for IT — and offer
// copy. Deliberately no AI call: this is assembled from what the enricher already
// wrote, so opening a ticket and clicking Generate costs nothing.
const replyDraft = ref("");
const replyCopied = ref(false);

function generateReply() {
  const bs = buildSheet.value;
  const it = itAssist.value;
  // Summary-only tickets — the ones the enricher analysed but couldn't put in a
  // build-sheet or IT branch, mostly request type "Other" — used to get no button
  // at all, which is about a third of currently-classified tickets. They get a
  // plain acknowledgement. Deliberately does NOT echo pyek_summary back: it's
  // written in the third person for an agent to read ("Request to add daily
  // utilization section…") and reads oddly returned to the person who wrote in.
  if (!bs && !it) {
    replyDraft.value = [
      "Hi,",
      "",
      "Thanks for flagging this — I'm looking into it now and will follow up shortly.",
      "",
      "Thanks!",
    ].join("\n");
    return;
  }
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
