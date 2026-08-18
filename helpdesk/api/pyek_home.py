"""Stats for the agent home (PyekHome / MobileHome), scoped to what an agent
can act on.

The old tiles counted raw totals: "SLA breached / at risk" was dominated by
historical machine-ticket failures (deliberately never recomputed after the
bot-SLA quarantine), and "Open" mixed camera alerts in with human requests.
This method draws the human/machine line with the SAME test the ack
suppression and AI skip use (`_automated_sender`), so the dashboard, the
mailer and the enricher can never disagree about what counts as a bot.

Also returns `bot_senders` — the exact addresses judged automated — so the
frontend can scope its client-side charts with the same judgment instead of
re-implementing pattern matching in JS.
"""

import frappe
from frappe.utils import get_datetime, today

from helpdesk.utils import agent_only


@frappe.whitelist()
@agent_only
def get_home_stats() -> dict:
    from helpdesk.helpdesk.doctype.hd_ticket.api import _automated_sender

    fields = [
        "name",
        "status_category",
        "raised_by",
        "_assign",
        "first_responded_on",
        "resolution_date",
        "creation",
    ]
    # pyek_auto_closed is provisioned by the enricher; guard so a site where it
    # hasn't run yet (fresh bench, other product line) doesn't 500 the home.
    has_auto_closed = frappe.get_meta("HD Ticket").has_field("pyek_auto_closed")
    if has_auto_closed:
        fields.append("pyek_auto_closed")

    rows = frappe.get_all("HD Ticket", fields=fields, limit_page_length=0)

    # One pattern-match per distinct sender, not per ticket.
    verdicts: dict[str, bool] = {}

    def is_bot(sender: str) -> bool:
        addr = (sender or "").lower()
        if addr not in verdicts:
            verdicts[addr] = _automated_sender(addr)
        return verdicts[addr]

    user = frappe.session.user
    today_start = get_datetime(today())

    open_rows = [r for r in rows if r.status_category in ("Open", "Paused")]
    open_human = [r for r in open_rows if not is_bot(r.raised_by)]
    silenced_today = [
        r
        for r in rows
        if get_datetime(r.creation) >= today_start
        and (is_bot(r.raised_by) or (has_auto_closed and r.get("pyek_auto_closed")))
    ]

    return {
        "my_open": sum(1 for r in open_rows if user in (r.get("_assign") or "")),
        "open_human": len(open_human),
        "awaiting_first_reply": sum(
            1 for r in open_human if not r.first_responded_on
        ),
        "resolved_today": sum(
            1
            for r in rows
            if r.resolution_date and get_datetime(r.resolution_date) >= today_start
        ),
        "silenced_today": len(silenced_today),
        "silenced_today_camera": sum(
            1 for r in silenced_today if has_auto_closed and r.get("pyek_auto_closed")
        ),
        "bot_senders": sorted(
            {(r.raised_by or "").lower() for r in rows if is_bot(r.raised_by)}
        ),
    }


@frappe.whitelist()
@agent_only
def get_home_board() -> dict:
    """The desktop triage board (Mark, 2026-08-18): one bucket per queue —
    POS, IT, Mine — each of up to five open tickets ordered by the moment
    something last ARRIVED on them (ticket created, or the newest customer
    reply; for Mine, being handed the ticket counts as an arrival too).

    Ordering is by inbound activity on purpose: agents triage by "what just
    landed", not by ticket age — an old ticket whose requester replied a
    minute ago belongs on top.
    """
    user = frappe.session.user

    rows = frappe.get_all(
        "HD Ticket",
        filters={"status_category": ("in", ("Open", "Paused"))},
        fields=[
            "name",
            "subject",
            "pyek_summary",
            "raised_by",
            "contact",
            "creation",
            "first_responded_on",
            "agent_group",
            "email_account",
            "_assign",
        ],
        limit_page_length=0,
    )
    names = [r.name for r in rows]

    # Newest customer reply per ticket, one query for the whole board.
    # Raw SQL (parameterized): frappe.get_all refuses SQL functions in
    # fields ("SQL functions are not allowed as strings in SELECT") — found
    # live, the dev proxy can't exercise new server code before a deploy.
    last_inbound: dict[str, object] = {}
    if names:
        last_inbound = dict(
            frappe.db.sql(
                """
                select reference_name, max(communication_date)
                from `tabCommunication`
                where reference_doctype = 'HD Ticket'
                  and reference_name in %(names)s
                  and sent_or_received = 'Received'
                group by reference_name
                """,
                {"names": names},
            )
        )

    # When each of MY tickets was handed to me (any assignment path writes a
    # ToDo — the same fact PR 149's notification hook keys on).
    assigned_at: dict[str, object] = {}
    if names:
        assigned_at = dict(
            frappe.db.sql(
                """
                select reference_name, max(creation)
                from `tabToDo`
                where reference_type = 'HD Ticket'
                  and reference_name in %(names)s
                  and allocated_to = %(user)s
                  and status != 'Cancelled'
                group by reference_name
                """,
                {"names": names, "user": user},
            )
        )

    def arrival(r, mine: bool):
        stamps = [get_datetime(r.creation)]
        if last_inbound.get(r.name):
            stamps.append(get_datetime(last_inbound[r.name]))
        if mine and assigned_at.get(r.name):
            stamps.append(get_datetime(assigned_at[r.name]))
        return max(stamps)

    def serialize(r, mine: bool):
        stamp = arrival(r, mine)
        return {
            "name": r.name,
            "subject": r.subject,
            "pyek_summary": r.pyek_summary,
            "raised_by": r.raised_by,
            "contact": r.contact,
            "creation": r.creation,
            "first_responded_on": r.first_responded_on,
            "agent_group": r.agent_group,
            "email_account": r.email_account,
            "last_arrival": stamp,
            # Distinguish "new assignment" cards in the Mine column.
            "assigned_at": assigned_at.get(r.name) if mine else None,
        }

    def bucket(pred, mine=False, cap=5):
        picked = [r for r in rows if pred(r)]
        picked.sort(key=lambda r: arrival(r, mine), reverse=True)
        return [serialize(r, mine) for r in picked[:cap]]

    return {
        "pos": bucket(lambda r: r.agent_group == "POS Support"),
        "it": bucket(lambda r: r.email_account == "IT Support"),
        "mine": bucket(lambda r: user in (r.get("_assign") or ""), mine=True),
        # The Knowledge Base card's number on the More-views shelf.
        "kb_articles": frappe.db.count("HD Article", {"status": "Published"}),
    }
