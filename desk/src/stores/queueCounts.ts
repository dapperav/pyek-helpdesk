import { defineStore } from "pinia";
import { call } from "frappe-ui";
import { reactive } from "vue";
import { useAuthStore } from "@/stores/auth";

// Live queue counts for the icon rail's POS / IT / Mine pills (Mark,
// 2026-08-18). Three frappe.client.get_count round trips — a proven core
// endpoint, deliberately no new server code (a new endpoint's first real test
// would be its first prod call). Filters mirror PyekHome's pool math exactly:
// POS and IT by agent_group (the team field — the one thing every ticket in a
// queue has, email or internal), Mine by _assign, all limited to live work
// (status_category Open/Paused).
export const useQueueCountsStore = defineStore("pyekQueueCounts", () => {
  const auth = useAuthStore();
  const counts = reactive<{ pos: number; it: number; mine: number }>({
    pos: 0,
    it: 0,
    mine: 0,
  });

  const LIVE: [string, string[]] = ["in", ["Open", "Paused"]];

  async function fetchCount(filters: Record<string, any>): Promise<number> {
    try {
      const n = await call("frappe.client.get_count", {
        doctype: "HD Ticket",
        filters,
      });
      return typeof n === "number" ? n : 0;
    } catch {
      return 0; // a failed count renders no pill, never an error
    }
  }

  async function refresh() {
    const [pos, it, mine] = await Promise.all([
      fetchCount({ agent_group: "POS Support", status_category: LIVE }),
      fetchCount({ agent_group: "IT Support", status_category: LIVE }),
      fetchCount({
        _assign: ["like", `%${auth.user}%`],
        status_category: LIVE,
      }),
    ]);
    counts.pos = pos;
    counts.it = it;
    counts.mine = mine;
  }

  // Same freshness rhythm as the Home pools: reload when the window comes
  // back into focus, plus a slow heartbeat. start() is idempotent — the
  // sidebar mounts once per layout, but guard anyway.
  let started = false;
  function onVisible() {
    if (!document.hidden) refresh();
  }
  function start() {
    if (started) return;
    started = true;
    refresh();
    document.addEventListener("visibilitychange", onVisible);
    setInterval(refresh, 180_000);
  }

  return { counts, refresh, start };
});
