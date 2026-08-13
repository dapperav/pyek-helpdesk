import { useScreenSize } from "@/composables/screen";
import { canGoBackInApp } from "@/composables/mobile";
import { isStaleChunkError, recoverFromStaleChunk, clearStaleChunkGuard } from "@/staleChunk";
import { canViewPersona, personaInterrupt } from "@/persona";
import { useAuthStore } from "@/stores/auth";
import { useUserStore } from "@/stores/user";
import { isCustomerPortal } from "@/utils";
import { createRouter, createWebHistory } from "vue-router";
const { isMobileView } = useScreenSize();

export const LOGIN_PAGE = "/login";

// type the meta fields
declare module "vue-router" {
  interface RouteMeta {
    auth?: boolean;
    agent?: boolean;
    admin?: boolean;
    public?: boolean;
    onSuccessRoute?: string;
    parent?: string;
  }
}

// Pages that render inside the portal chrome; PortalRoot picks the agent or
// customer shell from the session.
const portalRoutes = [
  // Agent Portal Routes
  {
    path: "",
    // PYEK: phones open straight to the ticket inbox; desktop lands on the
    // dashboard home.
    redirect: () => (isMobileView.value ? "/tickets" : "/home"),
  },
  {
    path: "/home",
    name: "Home",
    // PYEK: HomeView wraps the mobile/desktop choice with a LIVE viewport check
    // (the module-scope isMobileView below is frozen at load and unreliable).
    // Mobile → MobileHome (tiles + queue jumps); desktop → PyekHome.
    component: () => import("@/pages/home/HomeView.vue"),
  },

  {
    path: "/tickets",
    name: "TicketsAgent",
    component: () => import("@/pages/ticket/Tickets.vue"),
  },
  {
    path: "/tickets/:ticketId",
    name: "TicketAgent",
    component: () =>
      import(`@/pages/ticket/${handleMobileView("TicketAgent")}.vue`),
    props: true,
  },
  {
    path: "/tickets/new/:templateId?",
    name: "TicketAgentNew",
    component: () => import("@/pages/ticket/TicketNew.vue"),
    props: true,
    meta: {
      onSuccessRoute: "TicketAgent",
      parent: "TicketsAgent",
    },
  },
  {
    path: "/notifications",
    name: "Notifications",
    component: () => import("@/pages/MobileNotifications.vue"),
  },
  {
    path: "/kb",
    name: "AgentKnowledgeBase",
    component: () => import("@/pages/knowledge-base/KnowledgeBaseAgent.vue"),
  },
  {
    path: "/search",
    name: "SearchAgent",
    component: () => import("@/pages/SearchAgent.vue"),
    meta: { auth: true },
  },
  {
    path: "/kb/articles/:articleId",
    name: "Article",
    component: () => import("@/pages/knowledge-base/Article.vue"),
    props: true,
  },
  {
    path: "/articles/new/:id",
    name: "NewArticle",
    component: () => import("@/pages/knowledge-base/NewArticle.vue"),
    props: true,
  },
  {
    path: "/customers",
    name: "CustomerList",
    component: () => import("@/pages/customer/Customers.vue"),
  },
  {
    path: "/customers/:id",
    name: "Customer",
    component: () => import("@/pages/customer/Customer.vue"),
    props: true,
  },
  {
    path: "/contacts",
    name: "ContactList",
    component: () => import("@/pages/contact/Contacts.vue"),
  },
  {
    path: "/contacts/:id",
    name: "Contact",
    component: () => import("@/pages/contact/Contact.vue"),
    props: true,
  },
  {
    path: "/agents",
    name: "AgentList",
    redirect: "/tickets",
  },
  {
    path: "/teams",
    name: "Teams",
    redirect: "/tickets",
  },
  {
    path: "/teams/:teamId",
    name: "Team",
    redirect: "/tickets",
  },
  {
    path: "/dashboard",
    name: "Dashboard",
    component: () => import("@/pages/dashboard/Dashboard.vue"),
  },
  {
    path: "/call-logs",
    name: "CallLogs",
    component: () => import("@/pages/call-logs/CallLogs.vue"),
  },

  // Customer Portal Routes
  {
    path: "/my-tickets",
    name: "TicketsCustomer",
    component: () => import("@/pages/ticket/Tickets.vue"),
    meta: {
      public: true,
      auth: true,
    },
  },
  {
    path: "/my-tickets/:ticketId",
    name: "TicketCustomer",
    component: () => import("@/pages/ticket/TicketCustomer.vue"),
    meta: {
      public: true,
      auth: true,
    },
    props: true,
  },
  {
    path: "/my-tickets/new",
    name: "TicketNew",
    component: () => import("@/pages/ticket/TicketNew.vue"),
    props: true,
    meta: {
      onSuccessRoute: "TicketCustomer",
      parent: "TicketsCustomer",
      public: true,
      auth: true,
    },
  },
  {
    path: "/kb-public",
    name: "CustomerKnowledgeBase",
    component: () => import("@/pages/knowledge-base/KnowledgeBaseCustomer.vue"),
    meta: {
      public: true,
      auth: true,
    },
  },
  {
    path: "/kb-public/:categoryId",
    name: "Articles",
    component: () => import("@/pages/knowledge-base/Articles.vue"),
    props: true,
    meta: {
      public: true,
      auth: true,
    },
  },
  {
    path: "/kb-public/articles/:articleId",
    name: "ArticlePublic",
    component: () => import("@/pages/knowledge-base/Article.vue"),
    props: true,
    meta: {
      public: true,
      auth: true,
    },
  },

  // Additonal routes
  {
    path: "/:pathMatch(.*)*",
    name: "Invalid Page",
    component: () => import("@/pages/InvalidPage.vue"),
  },
];

const routes = [
  // Renders bare — no portal chrome.
  {
    path: "/onboarding",
    name: "Persona",
    component: () => import("@/pages/PersonaForm.vue"),
    beforeEnter: () => canViewPersona(useAuthStore()) || { name: "Home" },
  },
  {
    path: "/",
    component: () => import("@/roots/PortalRoot.vue"),
    children: portalRoutes,
  },
];

const handleMobileView = (componentName: string) => {
  return isMobileView.value ? `Mobile${componentName}` : componentName;
};

export const router = createRouter({
  history: createWebHistory("/helpdesk/"),
  routes,
});

// PYEK: a lazy route chunk that 404s after a deploy used to leave the app
// wedged — the navigation aborted and the screen never changed. Reload the
// target instead so the shell comes back with current chunk URLs. See
// staleChunk.ts for why the installed PWA hits this and a browser tab doesn't.
router.onError((err, to) => {
  if (isStaleChunkError(err) && recoverFromStaleChunk(router.resolve(to).href)) {
    return;
  }
  console.error(err);
});

// Vite raises this when a preloaded chunk can't be fetched, which on some
// navigations fires ahead of the router's own error hook.
if (typeof window !== "undefined") {
  window.addEventListener("vite:preloadError", (e: any) => {
    if (recoverFromStaleChunk(window.location.pathname + window.location.search)) {
      e.preventDefault?.();
    }
  });
}

router.beforeEach(async (to, _, next) => {
  const authStore = useAuthStore();
  isCustomerPortal.value = to.meta.public || false;
  if (authStore.isLoggedIn) {
    await authStore.init();
  }

  const interrupt = personaInterrupt(to, authStore);
  if (interrupt) return next(interrupt);

  if (!authStore.isLoggedIn) {
    const redirectURL = to.fullPath !== "/" ? to.fullPath : "";

    window.location.href =
      LOGIN_PAGE +
      (redirectURL ? `?redirect-to=/helpdesk${redirectURL}` : "/helpdesk");
  } else if (!to.meta.public && !authStore.hasDeskAccess) {
    next({ name: "TicketsCustomer" });
  } else if (to.name === "TicketAgent" && !authStore.isAgent) {
    const ticketId = to.params.ticketId;
    next({
      name: "TicketCustomer",
      params: { ticketId },
    });
  } else {
    next();
  }
});

router.afterEach(async (to) => {
  // A navigation landed, so the chunks we hold are good: re-arm the one-shot
  // reload guard for the next deploy.
  clearStaleChunkGuard();
  // Lets the mobile shell tell "cold-launched here" from "navigated here" — a
  // push notification opens the app directly on a ticket, where the bottom nav is
  // normally hidden. vue-router leaves `history.state.back` null exactly when
  // the current entry is the first in-app one. See canGoBackInApp.
  canGoBackInApp.value = window.history.state?.back != null;
  if (to.meta.public) return;
  const { users } = useUserStore();
  if (!users?.fetched) {
    await users.fetch();
  }
});
