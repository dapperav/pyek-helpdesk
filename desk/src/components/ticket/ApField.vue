<template>
  <!-- One row of the invoice card: label left, value right — visually identical to
       the read-only card it replaces, but the value is a control. Click it and only
       that row becomes editable, so the card keeps its compact scannable shape
       instead of turning into a form (which is what "Ticket Info" was, and why it
       got deleted in favour of this). -->
  <div class="flex items-center justify-between gap-2">
    <span class="shrink-0 text-ink-gray-5">{{ label }}</span>

    <!-- Check: no edit mode, clicking just flips it. -->
    <button
      v-if="type === 'Check'"
      class="rounded px-1 -mr-1 text-ink-gray-8 hover:bg-surface-gray-2"
      @click="save(current ? 0 : 1)"
    >
      {{ current ? __("Yes") : __("No") }}
    </button>

    <!-- Select: the value itself is the popover target, so one click opens the list. -->
    <Popover
      v-else-if="type === 'Select'"
      placement="bottom-end"
      :show="open"
      @update:show="(v) => (open = v)"
    >
      <template #target="{ togglePopover }">
        <button
          class="min-w-0 truncate rounded px-1 -mr-1 text-right hover:bg-surface-gray-2"
          :class="current ? 'text-ink-gray-8' : 'text-ink-gray-4'"
          @click="togglePopover()"
        >
          {{ current || __("Set") }}
        </button>
      </template>
      <template #body>
        <div
          class="min-w-[190px] rounded-lg bg-surface-elevation-2 p-1.5 shadow-2xl ring-1 ring-black ring-opacity-5"
        >
          <button
            v-for="opt in options"
            :key="opt || '__blank'"
            class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-ink-gray-8 hover:bg-surface-gray-2"
            @click="pick(opt)"
          >
            <span class="truncate">{{ opt || __("Clear") }}</span>
            <LucideCheck v-if="opt === current" class="ml-auto size-4 text-ink-gray-6" />
          </button>
        </div>
      </template>
    </Popover>

    <!-- Date / Data / Currency: swap in an input, focused, and revert on Escape. -->
    <input
      v-else-if="editing"
      ref="inputEl"
      v-model="draft"
      :type="type === 'Date' ? 'date' : 'text'"
      :inputmode="type === 'Currency' ? 'decimal' : undefined"
      class="w-[9.5rem] rounded border border-outline-gray-3 bg-surface-white px-1.5 py-0.5 text-right text-base text-ink-gray-9 outline-none focus:border-outline-gray-4"
      @keydown.enter.prevent="commit"
      @keydown.esc.prevent="cancel"
      @blur="commit"
    />
    <button
      v-else
      class="min-w-0 truncate rounded px-1 -mr-1 text-right hover:bg-surface-gray-2"
      :class="danger ? '' : display ? 'text-ink-gray-8' : 'text-ink-gray-4'"
      :style="danger ? { color: '#b91c1c' } : {}"
      @click="startEdit"
    >
      {{ display || __("Set") }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, ref } from "vue";
import { Popover, call, dayjs, toast } from "frappe-ui";
import { getMeta } from "@/stores/meta";
import { TicketSymbol } from "@/types";
import { __ } from "@/translation";
import LucideCheck from "~icons/lucide/check";

const props = defineProps<{
  ticket: Record<string, any>;
  fieldname: string;
  label: string;
  /** Extra fields to write alongside this one (e.g. terms -> doc type). */
  alsoSet?: (value: any) => Record<string, any>;
  /** Render the value in red — used for an overdue due date. */
  danger?: boolean;
}>();

const ticketRes = inject(TicketSymbol, undefined);
const { getField } = getMeta("HD Ticket");

// Type and Select options come from the doctype meta, not a hardcoded list, so the
// picker can never drift from what the field will actually accept.
const meta = computed(() => getField(props.fieldname) as any);
const type = computed(() => meta.value?.fieldtype || "Data");
const options = computed(() => {
  const raw = String(meta.value?.options || "").split("\n");
  // The stored options string leads with a blank — that's the field's "unset" value.
  // Keep exactly one, rendered as "Clear", and drop any stray extra blanks.
  const values = raw.filter((o) => o !== "");
  return raw.some((o) => o === "") ? ["", ...values] : values;
});

// Optimistic value so the row relabels the instant you pick, before the save lands.
const optimistic = ref<any>(undefined);
const current = computed(() =>
  optimistic.value !== undefined ? optimistic.value : props.ticket?.[props.fieldname]
);

const display = computed(() => {
  const v = current.value;
  if (v === null || v === undefined || v === "") return "";
  if (type.value === "Date") {
    const d = dayjs(v);
    return d.isValid() ? d.format("MM/DD/YYYY") : String(v);
  }
  if (type.value === "Currency") {
    const n = Number(v);
    return Number.isNaN(n)
      ? String(v)
      : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
  }
  return String(v);
});

const open = ref(false);
const editing = ref(false);
const draft = ref("");
const inputEl = ref<HTMLInputElement | null>(null);

function startEdit() {
  const v = current.value;
  // The date input needs ISO; everything else edits as its raw stored value.
  draft.value =
    type.value === "Date" && v ? dayjs(v).format("YYYY-MM-DD") : v == null ? "" : String(v);
  editing.value = true;
  nextTick(() => {
    inputEl.value?.focus();
    inputEl.value?.select?.();
    // Opens the native calendar on the first click rather than making them click twice.
    if (type.value === "Date") (inputEl.value as any)?.showPicker?.();
  });
}

function cancel() {
  editing.value = false;
}

function commit() {
  if (!editing.value) return; // Escape already closed it
  editing.value = false;
  let v: any = draft.value.trim();
  if (v === "") v = null;
  else if (type.value === "Currency") {
    const n = Number(v.replace(/[$,]/g, ""));
    if (Number.isNaN(n)) {
      toast.error(__("{0} must be a number").replace("{0}", props.label));
      return;
    }
    v = n;
  }
  save(v);
}

function pick(opt: string) {
  open.value = false;
  save(opt === "" ? null : opt);
}

function save(value: any) {
  const prev = props.ticket?.[props.fieldname];
  if (normalize(prev) === normalize(value)) return;
  optimistic.value = value;
  const fields: Record<string, any> = { [props.fieldname]: value };
  Object.assign(fields, props.alsoSet?.(value) || {});
  const ok = () => toast.success(__("{0} updated").replace("{0}", props.label));
  const fail = () => {
    optimistic.value = undefined; // fall back to the doc's real value
    toast.error(__("Couldn't update {0}. Try again.").replace("{0}", props.label));
  };
  if (ticketRes?.value?.setValue) {
    ticketRes.value.setValue.submit(fields, { onSuccess: ok, onError: fail });
  } else {
    call("frappe.client.set_value", {
      doctype: "HD Ticket",
      name: props.ticket?.name,
      fieldname: fields,
    })
      .then(ok)
      .catch(fail);
  }
}

function normalize(v: any) {
  return v === null || v === undefined || v === "" ? "" : String(v);
}
</script>
