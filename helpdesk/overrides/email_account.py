import re
from email import message_from_string
from email.utils import parseaddr

import frappe
from frappe import _
from frappe.core.doctype.communication.communication import Communication
from frappe.email.doctype.email_account.email_account import EmailAccount
from frappe.email.doctype.email_queue.email_queue import EmailQueue
from frappe.email.receive import InboundMail

from helpdesk.helpdesk.utils.agent_email import (
    _own_addresses,
    agent_user_for_email,
    is_email_reply_enabled,
    note_unrelayed_reply,
    relay_agent_reply,
    strip_reply,
)


class CustomInboundMail(InboundMail):
    """
    Extend InboundMail with robust thread stitching for forwarded emails.
       1. Run the standard Frappe parent_communication lookups first (In-Reply-To → Communication, EmailQueue, communication-name fallback)
       2. If still no parent, use the References header from emails, which may contain multiple message IDs in a thread

    It also recognises a reply sent by one of our own agents from their mailbox
    and records it as an agent reply rather than a message from the customer —
    see :meth:`_agent_reply_context`.
    """

    # None = not worked out yet, False = not an agent reply, tuple = it is one.
    _pyek_agent_reply = None
    _pyek_relay_ready = False
    # None = not worked out yet, True/False = cached answer.
    _pyek_self_echo = None

    def _is_self_echo(self) -> bool:
        """True when this inbound email was SENT BY one of the site's own
        helpdesk accounts (help.pyek@ / pos.pyek@).

        Our outbound replies come back into the mailbox whenever the thread
        carries an alias that delivers here (help@pyekgroup.com forwards into
        the help.pyek mailbox) or a reply-all CC's the account itself. Filed
        as a normal "Received" Communication, such an echo shows the same
        reply twice in the thread, reopens the ticket, stamps
        last_customer_response and fires a bogus Reply push ~10 minutes after
        every agent reply (measured on ticket 0171). Recognising the sender
        lets ingestion file it as an "Automated Message" instead — kept for
        audit, invisible in the thread, no side effects.
        """
        if self._pyek_self_echo is None:
            try:
                sender = (
                    getattr(self, "from_email", None)
                    or parseaddr(self.mail.get("From") or "")[1]
                )
                self._pyek_self_echo = (sender or "").lower() in _own_addresses()
            except Exception:
                frappe.log_error(
                    title=_("HD self-echo detection failed"),
                    message=frappe.get_traceback(),
                )
                self._pyek_self_echo = False
        return self._pyek_self_echo

    def _find_communication_by_message_id(self, msg_id: str):
        """Return a Communication for msg_id, checking both Communication and EmailQueue."""
        # Direct hit: incoming email stored its message_id on Communication
        comm = Communication.find_one_by_filters(
            message_id=msg_id, order_by="creation DESC"
        )
        if comm:
            return comm

        # Outgoing email: message_id lives in EmailQueue, not on Communication
        eq = EmailQueue.find_one_by_filters(message_id=msg_id)
        if eq and eq.communication:
            return Communication.find(eq.communication, ignore_error=True) or None

        return None

    def parent_communication(self):
        # Respect cached result from any prior call on this instance
        if self._parent_communication is not None:
            return self._parent_communication

        # Run the standard Frappe lookup method first. Checks for finding in reply to in Communication then if not found it looks in EmailQueue
        result = super().parent_communication()
        if result:
            return result

        # fallback: use the References header from emails
        references_raw = self.mail.get("References") or ""
        ref_ids = re.findall(r"<([^>]+)>", references_raw)

        for ref_id in reversed(ref_ids):
            communication = self._find_communication_by_message_id(ref_id)
            if communication:
                self._parent_communication = communication
                return self._parent_communication

        self._parent_communication = ""
        return self._parent_communication

    def _agent_reply_context(self):
        """``(ticket, agent_user)`` when this email is one of our own agents
        answering a ticket from their own mailbox, otherwise None.

        Frappe files every inbound email as ``sent_or_received = "Received"``,
        which for an agent's reply is backwards: it reopens the ticket, stamps
        ``last_customer_response`` and leaves the ticket looking unanswered.
        Recognising the sender lets us record it as the agent's reply instead —
        and pass it on to the requester, who is not a recipient of the
        notification the agent replied to.
        """
        if self._pyek_agent_reply is not None:
            return self._pyek_agent_reply or None

        context = None
        try:
            if is_email_reply_enabled():
                sender = (
                    getattr(self, "from_email", None)
                    or parseaddr(self.mail.get("From") or "")[1]
                )
                agent = agent_user_for_email(sender)
                if agent:
                    doc = self.reference_document()
                    if doc and doc.doctype == "HD Ticket":
                        context = (doc, agent)
        except Exception:
            frappe.log_error(
                title=_("Agent reply detection failed"),
                message=frappe.get_traceback(),
            )

        self._pyek_agent_reply = context or False
        return context

    def as_dict(self):
        # Our own outbound mail, echoed back via an alias or reply-all CC.
        # File it out of sight instead of letting it masquerade as a customer
        # reply (see _is_self_echo). Checked before the agent-reply context so
        # an echo can never be relayed back out again.
        if self._is_self_echo():
            data = super().as_dict()
            data["communication_type"] = "Automated Message"
            return data

        context = self._agent_reply_context()
        if not context:
            return super().as_dict()

        ticket, agent_user = context

        # Trim to what the agent actually typed BEFORE the parent builds the
        # doc: _build_communication_doc re-derives content from self.content
        # after insert, so stripping the doc afterwards would be undone.
        reply = strip_reply(getattr(self, "content", None))
        if reply:
            self.content = reply
            self._pyek_relay_ready = True

        data = super().as_dict()
        data["sent_or_received"] = "Sent"
        data["user"] = agent_user
        data["recipients"] = ticket.raised_by
        return data

    def process(self):
        communication = super().process()

        # A self-echo must never be relayed, even if the shared address were
        # ever (mis)configured as an agent alias — that would be a mail loop.
        if self._is_self_echo():
            return communication

        context = self._agent_reply_context()
        # is_new_communication is False when the same message is pulled twice —
        # relaying again would send the requester a duplicate.
        is_new = bool(getattr(self, "flags", None) and self.flags.is_new_communication)
        if context and communication and is_new:
            ticket = context[0]
            if self._pyek_relay_ready:
                relay_agent_reply(ticket, communication)
            else:
                # The reply marker never came back, so we cannot tell the
                # agent's words from the quoted thread (which carries internal
                # notes). File it, do not forward it, and say so on the ticket.
                note_unrelayed_reply(ticket, communication)

        return communication

    def match_record_by_subject_and_sender(self, doctype):
        """PYEK override — never merge a brand-new email onto an existing
        ticket just because their subject lines match.

        Frappe's default (frappe.email.receive.InboundMail) falls back to a
        fuzzy ``subject LIKE %..%`` match within a 60-day window when an email
        can't be threaded by reply headers — and for a sender who is a Frappe
        *system user* with a subject longer than 10 chars it drops the sender
        check and matches on subject ALONE. That silently swallowed unrelated
        new emails that happened to reuse a subject line ("Refund request",
        "POS down", etc.) into old, often-closed tickets.

        We keep ONLY the precise path: an explicit ticket name embedded in the
        subject (e.g. "... (#0042)"). Genuine replies still thread correctly
        via the In-Reply-To / References headers handled in
        ``parent_communication`` above. Everything else becomes a new ticket.
        """
        name = self.get_reference_name_from_subject()
        return self.get_doc(doctype, name, ignore_error=True) if name else None


class CustomEmailAccount(EmailAccount):
    def get_inbound_mails(self) -> list[InboundMail]:
        """retrive and return inbound mails."""
        mails = []

        def process_mail(messages, append_to=None):
            for index, message in enumerate(messages.get("latest_messages", [])):
                try:
                    _msg = message_from_string(
                        message.decode("utf-8", errors="replace")
                    )

                    # Important: If the email is auto-generated, we do not create a ticket
                    if _msg.get("X-Auto-Generated"):
                        continue

                    uid = (
                        messages["uid_list"][index]
                        if messages.get("uid_list")
                        else None
                    )
                    seen_status = messages.get("seen_status", {}).get(uid)
                    if self.email_sync_option != "UNSEEN" or seen_status != "SEEN":
                        _inbound_mail = CustomInboundMail(
                            message,
                            self,
                            frappe.safe_decode(uid),
                            seen_status,
                            append_to,
                        )
                        mails.append(_inbound_mail)
                except Exception as e:
                    # Log the error but continue processing other emails
                    frappe.log_error(
                        title=_(
                            "Error processing email at index {0}, message: {1}"
                        ).format(index, e),
                        message=frappe.get_traceback(),
                    )
                    self.handle_bad_emails(index, message, frappe.get_traceback())
                    continue

        if not self.enable_incoming:
            return []

        try:
            if self.service == "Frappe Mail":
                frappe_mail_client = self.get_frappe_mail_client()
                messages = frappe_mail_client.pull_raw(
                    last_received_at=self.last_synced_at
                )
                process_mail(messages)
                self.db_set(
                    "last_synced_at",
                    messages["last_received_at"],
                    update_modified=False,
                )
            else:
                email_sync_rule = self.build_email_sync_rule()
                email_server = self.get_incoming_server(
                    in_receive=True, email_sync_rule=email_sync_rule
                )
                if self.use_imap:
                    # process all given imap folder
                    for folder in self.imap_folder:
                        if email_server.select_imap_folder(folder.folder_name):
                            email_server.settings["uid_validity"] = folder.uidvalidity
                            messages = (
                                email_server.get_messages(
                                    folder=f'"{folder.folder_name}"'
                                )
                                or {}
                            )
                            process_mail(messages, folder.append_to)
                else:
                    # process the pop3 account
                    messages = email_server.get_messages() or {}
                    process_mail(messages)

                # close connection to mailserver
                email_server.logout()
        except Exception:
            self.log_error(
                title=_("Error while connecting to email account {0}").format(self.name)
            )
            return []

        return mails
