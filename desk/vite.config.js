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

  // PYEK: dev against a remote Frappe site instead of a local bench.
  //   PYEK_DEV_BACKEND=https://staging.example.com yarn dev
  // Off-bench (this repo's dev machines are Windows laptops, and Frappe can't
  // run on them) there is no localhost:8000 to proxy to, so the stock
  // frappeProxy plugin is disabled and an equivalent proxy points at the
  // remote site instead. Cookies set by the remote (sid) are rewritten to
  // host-only so the session sticks to the localhost origin.
  const devBackend = process.env.PYEK_DEV_BACKEND;
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
        frappeProxy: !devBackend,
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
        // PYEK: this plugin now provides the MANIFEST ONLY. The real service
        // worker is hand-written at helpdesk/www/sw.js, served at /sw.js so its
        // scope covers the whole origin — read the comment block there for why
        // that scope is load-bearing rather than cosmetic.
        //
        // `selfDestroying` keeps emitting a tiny unregister-me worker at
        // /assets/helpdesk/desk/sw.js, and that is deliberate MIGRATION work, not
        // leftover config: phones that opted in while the worker lived at that
        // path still hold a registration there. On its next update check it now
        // fetches this stub and unregisters itself — which also invalidates its
        // push subscription, so nobody ends up with two workers pushing the same
        // notification twice. The stale server-side row then 410s on its next
        // send and gets pruned automatically.
        //
        // Do not point this back at a real worker. Registration is ours
        // (composables/webPush.ts), gated on an agent explicitly opting in.
        selfDestroying: true,
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
      ...(devBackend
        ? {
            port: 8080,
            proxy: {
              // The remote /helpdesk shell carries the jinja-injected boot
              // (window["csrf_token"] = ...). /helpdesk itself must stay local
              // (it's this dev server's SPA), so main.js fetches the remote
              // shell through this dedicated path to bootstrap dev boot data
              // when the backend has no developer_mode (see getDevBoot).
              "/pyek-remote-boot": {
                target: devBackend,
                changeOrigin: true,
                secure: true,
                rewrite: () => "/helpdesk",
              },
              "^/(desk|app|login|api|assets|files|private)": {
                target: devBackend,
                changeOrigin: true,
                secure: true,
                ws: true,
                cookieDomainRewrite: "",
              },
            },
          }
        : {}),
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
        ...(existsSync(path.resolve(__dirname, "../../../../sites/common_site_config.json"))
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
