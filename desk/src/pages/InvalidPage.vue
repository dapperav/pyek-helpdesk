<template>
  <div
    class="grid h-full place-items-center px-4 py-20 text-center text-lg text-ink-gray-5"
  >
    <div class="space-y-4">
      <!-- Echo with the upside-down map — 404s are his (echo-eggs round,
           2026-08-19) -->
      <div class="flex justify-center items-center mx-auto">
        <img :src="ECHO_POSES.lost" class="w-24" alt="" />
      </div>
      <div class="flex flex-col gap-1">
        <div class="text-lg-medium text-ink-gray-8">
          {{ __("This page drifted out to sea.") }}
        </div>
        <div class="text-center text-p-base text-ink-gray-6 mt-1">
          {{
            __(
              "You don't have permission to view this page, or it no longer exists."
            )
          }}
        </div>
      </div>
      <Button :route="{ name: 'TicketsAgent' }" variant="subtle">
        <template #prefix>
          <FeatherIcon name="arrow-left" class="size-4" />
        </template>
        {{ __("Back to Tickets") }}
      </Button>
    </div>
  </div>
</template>

<script setup>
import { Button, FeatherIcon } from "frappe-ui";
import { ECHO_POSES } from "@/components/echo/echoAssets";
import { __ } from "@/translation";
</script>
