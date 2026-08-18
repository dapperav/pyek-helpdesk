// Pure signal helpers for PYEK ticket cards rendered OUTSIDE the list row
// (the desktop board). They mirror OutlookTicketRow.vue's rules exactly —
// stripe precedence (grey automated > red urgent > blue needs-action > none)
// and the SLA chip math (7-day cap, day-old breaches are history) — without
// touching that shipped component. If the rules ever change, change both.

export const NOTIFICATION_SENDER_PATTERNS = [
  "noreply",
  "no-reply",
  "no_reply",
  "donotreply",
  "do-not-reply",
  "do_not_reply",
  "notification",
  "notifications",
  "mailer-daemon",
  "postmaster",
  "bounce",
];

export function isNotificationSender(raisedBy?: string): boolean {
  const from = (raisedBy || "").toLowerCase();
  return !!from && NOTIFICATION_SENDER_PATTERNS.some((p) => from.includes(p));
}

// Statuses where the ball is in OUR court (unreplied / needs a response).
const NEEDS_ACTION_STATUSES = new Set(["Open", "Escalated"]);
export function needsAction(status?: string): boolean {
  return NEEDS_ACTION_STATUSES.has(status || "");
}

export function edgeColor(row: {
  raised_by?: string;
  priority?: string;
  status?: string;
}): string {
  if (isNotificationSender(row.raised_by)) return "#94A3B8"; // grey
  if (row.priority === "Urgent") return "#E03434"; // red
  if (needsAction(row.status)) return "#2563EB"; // blue
  return "transparent"; // replied / waiting / done
}

// Frappe datetimes are site-local "YYYY-MM-DD HH:mm:ss"; Safari wants the T.
export function parseFrappeDate(value: string): number {
  return new Date(value.replace(" ", "T")).getTime();
}

export function fmtSpan(ms: number): string {
  const mins = Math.max(1, Math.round(ms / 60_000));
  if (mins < 60) return `${mins}m`;
  const h = Math.floor(mins / 60);
  if (h >= 48) {
    const d = Math.floor(h / 24);
    const rh = h % 24;
    return rh ? `${d}d ${rh}h` : `${d}d`;
  }
  const m = mins % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

// The running SLA reply clock, if one is worth showing. `kind` is semantic —
// the consumer maps it to its own classes. Same rules as the list rows: no
// clock for automated mail or already-answered tickets, deadlines beyond a
// week aren't a running clock, breaches older than a day are history.
export function slaClock(row: {
  raised_by?: string;
  status?: string;
  response_by?: string;
  first_responded_on?: string;
}): { text: string; kind: "hot" | "due" } | null {
  if (
    !needsAction(row.status) ||
    isNotificationSender(row.raised_by) ||
    row.first_responded_on ||
    !row.response_by
  ) {
    return null;
  }
  const diff = parseFrappeDate(row.response_by) - Date.now();
  if (diff >= 0 && diff <= 7 * 24 * 3600_000) {
    return {
      text: `reply due ${fmtSpan(diff)}`,
      kind: diff < 2 * 3600_000 ? "hot" : "due",
    };
  }
  if (diff < 0 && -diff <= 24 * 3600_000) {
    return { text: `reply overdue ${fmtSpan(-diff)}`, kind: "hot" };
  }
  return null;
}

export function parseAssign(assign?: string): string[] {
  try {
    return JSON.parse(assign || "[]");
  } catch {
    return [];
  }
}

// Whole days a ticket has sat untouched — the "quiet Nd" chip on assigned
// cards (Mark's out-of-office worry: owned tickets must not rot invisibly).
export function quietDays(modified?: string): number {
  if (!modified) return 0;
  const ms = Date.now() - parseFrappeDate(modified);
  return ms > 0 ? Math.floor(ms / 86_400_000) : 0;
}
