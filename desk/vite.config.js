import vue from "@vitejs/plugin-vue";
import vueJsx from "@vitejs/plugin-vue-jsx";
import path from "path";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";
import {
  getLocalFrappeUIDevConfig,
  importFrappeUIPlugin,
} from "./vite-helpers";

export default defineConfig(async ({ mode }) => {
  const { useLocalFrappeUI, localFrappeUIAliases } = getLocalFrappeUIDevConfig({
    mode,
    rootDir: __dirname,
  });

  const frappeui = await importFrappeUIPlugin({ useLocalFrappeUI });
  const config = {
    define: {
      // PYEK: a per-build stamp for the service-worker script URL.
      //
      // Frappe Cloud serves /assets/helpdesk/desk/sw.js with
      // `max-age=31536000, immutable` — correct for the hashed chunks, wrong for
      // the ONE file whose whole job is to be re-checked. Measured on 2026-08-13:
      // right after a deploy, `sw.js` returned the PREVIOUS build's 330-byte body
      // while `sw.js?bust=1` returned the new 1031-byte one from the same origin,
      // seconds apart, with different ETags and Last-Modified dates.
      //
      // The filename can't be hashed (a service worker's URL has to be stable
      // enough to find) and the cache header isn't ours to change, so the script
      // URL carries a build stamp instead. Registration looks the worker up by
      // SCOPE, not script URL, so the changing query doesn't orphan an existing
      // registration or its push subscription.
      __SW_VERSION__: JSON.stringify(Date.now().toString(36)),
    },
    plugins: [
      frappeui({
        frappeProxy: true,
        lucideIcons: true,
        jinjaBootData: true,
        buildConfig: {
          outDir: `../helpdesk/public/desk`,
          emptyOutDir: true,
          indexHtmlPath: "../helpdesk/www/helpdesk/index.html",
        },
        frappeTypes: {
          input: {
            helpdesk: [
              "hd_ticket_status",
              "hd_ticket",
              "hd_service_holiday_list",
              "hd_service_level_agreement",
              "hd_agent",
              "hd_team",
              "hd_customer",
            ],
            frappe: ["assignment_rule", "contact"],
          },
        },
      }),

      vue(),
      vueJsx(),
      VitePWA({
        // PYEK: a hand-written, push-ONLY service worker (src/sw.js).
        //
        // History: a caching SW served stale chunks after a deploy and wedged the
        // installed PWA, so PR 95 set `selfDestroying: true` to remove the worker
        // entirely. Web push needs a worker, so that flag is gone — but src/sw.js
        // has no fetch handler and no cache, which is what made the old one
        // dangerous. See the comment block in src/sw.js before changing this.
        strategies: "injectManifest",
        srcDir: "src",
        filename: "sw.js",
        // The whole point: NO precache manifest. Without this, injectManifest
        // demands a `self.__WB_MANIFEST` injection point and would hand the
        // worker the very asset list that caused the stale-chunk freeze.
        injectManifest: {
          injectionPoint: undefined,
        },
        // Registration is deliberately ours (composables/webPush.ts), not the
        // plugin's auto-injected snippet: the worker should only be registered
        // for a logged-in agent who has opted into notifications, not for every
        // visitor on first paint.
        injectRegister: false,
        devOptions: {
          enabled: false,
        },
        manifest: {
          display: "standalone",
          name: "PYEKMAIL",
          short_name: "PYEKMAIL",
          id: "/helpdesk",
          start_url: "/helpdesk",
          // scope must contain start_url; vite-plugin-pwa otherwise defaults it
          // to the build base (/assets/helpdesk/desk/), which excludes /helpdesk
          // and makes browsers reject the install metadata.
          scope: "/helpdesk",
          theme_color: "#1B2A4A",
          background_color: "#1B2A4A",
          description: "PYEKMAIL — PYEK Group internal support portal.",
          icons: [
            {
              src: "/assets/helpdesk/desk/manifest/pyek-icon-192.png",
              sizes: "192x192",
              type: "image/png",
              purpose: "any",
            },
            {
              src: "/assets/helpdesk/desk/manifest/pyek-maskable-192.png",
              sizes: "192x192",
              type: "image/png",
              purpose: "maskable",
            },
            {
              src: "/assets/helpdesk/desk/manifest/pyek-icon-512.png",
              sizes: "512x512",
              type: "image/png",
              purpose: "any",
            },
            {
              src: "/assets/helpdesk/desk/manifest/pyek-maskable-512.png",
              sizes: "512x512",
              type: "image/png",
              purpose: "maskable",
            },
          ],
        },
      }),
    ],
    server: {
      allowedHosts: true,
      fs: {
        allow: [".."],
      },
    },
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "src"),
        "tailwind.config.js": path.resolve(__dirname, "tailwind.config.js"),
        // ...localFrappeUIAliases,
      },
      // frappe-ui is served from source (excluded from optimizeDeps) and the
      // submodule ships its own node_modules with older tiptap/ProseMirror.
      // Force a single copy of each so the editor doesn't load two
      // prosemirror-state instances (RangeError: different instances of a keyed plugin).
      dedupe: [
        "@tiptap/core",
        "@tiptap/pm",
        "prosemirror-state",
        "prosemirror-model",
        "prosemirror-transform",
        "prosemirror-view",
        "prosemirror-keymap",
        "prosemirror-commands",
        "prosemirror-history",
        "prosemirror-gapcursor",
        "prosemirror-tables",
      ],
    },
    optimizeDeps: {
      include: [
        "feather-icons",
        "tailwind.config.js",
        "prosemirror-state",
        "prosemirror-view",
        "prosemirror-gapcursor",
        "prosemirror-tables",
        "lowlight",
        "interactjs",
      ],
      exclude: ["frappe-ui"],
    },
  };
  return config;
});
