import { call } from "frappe-ui";

// "Acting = taking it" (Mark, 2026-08-14): replying to or resolving an
// unassigned ticket from a phone claims it for the acting agent first, so
// every acted-on ticket ends up with an owner. Desktop flows are untouched —
// callers gate on the mobile view themselves.

export function parseAssign(
  assign: string | string[] | null | undefined
): string[] {
  if (Array.isArray(assign)) return assign;
  try {
    return JSON.parse(assign || "[]") || [];
  } catch {
    return [];
  }
}

export async function selfAssignTicket(ticketId: string): Promise<boolean> {
  const me = window.agent;
  if (!me) return false;
  await call("frappe.desk.form.assign_to.add", {
    doctype: "HD Ticket",
    name: ticketId,
    assign_to: [me],
  });
  // The activity feed's "assigned X" line comes from HD Ticket Activity rows,
  // which the assign_to API does not create — AssignTo.vue inserts one by
  // hand for the same reason.
  await call("frappe.client.insert", {
    doc: {
      doctype: "HD Ticket Activity",
      ticket: ticketId,
      action: `assigned ${me}`,
    },
  });
  return true;
}
