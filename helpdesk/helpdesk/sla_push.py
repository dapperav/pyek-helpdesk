"""SLA-risk push: warn the assignee before a first-response deadline dies.

Unlike "a new ticket arrived", a first-response deadline is genuinely
actionable — and the dashboard's open-by-age chart shows how often it slips
(~half of open human tickets are over 7 days old, measured 2026-08-14).

Rules, chosen to make the FIRST run safe on a site with months of history:
- Human tickets only (same `_automated_sender` line as everything else) —
  the bot-SLA quarantine already parks machine mail on year-long targets.
- Fires when `response_by` is inside [now - 4h, now + 2h]: soon-due and
  freshly-missed. The 4h floor stops the first run from blasting a push for
  every historically-failed ticket at once.
- Assignees only. An unassigned at-risk ticket is the "Awaiting first reply"
  view's job (and the home tile counts it); pushing it to a whole team every
  hour would train everyone to swipe it away.
- Once per (ticket, agent): an existing "SLA due" HD Notification row is the
  dedupe marker, same trick the Team notification uses.

Delivery rides the normal HD Notification path, so per-agent prefs and quiet
hours apply — an overnight deadline pushes at 2am only if the ticket is
Urgent; otherwise the agent still finds the notification in the bell list.
"""

import json

import frappe
from frappe.utils import add_to_date, now_datetime

RISK_HORIZON_HOURS = 2  # push when due within this window...
STALE_FLOOR_HOURS = 4  # ...or missed no longer than this ago


def notify_response_due():
    """Hourly scheduler entry (see hooks.py)."""
    from helpdesk.helpdesk.doctype.hd_ticket.api import _automated_sender

    now = now_datetime()
    rows = frappe.get_all(
        "HD Ticket",
        filters={
            "status_category": ["in", ["Open", "Paused"]],
            "first_responded_on": ["is", "not set"],
            # `between` implies set, so no separate is-set condition needed.
            "response_by": [
                "between",
                [
                    add_to_date(now, hours=-STALE_FLOOR_HOURS),
                    add_to_date(now, hours=RISK_HORIZON_HOURS),
                ],
            ],
        },
        fields=["name", "raised_by", "response_by", "_assign"],
    )

    for ticket in rows:
        try:
            if _automated_sender(ticket.raised_by):
                continue
            assignees = json.loads(ticket.get("_assign") or "[]")
            for user in assignees:
                if not user or user == "Administrator":
                    continue
                if frappe.db.exists(
                    "HD Notification",
                    {
                        "notification_type": "SLA due",
                        "reference_ticket": ticket.name,
                        "user_to": user,
                    },
                ):
                    continue
                frappe.get_doc(
                    frappe._dict(
                        doctype="HD Notification",
                        user_from="Administrator",
                        reference_ticket=ticket.name,
                        user_to=user,
                        notification_type="SLA due",
                    )
                ).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(
                title=f"PMIT push: SLA-risk sweep failed for {ticket.name}",
                message=frappe.get_traceback(),
            )

    frappe.db.commit()
