import { createApp, h } from "vue";
import { isStaleChunkError, recoverFromStaleChunk } from "@/staleChunk";
import {
  Badge,
  Button,
  Dialog,
  ErrorMessage,
  FeatherIcon,
  FormControl,
  frappeRequest,
  FrappeUI,
  setConfig,
  TextInput,
  toast,
  Tooltip,
} from "frappe-ui";
import { createPinia } from "pinia";
import App from "./App.vue";
import { spritePlugin } from "frappe-ui/icons";
import { createDialog } from "./components/dialogs";
import "./index.css";
import { router } from "./router";
import { telemetryPlugin } from "frappe-ui/frappe";
import { isCustomerPortal } from "@/utils";
import { translationPlugin } from "./translation";
import CircleAlert from "~icons/lucide/circle-alert";
import { initSocket } from "./socket";

const globalComponents = {
  Badge,
  Button,
  Dialog,
  ErrorMessage,
  FeatherIcon,
  FormControl,
  Tooltip,
  TextInput,
};

setConfig("resourceFetcher", frappeRequest);
setConfig("serverMessagesHandler", (msgs) => {
  if (isCustomerPortal.value) {
    return;
  }
  msgs.forEach((msg) => {
    msg = JSON.parse(msg);
    if (msg && msg.message == "Feedback email has been sent to the customer.") {
      toast.success(msg.message);
      return;
    }
    toast.create({
      message: msg.message,
      icon: h(CircleAlert, { class: "text-ink-blue-5" }),
    });
  });
});
setConfig("fallbackErrorHandler", (error) => {
  const msg = error.exc_type
    ? (error.messages || error.message || []).join(", ")
    : error.message;
  toast.error(msg);
});

const pinia = createPinia();
const app = createApp(App);

// PYEK: an async component whose chunk 404s after a deploy surfaces here rather
// than through the router. Reload so the app picks up current chunk URLs instead
// of leaving a dead screen behind. See staleChunk.ts.
app.config.errorHandler = (err, _instance, info) => {
  if (isStaleChunkError(err) &&
      recoverFromStaleChunk(window.location.pathname + window.location.search)) {
    return;
  }
  console.error(err, info);
};

app.use(FrappeUI);
app.use(spritePlugin);
app.use(pinia);
// NOTE: app.use(router) happens in start() below, NOT here. Installing the
// router kicks off the initial navigation immediately, and in dev mode the
// auth guard's first POST must not fire before getDevBoot has put
// window.csrf_token in place — an authenticated session gets CSRFTokenError
// on that guard and boots to a blank page. (Guest sessions never noticed:
// CSRF isn't enforced for them, which is why this only surfaced the first
// time someone actually logged into the dev server.)
app.use(translationPlugin);
app.use(telemetryPlugin, { app_name: "helpdesk" });

for (const c in globalComponents) {
  app.component(c, globalComponents[c]);
}

app.config.globalProperties.$dialog = createDialog;

// PYEK: dev boot. get_context_for_dev only answers on a developer_mode bench;
// when developing against a remote site (PYEK_DEV_BACKEND, see vite.config.js)
// fall back to parsing the boot assignments out of the remote /helpdesk shell,
// which the server renders for every build via jinjaBootData. Both paths yield
// the same keys, csrf_token included.
async function getDevBoot() {
  try {
    return await frappeRequest({
      url: "/api/method/helpdesk.www.helpdesk.index.get_context_for_dev",
    });
  } catch (e) {
    const res = await fetch("/pyek-remote-boot", { credentials: "include" });
    const html = await res.text();
    const values = {};
    for (const m of html.matchAll(/window\["([^"]+)"\] = (.*);/g)) {
      try {
        values[m[1]] = JSON.parse(m[2]);
      } catch (_) {}
    }
    if (!("csrf_token" in values)) {
      console.warn(
        "PYEK dev boot: no boot data in the remote shell — not logged in? " +
          "Open /login (proxied) or a ?sid= link first, then reload."
      );
    }
    return values;
  }
}

let socket;
async function start() {
  if (import.meta.env.DEV) {
    const values = await getDevBoot();
    for (let key in values) {
      window[key] = values[key];
    }
  }
  // In production the boot values are inline in the HTML and already on
  // window; in dev they are now too. Only from here is it safe to install
  // the router (which starts the initial navigation) and mount.
  app.use(router);
  socket = initSocket();
  app.config.globalProperties.$socket = socket;
  app.mount("#app");
}
start();
