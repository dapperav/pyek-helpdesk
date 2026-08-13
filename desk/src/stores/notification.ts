import { useAuthStore } from "@/stores/auth";
import { ListResource, Notification } from "@/types";
import { isCustomerPortal } from "@/utils";
import { createListResource, createResource } from "frappe-ui";
import { defineStore } from "pinia";
import { computed, ref, watch } from "vue";
import { globalStore } from "./globalStore";

export const useNotificationStore = defineStore("notification", () => {
  const authStore = useAuthStore();
  const { $socket } = globalStore();

  const visible = ref(false);
  const resource: ListResource<Notification> = createListResource({
    doctype: "HD Notification",
    cache: "Notifications",
    fields: [
      "creation",
      "message",
      "name",
      "notification_type",
      "read",
      "reference_comment",
      "reference_ticket",
      "user_from",
      "user_to",
    ],
    orderBy: "modified desc",
  });
  const clear = createResource({
    url: "helpdesk.helpdesk.doctype.hd_notification.utils.clear",
    auto: false,
    onSuccess: () => resource.reload(),
  });

  const read = (ticket: string) => {
    createResource({
      url: "helpdesk.helpdesk.doctype.hd_notification.utils.clear",
      auto: true,
      params: {
        ticket,
      },
      onSuccess: () => resource.reload(),
    });
  };

  const data = computed(() => resource.data || []);
  const unread = computed(() => data.value.filter((d) => !d.read).length);

  function toggle() {
    visible.value = !visible.value;
  }

  watch(
    () => authStore.hasDeskAccess,
    (newVal) => {
      if (!newVal) return;
      resource.filters = {
        user_to: ["=", authStore.userId],
      };
      resource.reload();
    },
    { immediate: true }
  );
  $socket.on("helpdesk:comment-reaction-update", () => {
    if (isCustomerPortal.value) return;
    resource.reload();
  });

  // PYEK: badge the installed PWA's home-screen icon with the unread count.
  //
  // An installed PWA is just an icon on a home screen, so with the app closed
  // there was nothing at all to say a ticket had been assigned — the count only
  // existed inside the app, on the "Menu" tab, where you had to already be
  // looking. This is the cheap half of that problem; a push notification is the
  // other half.
  //
  // Guarded rather than assumed: the Badging API isn't universal, and Safari
  // rejects the call when the site is running as a tab rather than an installed
  // app. A badge is decoration — a rejection here must never surface as an error.
  watch(unread, (count) => {
    if (!("setAppBadge" in navigator)) return;
    if (count > 0) {
      navigator.setAppBadge(count).catch(() => {});
    } else {
      navigator.clearAppBadge?.().catch(() => {});
    }
  });

  return {
    clear,
    data,
    toggle,
    read,
    unread,
    visible,
    resource,
  };
});
