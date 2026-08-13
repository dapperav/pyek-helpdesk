<template>
  <LayoutHeader>
    <template #left-header>
      <Breadcrumbs
        :items="[
          { label: __('Notifications'), route: { name: 'Notifications' } },
        ]"
      />
    </template>
    <template #right-header>
      <Tooltip :text="__('Mark all as read')">
        <div>
          <Button
            :label="__('Mark all as read')"
            @click="() => notificationStore.clear.submit()"
          >
            <template #prefix>
              <LucideCheckCheck class="h-4 w-4" />
            </template>
          </Button>
        </div>
      </Tooltip>
    </template>
  </LayoutHeader>
  <div v-if="notificationStore.data.length" class="divide-y text-base">
    <RouterLink
      v-for="n in notificationStore.data"
      :key="n.name"
      class="flex cursor-pointer items-start gap-3.5 px-5 py-2.5 hover:bg-surface-gray-2"
      :to="getRoute(n)"
      @click="
        () => {
          notificationStore.read(n.reference_ticket);
        }
      "
    >
      <UserAvatar :name="n.user_from" />
      <div>
        <div class="mb-2 leading-5">
          <span class="space-x-1 rtl:space-x-reverse text-ink-gray-7">
            <!-- Team and Reply don't name a person: a ticket that arrives by email
                 is processed as Administrator, so leading with user_from would
                 read as a system account. They carry their own phrasing. -->
            <span
              v-if="!isSystemOriginated(n)"
              class="font-medium text-ink-gray-9"
              >{{ n.user_from }}</span
            >
            <span v-if="n.notification_type === 'Mention'">{{
              __("mentioned you in ticket")
            }}</span>
            <span v-if="n.notification_type === 'Assignment'">{{
              __("assigned you a ticket")
            }}</span>
            <span v-if="n.notification_type === 'Reaction'">{{
              __("has reopened the ticket")
            }}</span>
            <span v-if="n.notification_type === 'Team'">{{
              __("New ticket for your team")
            }}</span>
            <span v-if="n.notification_type === 'Reply'">{{
              __("New reply on ticket")
            }}</span>
            <span class="font-medium text-ink-gray-9">{{
              n.reference_ticket
            }}</span>
          </span>
        </div>
        <div class="flex items-center gap-2">
          <div class="text-sm text-ink-gray-5">
            {{ dayjs.tz(n.creation).fromNow() }}
          </div>
          <div
            v-if="!n.read"
            class="h-1.5 w-1.5 rounded-full bg-surface-blue-5"
          />
        </div>
      </div>
    </RouterLink>
  </div>
  <div v-else class="flex flex-1 flex-col items-center gap-2">
    <LucideBell class="h-20 w-20 text-ink-gray-2" />
    <div class="text-lg-medium text-ink-gray-4">
      {{ __("No new notifications") }}
    </div>
  </div>
</template>
<script setup lang="ts">
import { Breadcrumbs, dayjs, Tooltip } from "frappe-ui";
import LayoutHeader from "@/components/LayoutHeader.vue";
import { useNotificationStore } from "@/stores/notification";
import { ref } from "vue";
import { onClickOutside } from "@vueuse/core";
import { Notification } from "@/types";
import { UserAvatar } from "@/components";
import LucideBell from "~icons/lucide/bell";
import { __ } from "@/translation";
const notificationStore = useNotificationStore();
const target = ref(null);
onClickOutside(
  target,
  () => {
    if (notificationStore.visible) {
      notificationStore.toggle();
    }
  },
  {
    ignore: ["#notifications-btn"],
  }
);

// Team and Reply are raised by the system processing inbound mail, not by a
// colleague, so the row shouldn't lead with a user's name.
function isSystemOriginated(n: Notification) {
  return n.notification_type === "Team" || n.notification_type === "Reply";
}

function getRoute(n: Notification) {
  // Everything lands on the ticket; only a mention needs the comment anchor.
  // Note the default: this switch used to have none, so any notification type it
  // didn't enumerate returned undefined and gave RouterLink nothing to navigate to.
  if (n.notification_type === "Mention") {
    return {
      name: "TicketAgent",
      params: { ticketId: n.reference_ticket },
      hash: "#" + n.reference_comment,
    };
  }
  return {
    name: "TicketAgent",
    params: { ticketId: n.reference_ticket },
  };
}
</script>
