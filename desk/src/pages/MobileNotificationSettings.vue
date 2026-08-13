<template>
  <LayoutHeader>
    <template #left-header>
      <Breadcrumbs
        :items="[
          {
            label: __('Notification settings'),
            route: { name: 'NotificationSettings' },
          },
        ]"
      />
    </template>
  </LayoutHeader>
  <div class="p-5">
    <PushNotificationSettings />
  </div>
</template>

<script setup lang="ts">
import { Breadcrumbs } from "frappe-ui";
import LayoutHeader from "@/components/LayoutHeader.vue";
import PushNotificationSettings from "@/components/Settings/Notifications/PushNotificationSettings.vue";
import { __ } from "@/translation";
</script>
