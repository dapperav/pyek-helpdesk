<template>
  <!-- Echo on duty: the SOS receiver alert (Mark, 2026-08-19 — timed but
       recurring). Serious pose, red-edged bubble, straight voice; NO splash
       vocabulary — this is a fire alarm with a face, not an easter egg. The
       thin red bar drains over the ~90s surfacing; he resurfaces every ~4
       minutes while the window holds (state machine in composables/
       echoSos.ts). Clicking goes to Awaiting first reply; × dismisses this
       agent's window. -->
  <Transition name="esos">
    <div v-if="sosAlert.visible" class="esos" role="alert">
      <div class="esos-bubble" @click="go">
        <button class="esos-x" :aria-label="__('Dismiss')" @click.stop="dismiss">
          ×
        </button>
        <b>{{ __("SOS from {0}", [sosAlert.senderName]) }}</b>
        — {{ __("{0} waiting on a first reply. All hands.", [String(sosAlert.count)]) }}
        <i class="esos-hint">{{ __("click → Awaiting first reply") }}</i>
        <span class="esos-timer"></span>
      </div>
      <img :src="ECHO_POSES.serious" class="esos-img" alt="" />
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router";
import { ECHO_POSES } from "./echoAssets";
import { endWindow, sosAlert } from "@/composables/echoSos";
import { __ } from "@/translation";

const router = useRouter();

function go() {
  endWindow();
  // the backend sends a path like /helpdesk/tickets?view=… — strip the app
  // base so the router resolves it
  router.push(sosAlert.url.replace(/^\/helpdesk/, ""));
}
function dismiss() {
  endWindow();
}
</script>

<style scoped>
.esos {
  position: fixed;
  right: 18px;
  bottom: 12px;
  z-index: 46;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 5px;
}
.esos-img {
  width: 72px;
  filter: drop-shadow(0 4px 10px rgba(4, 26, 46, 0.3));
  margin-right: 4px;
}
.esos-bubble {
  position: relative;
  background: #fff;
  border: 2px solid #e11d48;
  border-radius: 13px;
  border-bottom-right-radius: 4px;
  padding: 9px 13px;
  font-size: 13px;
  line-height: 1.45;
  max-width: 250px;
  color: #22324f;
  box-shadow: 0 6px 18px rgba(4, 26, 46, 0.3);
  cursor: pointer;
}
.esos-hint {
  display: block;
  font-size: 10.5px;
  color: #8b94a5;
  font-style: normal;
  margin-top: 3px;
}
.esos-x {
  position: absolute;
  top: -9px;
  right: -9px;
  width: 20px;
  height: 20px;
  line-height: 18px;
  text-align: center;
  background: #1b2a4a;
  color: #fff;
  border-radius: 50%;
  font-size: 12px;
  cursor: pointer;
}
.esos-timer {
  position: absolute;
  left: 10px;
  right: 10px;
  bottom: -2px;
  height: 3px;
  background: #e11d48;
  border-radius: 2px;
  transform-origin: left;
  animation: esos-drain 90s linear both;
}
@keyframes esos-drain {
  from {
    transform: scaleX(1);
  }
  to {
    transform: scaleX(0);
  }
}
.esos-enter-active {
  transition:
    transform 0.55s cubic-bezier(0.3, 1.15, 0.5, 1),
    opacity 0.4s ease;
}
.esos-leave-active {
  transition:
    transform 0.4s ease-in,
    opacity 0.35s ease;
}
.esos-enter-from,
.esos-leave-to {
  transform: translateY(125%);
  opacity: 0;
}
@media (prefers-reduced-motion: reduce) {
  .esos-enter-active,
  .esos-leave-active {
    transition: opacity 0.3s ease;
  }
  .esos-enter-from,
  .esos-leave-to {
    transform: none;
  }
}
</style>
