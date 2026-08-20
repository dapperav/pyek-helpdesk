import vue from "@vitejs/plugin-vue";
import vueJsx from "@vitejs/plugin-vue-jsx";
import { existsSync } from "node:fs";
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
        registerType: "autoUpdate",
        devOptions: {
          enabled: true,
        },
        workbox: {
          cleanupOutdatedCaches: true,
          maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
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
        // On a bench, socket.ts imports the real common_site_config.json four
        // levels up. Off-bench (a dev machine), that file doesn't exist and
        // the build fails to resolve it — alias it to a stub carrying the
        // default socketio_port. Production is unaffected either way: the
        // imported value is only used when location.port is set.
        ...(existsSync(
          path.resolve(__dirname, "../../../../sites/common_site_config.json")
        )
          ? {}
          : {
              "../../../../sites/common_site_config.json": path.resolve(
                __dirname,
                "dev/common_site_config.stub.json"
              ),
            }),
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
