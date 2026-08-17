import frappe

from helpdesk.helpdesk.utils.agent_email import send_thread_email


def after_insert(doc, method=None):
    """Notify + email the assignee when a ticket is assigned.

    Hooked on ToDo rather than Notification Log because Frappe drops
    self-assignment notifications entirely: ``assign_to.notify_assignment``
    returns early when ``assigned_by == allocated_to``, and
    ``make_notification_logs`` skips any log whose ``for_user`` equals its
    ``from_user``. An agent who picks up a ticket themselves still wants it in
    their mailbox — and every assignment lands here, whether it came from an
    agent, an Assignment Rule, or the API.

    The HD Notification (which is what triggers the web push) is created HERE
    for the same reason (2026-08-17, found via Josh's silent assignment):
    the UI assigns through ``frappe.desk.form.assign_to.add``, which never
    touches ``HDTicket.assign_agent`` — so its ``notify_agent`` call was dead
    code on every real assignment and an Assignment push had never fired.
    Self-assignments stay silent: claiming your own ticket needs no buzz.
    """
    if doc.reference_type != "HD Ticket":
        return
    if not (doc.reference_name and doc.allocated_to):
        return

    if doc.allocated_to != frappe.session.user:
        try:
            ticket = frappe.get_doc("HD Ticket", doc.reference_name)
            ticket.notify_agent(doc.allocated_to, "Assignment")
        except Exception:
            # An assignment must never fail because its notification did.
            frappe.log_error(
                title=f"HD assignment notification failed for {doc.reference_name}",
                message=frappe.get_traceback(),
            )

    try:
        send_thread_email(doc.reference_name, doc.allocated_to, "Assignment", doc.owner)
    except Exception:
        # An assignment must never fail because its email did.
        frappe.log_error(
            title=f"HD agent thread email failed for {doc.reference_name}",
            message=frappe.get_traceback(),
        )
