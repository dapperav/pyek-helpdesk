<template>
  <Dialog v-model:open="show" :title="__('Close ticket')">
    <template #default>
      <div class="flex flex-col flex-1 gap-3">
        <p class="text-p-sm text-ink-gray-6">
          {{
            __(
              "One line on what actually fixed it. This is the only place that knowledge gets written down — the AI reuses it on similar tickets later."
            )
          }}
        </p>
        <FormControl
          ref="resolutionInput"
          v-model="resolution"
          type="textarea"
          size="sm"
          variant="subtle"
          rows="3"
          :placeholder="
            __('e.g. Printer had lost its LAN IP — rebooted the switch port and re-paired it in Toast')
          "
          maxlength="500"
          @keydown.ctrl.enter.capture.stop="saveAndClose"
          @keydown.meta.enter.capture.stop="saveAndClose"
        />
        <!-- "Done!" is what most closes say today, and it teaches nobody
             anything. Warn rather than block: an agent who means it should still
             get through in one more click. -->
        <p v-if="tooThin" class="text-p-sm text-ink-amber-7">
          {{
            __(
              "That won't help anyone later — try naming the cause or the fix, not just that it's finished."
            )
          }}
        </p>
        <div class="flex gap-2">
          <Button
            variant="solid"
            theme="blue"
            :loading="saving"
            :label="
              isMac ? __('Save & close (⌘ + ⏎)') : __('Save & close (Ctrl + ⏎)')
            "
            :disabled="!resolution.trim()"
            @click="saveAndClose"
          />
          <Button
            variant="ghost"
            :loading="saving"
            :label="__('Close without')"
            @click="closeWithout"
          />
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { useDevice } from "@/composables";
import { TicketSymbol } from "@/types";
import { Button, Dialog, FormControl } from "frappe-ui";
import { computed, inject, nextTick, ref, watch } from "vue";

const emit = defineEmits<{ (e: "closed"): void }>();

const ticket = inject(TicketSymbol)!;
const { isMac } = useDevice();
const show = defineModel<boolean>({ default: false });

const resolution = ref("");
const saving = ref(false);

// Mirrors the enricher's distiller gate, so what passes here is what will
// actually survive into an article rather than being silently discarded later.
const ACK_ONLY = /^(ok(ay)?|done|all done|completed?|fixed|resolved|thanks?|thank you|got it|sure|yes|np)[\s!.:)-]*$/i;
const tooThin = computed(() => {
  const t = resolution.value.trim();
  if (!t) return false;
  return ACK_ONLY.test(t) || t.split(/\s+/).length < 4;
});

watch(show, async (open) => {
  if (!open) return;
  resolution.value = ticket.value?.doc?.pyek_resolution || "";
  await nextTick();
  // $el can be a comment node mid-dialog-transition — querySelector only
  // exists on real elements, so probe for it rather than assuming (this
  // watcher logged a TypeError on every open since PR 79).
  resolutionInput.value?.$el?.querySelector?.("textarea")?.focus();
});

const resolutionInput = ref<any>(null);

function submit(fields: Record<string, string>) {
  saving.value = true;
  ticket.value.setValue.submit(fields, {
    onSuccess() {
      saving.value = false;
      show.value = false;
      emit("closed");
    },
    onError() {
      // Leave the dialog open with the text intact rather than losing what they
      // typed; the status change didn't happen either, so nothing is half-done.
      saving.value = false;
    },
  });
}

function saveAndClose() {
  const text = resolution.value.trim();
  if (!text) return;
  submit({ pyek_resolution: text, status: "Closed" });
}

function closeWithout() {
  submit({ status: "Closed" });
}
</script>
