<template>
  <FrappeUIProvider>
    <router-view />
  </FrappeUIProvider>
  <Dialogs />
</template>

<script setup lang="ts">
import { Dialogs } from "@/components/dialogs";
import { FrappeUIProvider, setConfig, toast, useTheme } from "frappe-ui";
import { h, onMounted } from "vue";
import Wifi from "~icons/lucide/wifi";
import WifiOff from "~icons/lucide/wifi-off";
import { __ } from "./translation";
import { isCustomerPortal, getBrowserTimezone } from "./utils";

// NOTE: intentionally NOT running @vueuse useFavicon(config.favicon) here.
// useFavicon rewrites EVERY link[rel*="icon"] — favicon, mask-icon AND
// apple-touch-icon — to the HD Settings branding favicon. That clobbered the
// per-site home-screen icon (PMIT/PMAP/PMHR) rendered server-side in
// www/helpdesk/index.html, and iOS rejects SVG apple-touch icons anyway. The
// browser-tab favicon + home-screen apple-touch icon are set statically/per
// site in index.html instead, so we leave the DOM icon links alone.

if (!localStorage.getItem("theme")) {
  localStorage.setItem("theme", "light");
}
useTheme();

onMounted(() => {
  window.addEventListener("online", () => {
    toast.create({
      message: __("You are now online."),
      icon: h(Wifi, { class: "text-ink-base" }),
    });
  });

  window.addEventListener("offline", () => {
    toast.create({
      message: __("You are now offline."),
      icon: h(WifiOff, { class: "text-ink-base" }),
    });
  });
  !isCustomerPortal.value && setConfig("localTimezone", window.timezone?.user);
  setConfig("systemTimezone", window.timezone?.system || null);
});
</script>
