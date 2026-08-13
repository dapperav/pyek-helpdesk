import frappe
from frappe.model.document import Document


class HDNotification(Document):
    def format_message(self):
        user_from = self.get_from()
        if self.notification_type == "Mention":
            if self.reference_comment:
                return f"{user_from} mentioned you in a comment"
            return f"{user_from} mentioned you"
        return ""

    def get_from(self):
        return frappe.db.get_value(
            "User", {"name": self.user_from}, fieldname="full_name"
        )

    def get_button_label(self):
        if self.reference_comment:
            return "See Comment"
        return "Visit"

    def get_url(self):
        res = "/helpdesk"
        if self.reference_ticket:
            res += "/tickets/" + str(self.reference_ticket)
        if self.reference_comment:
            res += "#" + self.reference_comment
        return frappe.utils.get_url(res)

    def parse_html(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(self.message, "html.parser")
        if soup.find("img"):
            img = soup.find("img")
            img["src"] = ("").join([frappe.utils.get_url(), img["src"]])
            return str(soup)
        return str(soup)

    def get_args(self):
        if self.notification_type == "Mention":
            return {
                "title": self.format_message(),
                "button_label": self.get_button_label(),
                "callback_url": self.get_url(),
                "comment": self.parse_html(),
            }

    def push_title(self):
        """One line for a lock screen. format_message() only covers Mention."""
        user_from = self.get_from() or "Someone"
        if self.notification_type == "Assignment":
            return "Assigned to you"
        if self.notification_type == "Mention":
            return f"{user_from} mentioned you"
        if self.notification_type == "Reaction":
            return f"{user_from} reacted"
        return "PYEKMAIL"

    def push_body(self):
        """Subject line, then what the ticket is actually about.

        The subject alone is often too terse to act on ("Mobaro Access", "TTH
        consignment"), so the second line is the enricher's `pyek_summary` — the
        one-line plain-English description it already writes for the AI panel.
        Reusing it costs nothing and is exactly the context you want before
        deciding whether to open the ticket on a phone.

        Two lines rather than one because iOS shows the first collapsed and the
        rest when the notification is expanded, so the subject always survives
        truncation and the summary is there if you want it.
        """
        if not self.reference_ticket:
            return self.format_message() or ""

        ticket = (
            frappe.db.get_value(
                "HD Ticket",
                self.reference_ticket,
                ["subject", "pyek_summary"],
                as_dict=True,
            )
            or {}
        )

        head = (
            f"#{self.reference_ticket} · {ticket.get('subject')}"
            if ticket.get("subject")
            else f"Ticket #{self.reference_ticket}"
        )

        summary = (ticket.get("pyek_summary") or "").strip()
        if not summary:
            # No AI summary: automated senders are skipped by design, and older
            # tickets predate enrichment. The subject line still stands alone.
            return head

        # Keep it to a sensible lock-screen length; the full text is in the app.
        if len(summary) > 180:
            summary = summary[:179].rstrip() + "…"
        return f"{head}\n{summary}"

    def send_web_push(self):
        """Every notification type routes through here.

        This is the single hook for push precisely because assignment, mention
        and reaction all create an HD Notification — hooking each producer
        instead would have meant three places to keep in step.

        Wrapped: a push failure must never roll back the assignment that caused
        it. notify_user only enqueues, but the enqueue itself can throw if Redis
        is unhappy.
        """
        try:
            from helpdesk.helpdesk.web_push import notify_user

            notify_user(
                user=self.user_to,
                title=self.push_title(),
                body=self.push_body(),
                # Reuses the same deep link the mention email already uses, so a
                # tap lands on the ticket (and the comment) rather than the inbox.
                url=self.get_url(),
                # Collapse per ticket: ten updates on one ticket shouldn't stack
                # ten notifications on a lock screen.
                tag=f"ticket-{self.reference_ticket or self.name}",
            )
        except Exception:
            frappe.log_error(
                title="PMIT push: could not queue notification",
                message=frappe.get_traceback(),
            )

    def after_insert(self):
        self.send_web_push()

        if self.notification_type == "Mention":
            skip_email_workflow = frappe.db.get_single_value(
                "HD Settings", "skip_email_workflow"
            )

            if skip_email_workflow:
                return

            frappe.sendmail(
                recipients=self.user_to,
                subject="New notification",
                message=self.format_message(),
                template="notification",
                args=self.get_args(),
            )
