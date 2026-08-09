<template>
  <!-- The two actions people actually take, as buttons. Assigning was a small
       text link and 88% of tickets never got assigned; closing was buried in
       the status dropdown. Each hides once it no longer applies, so a ticket
       already assigned to you and already closed shows no bar at all. -->
  <div
    v-if="showAssignSelf || showClose"
    class="flex items-center gap-2 px-5 pt-3"
  >
    <Button
      v-if="showAssignSelf"
      :loading="assignSelf.loading"
      :label="__('Assign to me')"
      @click="assignSelf.submit()"
    >
      <template #prefix>
        <LucideUserPlus class="size-4" />
      </template>
    </Button>
    <Button
      v-if="showClose"
      variant="solid"
      :label="__('Close ticket')"
      @click="onCloseClicked"
    >
      <template #prefix>
        <LucideCheck class="size-4" />
      </template>
    </Button>
  </div>
  <TicketResolutionModal
    v-model="showResolutionDialog"
    @closed="activities.reload()"
  />
  <Tabs
    :modelValue="tabIndex"
    :tabs="tabs"
    @update:modelValue="changeTabTo"
    class="[&_[role='tab']]:px-0 [&_[role='tablist']]:px-5 [&_[role='tablist']]:gap-7.5 [&_[role='tablist']]:flex-shrink-0 [&_[role='tabpanel'][data-state='active']]:flex-1"
  >
    <!-- Counts so a tab says whether it is worth opening: 164 of 270 tickets
         have no real attachment at all. Mirrors the component's own default
         markup, plus the number. -->
    <template #tab-item="{ tab, selected }">
      <button
        class="flex items-center gap-1.5 py-2.5 text-base duration-300 ease-in-out hover:text-ink-gray-9"
        :class="selected ? 'text-ink-gray-9' : 'text-ink-gray-5'"
      >
        <component :is="tab.icon" class="size-4" />
        {{ __(tab.label) }}
        <span
          v-if="tabCounts[tab.name] !== undefined"
          class="rounded-full px-1.5 text-xs leading-[18px]"
          :class="
            tabCounts[tab.name]
              ? 'bg-surface-gray-3 text-ink-gray-7'
              : 'text-ink-gray-4'
          "
        >
          {{ tabCounts[tab.name] }}
        </span>
      </button>
    </template>
    <template #tab-panel="{ tab }">
      <TicketAttachments
        v-if="Boolean(activities.data) && tab.name === 'attachment'"
        :activities="filterActivities('attachment')"
        :title="tab.label"
      />
      <TicketAgentActivities
        v-else-if="Boolean(activities.data)"
        ref="ticketAgentActivitiesRef"
        :activities="filterActivities(tab.name as TicketTab)"
        :title="tab.label"
        :ticket-status="ticket.doc.status"
        @email:reply="
          (e) => {
            communicationAreaRef?.replyToEmail(e);
          }
        "
        @update="
          () => {
            activities.reload();
            ticketAgentActivitiesRef?.scrollToLatestActivity();
          }
        "
      />
      <!-- <div v-else class="flex items-center justify-center flex-col flex-1">
        <Button :loading="true" variant="ghost" size="2xl" />
        <p class="text-2xl-medium text-ink-gray-5">Loading...</p>
      </div> -->
    </template>
  </Tabs>
  <!-- Comm Area -->
  <CommunicationArea
    ref="communicationAreaRef"
    :ticketId="String(ticket.doc?.name)"
    :to-emails="[ticket.doc?.raised_by]"
    :cc-emails="[]"
    :bcc-emails="[]"
    :key="ticket.doc?.name"
    @update="
      () => {
        activities.reload();
        ticketAgentActivitiesRef?.scrollToLatestActivity();
      }
    "
  />
</template>

<script setup lang="ts">
import CommunicationArea from "@/components/CommunicationArea.vue";
import {
  ActivityIcon,
  AttachmentIcon,
  CommentIcon,
  EmailIcon,
  PhoneIcon,
} from "@/components/icons";
import TicketAttachments from "@/components/ticket/TicketAttachments.vue";
import { useActiveTabManager } from "@/composables/useActiveTabManager";
import { useTelephonyStore } from "@/stores/telephony";
import {
  ActivitiesSymbol,
  FeedbackActivity,
  TabObject,
  TicketSymbol,
  TicketTab,
} from "@/types";
import TicketResolutionModal from "@/components/ticket-agent/TicketResolutionModal.vue";
import { useAuthStore } from "@/stores/auth";
import { Button, createResource, Tabs } from "frappe-ui";
import { storeToRefs } from "pinia";
import { computed, ComputedRef, inject, ref } from "vue";
import LucideCheck from "~icons/lucide/check";
import LucideUserPlus from "~icons/lucide/user-plus";
import { TicketAgentActivities } from "../ticket";

const ticket = inject(TicketSymbol);
const activities = inject(ActivitiesSymbol);

const ticketAgentActivitiesRef = ref<InstanceType<
  typeof TicketAgentActivities
> | null>(null);
const communicationAreaRef = ref<InstanceType<typeof CommunicationArea> | null>(
  null
);
const telephonyStore = useTelephonyStore();
const { isCallingEnabled } = storeToRefs(telephonyStore);

const tabs: ComputedRef<TabObject[]> = computed(() => {
  const _tabs: TabObject[] = [
    {
      name: "activity",
      label: "Activity",
      icon: ActivityIcon,
    },
    {
      name: "email",
      label: "Emails",
      icon: EmailIcon,
    },
    {
      name: "comment",
      label: "Comments",
      icon: CommentIcon,
    },
    {
      name: "attachment",
      label: "Attachments",
      icon: AttachmentIcon,
    },
  ];

  if (isCallingEnabled.value) {
    _tabs.push({
      name: "call",
      label: "Calls",
      icon: PhoneIcon,
    });
  }
  return _tabs;
});

const { tabIndex, changeTabTo } = useActiveTabManager(tabs);

const showResolutionDialog = ref(false);
const auth = useAuthStore();

// `_assign` is a JSON array on the ticket; treat anything unparseable as
// unassigned rather than throwing in a computed.
const assignees = computed<string[]>(() => {
  try {
    return JSON.parse(ticket.value?.doc?._assign || "[]") || [];
  } catch {
    return [];
  }
});

const showAssignSelf = computed(
  () =>
    !!auth.userId &&
    !!ticket.value?.doc &&
    !assignees.value.includes(auth.userId)
);

const showClose = computed(
  () => ticket.value?.doc && ticket.value.doc.status !== "Closed"
);

const assignSelf = createResource({
  url: "frappe.desk.form.assign_to.add",
  makeParams: () => ({
    doctype: "HD Ticket",
    name: ticket.value?.doc?.name,
    assign_to: [auth.userId],
  }),
  onSuccess: () => {
    ticket.value?.reload?.();
    activities.value?.reload?.();
  },
});

function onCloseClicked() {
  // Route through the same dialog the status dropdown and Reply & close use,
  // so "what fixed it" is asked in exactly one place. Already answered once?
  // Then close straight away rather than nagging.
  if (!ticket.value.doc.pyek_resolution) {
    showResolutionDialog.value = true;
    return;
  }
  ticket.value.setValue.submit(
    { status: "Closed" },
    { onSuccess: () => activities.value.reload() }
  );
}

// Activity and Calls are deliberately absent: Activity is everything (a count
// would just restate the page) and call logs load separately.
const tabCounts = computed<Record<string, number>>(() => {
  const data = activities.value?.data;
  if (!data) return {};
  const attachments = new Set<string>();
  for (const source of [data.communications || [], data.comments || []]) {
    for (const c of source) {
      for (const a of c.attachments || []) {
        if (!a.is_noise) attachments.add(a.file_url || a.name);
      }
    }
  }
  return {
    email: (data.communications || []).length,
    comment: (data.comments || []).length,
    attachment: attachments.size,
  };
});

// TODO: refactor for pagination
// can be done once we sort out the backend
// sender mail will be  user using portal
const _activities = computed(() => {
  if (!activities.value?.data) {
    return [];
  }
  const emailProps = activities.value?.data?.communications.map(
    (email, idx: number) => {
      return {
        subject: email.subject,
        content: email.content,
        sender: {
          name: email.user.email,
          full_name: email.user.name,
        },
        to: email.recipients,
        type: "email",
        key: email.creation,
        cc: email.cc,
        bcc: email.bcc,
        creation: email.communication_date || email.creation,
        attachments: email.attachments,
        name: email.name,
        deliveryStatus: email.delivery_status,
        isFirstEmail: idx === 0,
        // Present only when the backend judged this a short automated alert
        // whose HTML is pure scaffolding; null means render the original.
        compactLines: email.compact_lines,
        isAutomated: email.is_automated,
      };
    }
  );

  const commentProps = activities.value.data.comments.map((comment) => {
    return {
      name: comment.name,
      type: "comment",
      key: comment.creation,
      commentedBy: comment.commented_by,
      commenter: comment.user.name,
      creation: comment.creation,
      content: comment.content,
      attachments: comment.attachments,
    };
  });

  activities.value.data.history.map((h) => {
    // }
    h.action;
    h.owner;
    // if h.actions includes h.owner, replace it with 'themselves'
    if (h.action && h.owner && h.action.includes(h.owner)) {
      h.action = h.action.replace(h.owner, "themselves");
    }
    return h;
  });

  const historyProps = [
    ...activities.value.data.history,
    ...activities.value.data.views,
  ].map((h) => {
    return {
      type: "history",
      key: h.creation,
      content: h.action ? h.action : "viewed this",
      creation: h.creation,
      user: h.user.name + " ",
    };
  });

  const callProps = activities.value.data.calls.map((call) => {
    return {
      ...call,
      type: "call",
      name: call.name,
      key: call.creation,
      call_type: call.type,
      content: `${call.caller || "Unknown"} made a call to ${
        call.receiver || "Unknown"
      }`,
      duration: call.duration ? call.duration + "s" : "0s",
    };
  });

  const sorted = [
    ...emailProps,
    ...commentProps,
    ...historyProps,
    ...callProps,
  ].sort((a, b) => new Date(a.creation) - new Date(b.creation));
  const data = [];
  let i = 0;

  while (i < sorted.length) {
    const currentActivity = sorted[i];

    if (currentActivity.type === "history") {
      currentActivity.relatedActivities = [currentActivity];
      for (let j = i + 1; j < sorted.length + 1; j++) {
        const nextActivity = sorted[j];

        if (
          nextActivity &&
          nextActivity.user === currentActivity.user &&
          nextActivity.content !== "viewed this" &&
          !nextActivity.content.includes("assigned") &&
          !nextActivity.content.includes("unassigned")
        ) {
          currentActivity.relatedActivities.push(nextActivity);
        } else {
          data.push(currentActivity);
          i = j - 1;
          break;
        }
      }
    } else {
      data.push(currentActivity);
    }
    i++;
  }
  // add feedback data at the last always
  // name is email
  // full_name is name

  if (ticket.value.doc.feedback_rating === 0) {
    return data;
  }
  let feedbackActivity: FeedbackActivity[] = [
    {
      type: "feedback",
      key: "feedback-activity",
      feedback_rating: ticket.value?.doc.feedback_rating,
      feedback_extra: ticket.value?.doc.feedback_extra,
      feedback: ticket.value?.doc.feedback,
      sender: {
        name: ticket.value?.doc.raised_by,
        full_name: ticket.value?.doc.contact,
      },
    },
  ];
  data.push(...feedbackActivity);

  return data;
});

function filterActivities(eventType: TicketTab) {
  // Attachments hang off emails and comments rather than being an activity
  // type of their own, so that tab gets everything and picks them out itself.
  if (eventType === "activity" || eventType === "attachment") {
    return _activities.value;
  }
  return _activities.value.filter((activity) => activity.type === eventType);
}
</script>
