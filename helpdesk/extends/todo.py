import frappe

from helpdesk.helpdesk.utils.agent_email import send_thread_email


def after_insert(doc, method=None):
    """Email the assignee the ticket thread when a ticket is assigned.

    Hooked on ToDo rather than Notification Log because Frappe drops
    self-assignment notifications entirely: ``assign_to.notify_assignment``
    returns early when ``assigned_by == allocated_to``, and
    ``make_notification_logs`` skips any log whose ``for_user`` equals its
    ``from_user``. An agent who picks up a ticket themselves still wants it in
    their mailbox — and every assignment lands here, whether it came from an
    agent, an Assignment Rule, or the API.
    """
    if doc.reference_type != "HD Ticket":
        return
    if not (doc.reference_name and doc.allocated_to):
        return

    try:
        send_thread_email(doc.reference_name, doc.allocated_to, "Assignment", doc.owner)
    except Exception:
        # An assignment must never fail because its email did.
        frappe.log_error(
            title=f"HD agent thread email failed for {doc.reference_name}",
            message=frappe.get_traceback(),
        )
