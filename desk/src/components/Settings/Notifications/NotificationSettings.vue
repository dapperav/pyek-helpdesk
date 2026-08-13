<template>
  <SettingsLayoutBase
    :description="
      __('Choose which events reach your phone as push notifications.')
    "
  >
    <template #title>
      <h1 class="text-lg-semibold text-ink-gray-8">
        {{ __("Notifications") }}
      </h1>
    </template>
    <template #content>
      <PushNotificationSettings />
    </template>
  </SettingsLayoutBase>
</template>

<script setup lang="ts">
import SettingsLayoutBase from "@/components/layouts/SettingsLayoutBase.vue";
import PushNotificationSettings from "./PushNotificationSettings.vue";
import { __ } from "@/translation";
</script>
