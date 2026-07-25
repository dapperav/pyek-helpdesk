<template>
  <!-- PYEK: one-tap move between the POS and IT queues. The team (agent_group)
       is what the POS Tickets / IT Tickets views filter on, so this reassigns
       the ticket's queue in a single click. Injects the shared ticket resource,
       so it works in both the desktop and mobile ticket views. -->
  <Button
    :label="compact ? shortLabel : label"
    :tooltip="label"
    :loading="ticket?.setValue?.loading"
    @click="move"
  >
    <template #prefix>
      <FeatherIcon name="repeat" class="h-4 w-4" />
    </template>
  </Button>
</template>

<script setup lang="ts">
import { __ } from "@/translation";
import { TicketSymbol } from "@/types";
import { Button, FeatherIcon, toast } from "frappe-ui";
import { computed, inject } from "vue";

defineProps<{ compact?: boolean }>();

const POS_TEAM = "POS Support";
const IT_TEAM = "IT Support";

const ticket = inject(TicketSymbol)!;
const isIT = computed(() => ticket.value?.doc?.agent_group === IT_TEAM);
const target = computed(() => (isIT.value ? POS_TEAM : IT_TEAM));
const label = computed(() =>
  isIT.value ? __("Move to POS") : __("Move to IT")
);
const shortLabel = computed(() => (isIT.value ? __("POS") : __("IT")));

function move() {
  const t = target.value;
  ticket.value.setValue.submit({ agent_group: t });
  toast.success(__("Moved to {0}", [t]));
}
</script>
