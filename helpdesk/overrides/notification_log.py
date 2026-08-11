import frappe
from frappe.desk.doctype.notification_log.notification_log import (
    NotificationLog,
    set_notifications_as_unseen,
)

from helpdesk.helpdesk.utils.agent_email import (
    send_thread_email,
    will_send_thread_email,
)


class CustomNotificationLog(NotificationLog):
    """Replace the framework's plain assignment/mention email with the ticket
    thread email, so an agent can work the ticket without opening the desk.

    Frappe's own notification email carries a one-line subject and a link and
    nothing else — and because it goes out with no ``reference_doctype`` and no
    ``communication`` on its Email Queue row, a reply to it cannot be traced
    back to the ticket and lands as a brand-new one. The thread email is sent
    as a Communication on the ticket, which is what makes replies thread.

    Assignments are sent from the ToDo hook (``helpdesk.extends.todo``), which
    also covers self-assignment — Frappe creates no Notification Log at all
    when you assign a ticket to yourself. This class only suppresses the
    duplicate for those, and sends the thread email itself for mentions, which
    create no ToDo.

    Only the email is replaced; the in-app notification is untouched. If the
    feature is off, or the recipient is not an active agent, nothing changes.
    """

    def after_insert(self):
        if self._pyek_handled():
            frappe.publish_realtime(
                "notification", after_commit=True, user=self.for_user
            )
            set_notifications_as_unseen(self.for_user)
            return

        super().after_insert()

    def _pyek_handled(self) -> bool:
        """True when the thread email covers this notification, so the
        framework's plain email would be a duplicate."""
        if self.document_type != "HD Ticket":
            return False
        if not (self.document_name and self.for_user):
            return False

        try:
            if self.type == "Assignment":
                # Sent from the ToDo hook, which fires for self-assignment too.
                return will_send_thread_email(self.for_user)
            if self.type == "Mention":
                # Mentions create no ToDo, so this is where they are sent.
                return send_thread_email(
                    self.document_name, self.for_user, self.type, self.from_user
                )
        except Exception:
            # Never let a notification failure break the assignment itself.
            frappe.log_error(
                title=f"HD agent thread email failed for {self.document_name}",
                message=frappe.get_traceback(),
            )

        return False
