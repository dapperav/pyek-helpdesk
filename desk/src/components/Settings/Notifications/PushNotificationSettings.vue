<template>
  <div class="flex flex-col gap-6">
    <!-- This device: the existing opt-in, surfaced properly instead of living
         only behind the drawer's profile dropdown. Permission is still only
         ever requested from this explicit tap (an on-load prompt is the
         fastest route to a permanent iOS denial). -->
    <div>
      <div class="text-base-semibold text-ink-gray-9">
        {{ __("This device") }}
      </div>
      <div class="mt-3 flex items-center justify-between gap-4">
        <div class="min-w-0">
          <div class="text-base text-ink-gray-8">{{ deviceLabel }}</div>
          <div class="mt-0.5 text-sm text-ink-gray-5">
            {{ deviceHint }}
          </div>
        </div>
        <Button
          v-if="pushState !== 'unsupported' && pushState !== 'denied'"
          :label="pushState === 'on' ? __('Turn off') : __('Turn on')"
          :loading="pushState === 'working'"
          @click="togglePush"
        />
      </div>
    </div>

    <div>
      <div class="text-base-semibold text-ink-gray-9">
        {{ __("What gets pushed") }}
      </div>
      <div class="mt-1 text-sm text-ink-gray-5">
        {{ __("Applies to all your devices.") }}
      </div>
      <div class="mt-3 divide-y divide-outline-gray-modals">
        <div
          v-for="row in rows"
          :key="row.key"
          class="flex items-center justify-between gap-4 py-2.5"
        >
          <div class="min-w-0">
            <div class="text-base text-ink-gray-8">{{ row.label }}</div>
            <div class="mt-0.5 text-sm text-ink-gray-5">{{ row.hint }}</div>
          </div>
          <Switch
            size="sm"
            :model-value="prefValue(row)"
            :disabled="prefs.loading || saving"
            @update:model-value="(v) => setPref(row, v)"
          />
        </div>
      </div>
    </div>

    <!-- Quiet hours: default on 9pm–7am (site time), Urgent tickets still
         push. Times save on change; the window may wrap midnight. -->
    <div>
      <div class="flex items-center justify-between gap-4">
        <div class="min-w-0">
          <div class="text-base-semibold text-ink-gray-9">
            {{ __("Quiet hours") }}
          </div>
          <div class="mt-0.5 text-sm text-ink-gray-5">
            {{ __("No pushes during these hours — except Urgent tickets.") }}
          </div>
        </div>
        <Switch
          size="sm"
          :model-value="quiet.enabled"
          :disabled="prefs.loading || saving"
          @update:model-value="(v) => saveQuiet({ enabled: v })"
        />
      </div>
      <div
        v-if="quiet.enabled"
        class="mt-3 flex items-center gap-3 text-base text-ink-gray-8"
      >
        <label class="flex items-center gap-2">
          {{ __("From") }}
          <input
            type="time"
            class="rounded border-outline-gray-2 bg-surface-base px-2 py-1 text-base text-ink-gray-8 focus:border-outline-gray-4 focus:ring-0"
            :value="quiet.start"
            :disabled="saving"
            @change="(e: any) => saveQuiet({ start: e.target.value })"
          />
        </label>
        <label class="flex items-center gap-2">
          {{ __("to") }}
          <input
            type="time"
            class="rounded border-outline-gray-2 bg-surface-base px-2 py-1 text-base text-ink-gray-8 focus:border-outline-gray-4 focus:ring-0"
            :value="quiet.end"
            :disabled="saving"
            @change="(e: any) => saveQuiet({ end: e.target.value })"
          />
        </label>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Button, Switch, createResource, call, toast } from "frappe-ui";
import { pushState, refreshPushState, togglePush } from "@/composables/webPush";
import { __ } from "@/translation";

interface PrefRow {
  key: string;
  // The HD Notification types this switch controls. "Mentions & reactions"
  // is one switch over two types — they're the same kind of interruption.
  types: string[];
  label: string;
  hint: string;
}

const rows: PrefRow[] = [
  {
    key: "assignment",
    types: ["Assignment"],
    label: __("Assignments"),
    hint: __("A ticket is assigned to you"),
  },
  {
    key: "mention",
    types: ["Mention", "Reaction"],
    label: __("Mentions & reactions"),
    hint: __("A colleague mentions you or reacts"),
  },
  {
    key: "team",
    types: ["Team"],
    label: __("New team tickets"),
    hint: __("A human ticket arrives for a team you're on"),
  },
  {
    key: "reply",
    types: ["Reply"],
    label: __("Replies"),
    hint: __("A requester replies on a ticket assigned to you"),
  },
  {
    key: "sla",
    types: ["SLA due"],
    label: __("SLA warnings"),
    hint: __("A ticket assigned to you is due a first response within 2 hours"),
  },
];

const prefs = createResource({
  url: "helpdesk.helpdesk.web_push.get_push_prefs",
  auto: true,
});

const saving = ref(false);

function prefValue(row: PrefRow): boolean {
  const data = prefs.data;
  if (!data) return true;
  // A combined row reads as ON unless every type in it is off, so flipping it
  // on from a mixed state is a single tap.
  return row.types.some((t) => data[t] !== false);
}

// Quiet-hours state: server truth when loaded, defaults (on, 21:00–07:00)
// while loading or when no agent row exists — matching the send path.
const quiet = computed(() => {
  const q = prefs.data?._quiet;
  return {
    enabled: q ? q.enabled !== false : true,
    start: q?.start || "21:00",
    end: q?.end || "07:00",
  };
});

async function saveQuiet(patch: { enabled?: boolean; start?: string; end?: string }) {
  saving.value = true;
  try {
    const next = { ...quiet.value, ...patch };
    await call("helpdesk.helpdesk.web_push.set_quiet_hours", {
      enabled: next.enabled ? 1 : 0,
      start: next.start,
      end: next.end,
    });
    if (prefs.data) prefs.data._quiet = next;
  } catch (e) {
    toast.error(__("Could not save quiet hours."));
    prefs.reload();
  } finally {
    saving.value = false;
  }
}

async function setPref(row: PrefRow, enabled: boolean) {
  saving.value = true;
  try {
    for (const t of row.types) {
      await call("helpdesk.helpdesk.web_push.set_push_pref", {
        notification_type: t,
        enabled: enabled ? 1 : 0,
      });
      if (prefs.data) prefs.data[t] = enabled;
    }
  } catch (e) {
    toast.error(__("Could not save the preference."));
    prefs.reload();
  } finally {
    saving.value = false;
  }
}

const deviceLabel = computed(() => {
  switch (pushState.value) {
    case "on":
      return __("Notifications are on for this device");
    case "working":
      return __("Just a moment…");
    case "denied":
      return __("Notifications are blocked");
    case "unsupported":
      return __("This browser can't do push notifications");
    default:
      return __("Notifications are off on this device");
  }
});

const deviceHint = computed(() => {
  switch (pushState.value) {
    case "denied":
      // Nothing a tap can do: the browser won't re-prompt once refused.
      return __("Allow notifications for this site in your device settings.");
    case "unsupported":
      return __("On iPhone, install the app to your home screen first.");
    case "on":
      return __("Pushes arrive even when the app is closed.");
    default:
      return __("Get a push when something below happens.");
  }
});

onMounted(refreshPushState);
</script>
