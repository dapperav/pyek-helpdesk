import json
import re
import uuid
from datetime import timedelta
from email.utils import parseaddr
from html import escape as html_escape
from zoneinfo import ZoneInfo

import frappe
from bs4 import BeautifulSoup, Comment
from frappe import _
from frappe.core.page.permission_manager.permission_manager import remove
from frappe.desk.form.assign_to import add as assign
from frappe.desk.form.assign_to import clear as clear_all_assignments
from frappe.desk.form.assign_to import get as get_assignees
from frappe.model.document import Document
from frappe.permissions import add_permission, update_permission_property
from frappe.query_builder import DocType, Order
from frappe.utils import add_to_date, cint, get_datetime, getdate, now_datetime
from pypika.functions import Count
from pypika.queries import Query
from pypika.terms import Criterion

from helpdesk.helpdesk.doctype.hd_settings.helpers import (
    get_default_email_content,
    is_email_content_empty,
)
from helpdesk.helpdesk.doctype.hd_ticket_activity.hd_ticket_activity import (
    log_ticket_activity,
)
from helpdesk.helpdesk.utils import echo
from helpdesk.helpdesk.utils.email import (
    default_outgoing_email_account,
    default_ticket_outgoing_email_account,
)
from helpdesk.utils import (
    capture_event,
    get_agents_team,
    get_customers,
    get_doc_room,
    is_admin,
    is_agent,
    publish_event,
)

from ..hd_notification.utils import clear as clear_notifications
from ..hd_service_level_agreement.utils import get_sla

# Automated/bot senders and subjects whose inbound mail should NOT get a
# "We've received your request" auto-acknowledgement — the same traffic the AI
# enricher skips (no-reply monitoring, refund work orders, auto-replies, bounces).
# Sending an ack to these just bounces noise back at no-reply mailboxes or loops
# into work-order inboxes. These generic defaults intentionally mirror the
# enricher's built-ins (the two repos are independent, so kept in sync by hand);
# org-specific patterns live in the HD Settings fields pyek_ai_excluded_senders /
# pyek_ai_excluded_subjects and are unioned in at runtime.
_AUTOMATED_SENDER_DEFAULTS = (
    "no-reply@",
    "noreply@",
    "no_reply@",
    "do-not-reply@",
    "donotreply@",
    "mailer-daemon@",
    "postmaster@",
    "notifications@",
    "notification@",
)
_AUTOMATED_SUBJECT_DEFAULTS = (
    "automatic reply",
    "out of office",
    "undeliverable",
    "delivery status notification",
    "mail delivery failed",
    "returning online",
)


# Deferred acknowledgement (see _defer_or_send_acknowledgement). The requester's one
# email says what we understood the request to be, which needs the AI enricher's
# pyek_summary — written by a separate worker up to a minute after insert. So the ack
# is marked pending here and sent by send_pending_acknowledgements() once the summary
# lands. pyek_ack_state is a hidden Custom Field provisioned by the enricher repo's
# setup_ack_state.py; tickets predating it read back NULL and are never picked up.
ACK_STATE_FIELD = "pyek_ack_state"
ACK_PENDING = "pending"
ACK_SENT = "sent"
ACK_FALLBACK = "fallback"
# How long to wait for enrichment before giving up and sending the plain
# acknowledgement instead. The enricher polls every 60s; this leaves room for a
# retry or a briefly-down worker without leaving the requester in silence.
# Cut from 5 minutes to 90s on 2026-08-20: five minutes plus a wait for the next
# scheduler tick put the requester's confirmation ~8 minutes behind their email
# (measured on ticket 0493), and every hop is meant to be under two. 90s is
# still ample — enrichment on 0493 finished 45 seconds after insert — and the
# sweep now also runs every 60s off the enricher's poke (helpdesk.api.mail_tick),
# so a ticket enriched at t+50s is still acknowledged WITH its summary.
ACK_ENRICHMENT_GRACE_SECONDS = 90
# Bound the sweep so one slow cycle can't fan out into a huge mail batch.
ACK_SWEEP_BATCH = 50

# --- Ubiquiti camera-drop auto-close -----------------------------------------
# Ubiquiti mail is 106 of 314 tickets on this site, and 64 of those are a single
# camera dropping and reconnecting: "Typhoon Texas Austin NVR's Cash Control has
# gone offline." Nobody triages them, but they carry an SLA, so they were the
# largest single contributor to SLA failure (63% of all failures came from
# machine senders). They are closed on arrival instead.
#
# The match is deliberately NARROW and matches the POSSESSIVE form only. "the
# NVR's Front Gate Scanner" is one camera; a bare "NVR has gone offline" would be
# the recorder itself, and "Cowabunga Bay: Shadow Console Disconnected" is a whole
# site — both must stay open, and neither matches. Anything unrecognised stays a
# normal ticket, so an alert shape we have never seen fails safe rather than
# closing silently. Validated against all 106 real Ubiquiti tickets: 64 match, and
# every one of them is an offline/reconnected camera event.
AUTO_CLOSE_SENDER_HINT = "ui.com"
AUTO_CLOSE_SUBJECT_RE = re.compile(r"NVR['’ʼ]s\b", re.IGNORECASE)
AUTO_CLOSE_FIELD = "pyek_auto_closed"

# The marker paragraph every quoted reply carries. The composers emit it
# (EmailEditor.vue, MobileReplyFlow.submitCompose) and hide it in the editor
# via [&_p.reply-to-content]:hidden; reply_via_agent reads it as "this message
# already carries a quote", so a composer reply never gets quoted twice.
QUOTED_REPLY_MARKER = "reply-to-content"

# _QUOTE_HEADER in hd_ticket/api.py matches `^on .{0,140}wrote:?$` to cut the
# attribution line out of an agent-facing bubble. Keep name + address well
# inside that budget: an attribution that failed to match would surface as a
# stray line above every quoted reply in the thread.
QUOTE_ATTRIBUTION_MAX = 90


def _split_ack_patterns(raw) -> list:
    """Split a newline/comma-separated HD Settings pattern string into normalized
    lowercase entries (mirrors the enricher's config.parse_sender_patterns)."""
    if not raw:
        return []
    out = []
    for chunk in str(raw).replace("\n", ",").split(","):
        p = chunk.strip().lower()
        if p:
            out.append(p)
    return out


class HDTicket(Document):
    @property
    def default_open_status(self):
        return frappe.db.get_value(
            "HD Service Level Agreement",
            self.sla,
            "default_ticket_status",
        ) or frappe.db.get_single_value("HD Settings", "default_ticket_status")

    @property
    def ticket_reopen_status(self):
        return frappe.db.get_value(
            "HD Service Level Agreement",
            self.sla,
            "ticket_reopen_status",
        ) or frappe.db.get_single_value("HD Settings", "ticket_reopen_status")

    def publish_update(self):
        room = get_doc_room("HD Ticket", self.name)
        publish_event(
            "helpdesk:ticket-update", room=room, data={"ticket_id": self.name}
        )

    def autoname(self):
        return self.name

    def before_insert(self):
        self.generate_key()

    def before_validate(self):
        self.check_update_perms()
        self.set_ticket_type()
        self.set_raised_by()
        self.set_priority()
        self.set_first_responded_on()
        self.set_feedback_values()
        self.set_default_status()
        self.set_status_category()
        self.set_sla()

        self.validate_portal_contact()
        self.set_contact()
        self.set_customer()

    def validate(self):
        self.validate_feedback()

    def before_save(self):
        self.apply_sla()
        if not self.is_new():
            self.handle_ticket_activity_update()

        self.handle_email_feedback()
        if self.is_new():
            self.raised_outside_working_hours = (
                self.is_currently_outside_working_hours()
            )

    def _get_rendered_template(
        self, content: str, default_content: str, args: dict[str, str] | None = None
    ):
        if args is None:
            args = dict()
        template_args = {
            "doc": self.as_dict(),
        }
        for key, value in args.items():
            template_args[key] = value
        return frappe.render_template(
            default_content if is_email_content_empty(content) else content,
            template_args,
        )

    def handle_email_feedback(self):
        if (
            self.is_new()
            or self.via_customer_portal
            or self.feedback_rating
            or not self.has_value_changed("status")
            or not self.key
        ):
            return

        [is_email_feedback_enabled, email_feedback_status] = frappe.get_cached_value(
            "HD Settings",
            "HD Settings",
            ["enable_email_ticket_feedback", "send_email_feedback_on_status"],
        )

        send_feedback_email = int(is_email_feedback_enabled) and (
            email_feedback_status == self.status
            or email_feedback_status == ""
            and self.status == "Closed"
        )

        if not send_feedback_email:
            return

        last_communication = self.get_last_communication()

        url = f"{frappe.utils.get_url()}/ticket-feedback/new?key={self.key}"
        feedback_email_content = frappe.db.get_single_value(
            "HD Settings", "feedback_email_content"
        )
        default_feedback_email_content = get_default_email_content("share_feedback")
        try:
            frappe.sendmail(
                recipients=[self.raised_by],
                subject=self.outgoing_subject(),
                message=self._get_rendered_template(
                    feedback_email_content,
                    default_feedback_email_content,
                    {"url": url},
                ),
                reference_doctype="HD Ticket",
                reference_name=self.name,
                now=True,
                in_reply_to=last_communication.name if last_communication else None,
                email_headers={"X-Auto-Generated": "hd-email-feedback"},
            )
            frappe.msgprint(_("Feedback email has been sent to the customer"))
        except Exception as e:
            frappe.throw(_("Could not send feedback email,due to: {0}").format(e))

    def after_insert(self):

        # Telemetry Event
        self.capture_ticket_created_telemetry_events()
        publish_event("helpdesk:new-ticket")

        if self.get("description"):
            self.create_communication_via_contact(self.description, new_ticket=True)
            self.handle_inline_media_new_ticket()

        self._auto_close_if_camera_alert()

        send_ack_email = frappe.db.get_single_value(
            "HD Settings", "send_acknowledgement_email"
        )
        if (
            not self.via_customer_portal
            and not frappe.flags.initial_sync
            and send_ack_email
            and not self._suppress_acknowledgement()
        ):
            self._defer_or_send_acknowledgement()

    def capture_ticket_created_telemetry_events(self):
        if self.subject == "Welcome to Helpdesk":
            return

        capture_event("ticket_created")
        if not self.via_customer_portal:
            capture_event("ticket_created_via_email")
        if self.via_customer_portal and not is_agent():
            capture_event("ticket_created_via_customer")

        if self.ticket_split_from:
            log_ticket_activity(
                self.name,
                "split the ticket from #{0}".format(self.ticket_split_from),
            )
            capture_event("ticket_split")

    def on_update(self):
        # flake8: noqa
        if self.status_category == "Open":
            if (
                self.get_doc_before_save()
                and self.get_doc_before_save().status_category != "Open"
            ):
                agents = self.get_assigned_agents()
                if agents:
                    for agent in agents:
                        if agent.name == frappe.session.user:
                            continue
                        self.notify_agent(agent.name, "Reaction")

        self.remove_assignment_if_not_in_team()
        self.notify_team_of_new_ticket()
        self.publish_update()
        self.capture_update_telemetry_events()

    def notify_team_of_new_ticket(self):
        """Tell a team's members when a ticket lands in their queue.

        Hooked on agent_group CHANGING rather than after_insert, because the team
        is not populated at insert — routing sets it moments later. Measured on
        this site: 264 of 266 tickets over 14 days end up with a team, so the
        signal is reliable; it just arrives on an update. A useful side effect is
        that moving a ticket between teams notifies the receiving team, which is
        what you'd want anyway.

        HUMAN TICKETS ONLY, and that filter is the difference between a feature
        people keep and one they mute. Measured over the same 14 days: IT Support
        took 140 tickets of which 121 were automated (Ubiquiti monitoring, config
        reports), and POS took 124 of which 71 were automated ([BR-] refund work
        orders). Notifying on everything would be ~10 pushes a day at 86% noise
        for IT. Filtered, it's ~1.4/day for IT and ~3.8/day for POS.
        Mark chose human-only when asked.

        Dedupe rides on HD Notification itself rather than a new flag: an existing
        Team row for this (user, ticket) means they've already been told. On a
        genuine team move the receiving team has no such row, so they get notified
        while the previous team is not told twice.
        """
        if not self.agent_group or not self.has_value_changed("agent_group"):
            return
        # A ticket that arrived already closed (camera-drop auto-close) is not news.
        if self.status_category == "Resolved" or self.get(AUTO_CLOSE_FIELD):
            return
        # Same senders/subjects the enricher and the auto-ack skip. Fails open, so
        # an unrecognised sender still notifies — a stray push beats a missed ticket.
        if self._suppress_acknowledgement():
            return

        try:
            members = [
                row.user
                for row in frappe.get_doc("HD Team", self.agent_group).users
                if row.user
            ]
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), "HD team notification: team lookup failed"
            )
            return

        for user in members:
            # Whoever just routed the ticket doesn't need telling about it.
            if user == frappe.session.user:
                continue
            if frappe.db.exists(
                "HD Notification",
                {
                    "reference_ticket": self.name,
                    "user_to": user,
                    "notification_type": "Team",
                },
            ):
                continue
            self.notify_agent(user, "Team")

    def notify_assignees_of_reply(self, c):
        """Tell the people working a ticket that the requester has replied.

        Only for inbound mail: an agent's own outgoing reply is handled by the
        caller's "Sent" branch and obviously shouldn't notify them. Not deduped —
        every reply is new information — but the push collapses per ticket, so a
        fast back-and-forth replaces itself on the lock screen instead of stacking.
        """
        if c.sent_or_received != "Received":
            return
        if c.communication_type == "Automated Message":
            return
        try:
            for agent in self.get_assigned_agents():
                if agent.name == frappe.session.user:
                    continue
                self.notify_agent(agent.name, "Reply")
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), "HD reply notification failed"
            )

    def notify_agent(self, agent, notification_type="Assignment"):
        frappe.get_doc(
            frappe._dict(
                doctype="HD Notification",
                user_from=frappe.session.user,
                reference_ticket=self.name,
                user_to=agent,
                notification_type=notification_type,
            )
        ).insert(ignore_permissions=True)

    def capture_update_telemetry_events(self):
        capture_event("ticket_updated")

        if self.has_value_changed("status"):
            capture_event("ticket_status_updated")
        if (
            self.has_value_changed("status_category")
            and self.status_category == "Resolved"
        ):
            capture_event("ticket_resolved")

    def set_ticket_type(self):
        if self.ticket_type:
            return
        self.ticket_type = (
            frappe.db.get_single_value("HD Settings", "default_ticket_type") or ""
        )

    def set_raised_by(self):
        if self.raised_by:
            return
        self.raised_by = frappe.session.user

    def validate_portal_contact(self) -> None:
        """Block non-agent users from attributing a ticket to another contact.

        Agents are unrestricted, and so are system channels like email intake,
        which run as Administrator.
        """
        if is_agent():
            return
        if not self.contact:
            return
        if not self.is_new() and not self.has_value_changed("contact"):
            return

        if self.contact != self.get_session_contact():
            frappe.throw(
                _("You can only raise tickets for your own contact."),
                frappe.PermissionError,
            )

    def get_session_contact(self) -> str | None:
        """Resolve the Contact owned by the current session user.

        Match strictly on the ``user`` link. Fall back to the email only when
        it is the session user's own verified email and the Contact is not
        already linked to a different user, so an unrelated record that merely
        shares the email can never satisfy the ownership check.
        """
        contact = frappe.db.get_value("Contact", {"user": frappe.session.user})
        if contact:
            return contact

        user_email = frappe.db.get_value("User", frappe.session.user, "email")
        if not user_email:
            return None
        return frappe.db.get_value(
            "Contact", {"email_id": user_email, "user": ("in", ("", None))}
        )

    def set_contact(self):
        email_id = parseaddr(self.raised_by)[1]
        # flake8: noqa
        if email_id:
            if not self.contact:
                contact = frappe.db.get_value("Contact", {"email_id": email_id})
                if contact:
                    self.contact = contact

    def set_customer(self):
        if not frappe.db.get_single_value(
            "HD Settings", "auto_set_customer_from_contact"
        ):
            return

        # For existing tickets, only validate if customer value has changed
        if not self.is_new() and not self.has_value_changed("customer"):
            return

        contact_customers = get_customers(contact=self.contact) if self.contact else []

        if self.customer:
            if self.customer not in contact_customers and not is_agent():
                frappe.throw(
                    _(
                        "The selected customer {0} is not linked to the contact {1}."
                        "Please select a valid customer or update the contact's linked customers."
                    ).format(self.customer, self.contact),
                    frappe.ValidationError,
                )
            return

        # Auto-set customer only for new tickets
        if self.is_new() and self.contact:
            if len(contact_customers) == 1:
                self.customer = contact_customers[0]
            elif (
                len(contact_customers) > 1
                and not is_agent()
                and self.via_customer_portal
            ):
                frappe.throw(
                    _(
                        "The contact {0} is linked to multiple customers. Please select the customer manually."
                    ).format(self.contact),
                    frappe.ValidationError,
                )

    def set_priority(self):
        if self.priority:
            return
        self.priority = frappe.get_cached_value(
            "HD Ticket Type", self.ticket_type, "priority"
        ) or frappe.get_cached_value("HD Settings", "HD Settings", "default_priority")

    def set_first_responded_on(self):
        if self.is_new():
            return
        if self.first_responded_on:
            return

        old_status_category = (
            self.get_doc_before_save().status_category
            if self.get_doc_before_save()
            else None
        )
        is_closed_or_resolved = (
            old_status_category == "Open" and self.status_category == "Resolved"
        )

        if self.status_category == "Paused" or is_closed_or_resolved:
            self.first_responded_on = frappe.utils.now_datetime()

    def set_feedback_values(self):
        if not self.feedback:
            return
        feedback_option = frappe.get_doc("HD Ticket Feedback Option", self.feedback)
        self.feedback_rating = feedback_option.rating

    @property
    def has_agent_replied(self):
        return frappe.db.exists(
            "Communication",
            {
                "reference_doctype": "HD Ticket",
                "reference_name": self.name,
                "sent_or_received": "Sent",
            },
        )

    def validate_feedback(self):
        is_feedback_mandatory = frappe.get_cached_value(
            "HD Settings", "HD Settings", "is_feedback_mandatory"
        )
        if (
            self.feedback_rating
            or self.status_category != "Resolved"
            or is_agent()
            or not self.has_agent_replied
            or not is_feedback_mandatory
        ):
            return

        frappe.throw(
            _("Ticket must be resolved with a feedback"), frappe.ValidationError
        )

    def check_update_perms(self):
        if self.is_new() or is_agent() or not self.via_customer_portal:
            return
        old_doc = self.get_doc_before_save()
        is_closed = old_doc.status == "Closed"
        is_rated = bool(old_doc.feedback)
        if is_closed or is_rated:
            text = _("Closed or rated tickets cannot be updated by non-agents")
            frappe.throw(text, frappe.PermissionError)

    def handle_ticket_activity_update(self):
        """
        Handles the ticket activity update.
        Should be called inside on_update
        """
        field_maps = {
            "status": "status",
            "priority": "priority",
            "agent_group": "team",
            "ticket_type": "type",
            "contact": "contact",
            "sla": "SLA",
        }
        for field in [
            "status",
            "priority",
            "agent_group",
            "contact",
            "ticket_type",
            "sla",
        ]:
            if self.has_value_changed(field):
                value = self.as_dict()[field]
                if not value:
                    msg = f"cleared {field_maps[field]}"
                else:
                    msg = f"set {field_maps[field]} to {value}"

                log_ticket_activity(self.name, msg)

    def generate_key(self):
        self.key = uuid.uuid4()

    def remove_assignment_if_not_in_team(self):
        """
        Removes the assignment if the agent is not in the team.
        Should be called inside on_update
        """
        if self.is_new():
            return
        if not self.agent_group or (hasattr(self, "_assign") and not self._assign):
            return
        if self.has_value_changed("agent_group") and self.status_category == "Open":
            current_assigned_agent = self.get_assigned_agent()
            if not current_assigned_agent:
                return
            is_agent_in_assigned_team = self.agent_in_assigned_team(
                current_assigned_agent, self.agent_group
            )

            if (
                not is_agent_in_assigned_team
            ) and self.users_present_in_team_assignment_rule():
                clear_all_assignments("HD Ticket", self.name)

    def agent_in_assigned_team(self, agent, team):
        return frappe.db.exists(
            "HD Team Member",
            {
                "parent": team,
                "user": agent,
            },
        )

    def users_present_in_team_assignment_rule(self):
        if not self.agent_group:
            return False

        assignment_rule = frappe.db.get_value(
            "HD Team", self.agent_group, "assignment_rule"
        )
        if not assignment_rule:
            return False

        is_disabled = frappe.db.get_value(
            "Assignment Rule", assignment_rule, "disabled"
        )
        if is_disabled:
            return False

        users = frappe.get_all(
            "Assignment Rule User", filters={"parent": assignment_rule}
        )
        if not users:
            return False

        return True

    @frappe.whitelist()
    def assign_agent(self, agent: str):
        # The Assignment HD Notification (and its push) is created by the ToDo
        # after_insert hook (helpdesk/extends/todo.py), which fires for EVERY
        # assignment path — including the UI's frappe.desk.form.assign_to.add,
        # which never comes through here. Notifying here too would double-ping
        # this one path (2026-08-17).
        assign({"assign_to": [agent], "doctype": "HD Ticket", "name": self.name})

    def get_assigned_agents(self):
        assignees = get_assignees({"doctype": "HD Ticket", "name": self.name})
        if len(assignees) > 0:
            names = [assignee.owner for assignee in assignees]
            return frappe.get_all("HD Agent", filters={"name": ["in", names]})
        # An unassigned ticket must read as "no agents", not None — callers
        # iterate this (notify_assignees_of_reply was logging a TypeError on
        # every requester reply to an unassigned ticket).
        return []

    def get_assigned_agent(self):
        # TODO: deprecate this
        # for some reason _assign is not set, maybe a framework bug?
        if hasattr(self, "_assign") and self._assign:
            assignees = json.loads(self._assign)
            if len(assignees) > 0:
                # TODO: temporary fix, remove this when only agents can be assigned to ticket
                exists = frappe.db.exists("HD Agent", assignees[0])
                if exists:
                    return assignees[0]

        assignees = get_assignees({"doctype": "HD Ticket", "name": self.name})
        if len(assignees) > 0:
            # TODO: temporary fix, remove this when only agents can be assigned to ticket
            return frappe.db.exists("HD Agent", assignees[0].owner)

        return None

    def on_trash(self):
        activities = frappe.db.get_all("HD Ticket Activity", {"ticket": self.name})
        for activity in activities:
            frappe.db.delete("HD Ticket Activity", activity)

        comments = frappe.db.get_all(
            "HD Ticket Comment", {"reference_ticket": self.name}
        )
        for comment in comments:
            frappe.db.delete("HD Ticket Comment", comment)

    def skip_email_workflow(self):
        skip: str = frappe.get_value("HD Settings", None, "skip_email_workflow") or "0"

        return bool(int(skip))

    def _resolve_sender_email(self, email_account_name, from_email_id):
        if not email_account_name:
            sender_email = self.sender_email()
            return sender_email, (sender_email.name if sender_email else None)

        if not frappe.db.exists("Email Account", email_account_name):
            frappe.throw(_("No Email Account found for {0}").format(from_email_id))

        sender_email = frappe._dict(name=email_account_name, email_id=from_email_id)
        return sender_email, email_account_name

    def instantly_send_email(self):
        check: str = (
            frappe.get_value("HD Settings", None, "instantly_send_email") or "0"
        )

        return bool(int(check))

    @frappe.whitelist()
    def get_last_communication(self):
        filters = {
            "reference_doctype": "HD Ticket",
            "reference_name": ["=", str(self.name)],
        }

        try:
            communication = frappe.get_last_doc(
                "Communication",
                filters=filters,
            )

            return communication
        except Exception:
            return None

    def last_communication_email(self):
        if not (communication := self.get_last_communication()):
            return

        if not communication.email_account:
            return

        email_account = frappe.get_doc("Email Account", communication.email_account)

        if not email_account.enable_outgoing:
            return

        return email_account

    def ticket_email_account(self):
        """The inbox this ticket arrived on, when it is able to send."""
        if not self.email_account:
            return

        if not frappe.db.exists("Email Account", self.email_account):
            return

        email_account = frappe.get_doc("Email Account", self.email_account)

        if not email_account.enable_outgoing:
            return

        return email_account

    def sender_email(self):
        """
        Find an email to use as sender. Fall back through multiple choices

        :return: `Email Account`
        """
        # The ticket's own inbox comes first. Keying on the newest message
        # instead let the account drift: an Echo acknowledgement goes out on
        # the IT account, so a POS ticket whose last message was automated
        # answered from help.pyek@ rather than pos.pyek@. That put 5 of 109
        # POS replies on the wrong address between 8/6 and 8/22 (tickets 0272,
        # 0379, 0381, 0558) — the requester sees an address they don't
        # recognise, and their answer lands back in the IT queue.
        if email_account := self.ticket_email_account():
            return email_account

        if email_account := self.last_communication_email():
            return email_account

        if email_account := default_ticket_outgoing_email_account():
            return email_account

        if email_account := default_outgoing_email_account():
            return email_account

    def outgoing_subject(self) -> str:
        """The subject every requester-facing email on this ticket carries.

        The trailing `(#name)` is Frappe's own inbound convention —
        `InboundMail.get_reference_name_from_subject` reads
        `subject.rsplit("#", 1)[-1].strip(" ()")` — so the reference has to sit
        LAST or a ticket whose own subject contains a '#' wins the split. It
        also hands Outlook a distinct conversation topic per ticket, which is
        the point: Brittany Estes had three open tickets all titled "TTH
        consignment" on 2026-08-24, and every reply collapsed into one
        indistinguishable thread.

        utils/agent_email.py builds the same string for relayed agent mail;
        keep the two in step.
        """
        return f"Re: {self.subject} (#{self.name})"

    def _last_inbound_communication(self):
        rows = frappe.get_all(
            "Communication",
            filters={
                "reference_doctype": "HD Ticket",
                "reference_name": self.name,
                "communication_type": "Communication",
                "sent_or_received": "Received",
            },
            fields=[
                "content",
                "sender",
                "sender_full_name",
                "communication_date",
                "creation",
            ],
            order_by="creation desc",
            limit=1,
        )
        return rows[0] if rows else None

    @staticmethod
    def _quote_timestamp(value) -> str:
        if not value:
            return ""
        try:
            dt = get_datetime(value)
        except Exception:
            return ""
        # %-I is not portable, so strip the leading zero by hand.
        hour = dt.strftime("%I").lstrip("0") or "12"
        stamp = f"{dt.strftime('%b %d, %Y')} at {hour}:{dt.strftime('%M %p')}"
        # Communication timestamps are stored in the SITE timezone, which is
        # not the reader's — this desk already shipped an hour-off bug from
        # exactly that gap (2026-08-20). Naming the zone costs four characters
        # and makes the quote unambiguous instead of quietly wrong.
        try:
            zone = ZoneInfo(frappe.utils.get_system_timezone())
            if abbreviation := dt.replace(tzinfo=zone).strftime("%Z"):
                stamp = f"{stamp} {abbreviation}"
        except Exception:
            pass
        return stamp

    @staticmethod
    def _quote_attribution(comm) -> str:
        name = (comm.get("sender_full_name") or "").strip()
        address = (comm.get("sender") or "").strip()
        who = f"{name} <{address}>" if name and address else (name or address)
        if len(who) > QUOTE_ATTRIBUTION_MAX:
            who = name or address
        when = HDTicket._quote_timestamp(
            comm.get("communication_date") or comm.get("creation")
        )
        said = ", ".join(part for part in (when, who) if part)
        if not said:
            return ""
        return f"On {said} wrote:"

    def quoted_thread_html(self) -> str:
        """The requester's own last message, quoted under a new reply.

        The quick reply bars send a bare line — "Done!" and nothing else — so a
        requester with three same-subject tickets open cannot tell which one
        was answered (Brittany Estes, 2026-08-24). The full composer has always
        appended this block client-side; building it server-side means every
        surface quotes, including any added later.

        Both pieces are load-bearing downstream: `_visible_lines` in
        hd_ticket/api.py decomposes the <blockquote> and `_QUOTE_HEADER` cuts
        the attribution, so agent-facing bubbles stay exactly as short as they
        are today while the outgoing email carries the history.

        Only RECEIVED mail is ever quoted, so our own replies can't compound
        into an ever-growing chain of themselves.
        """
        comm = self._last_inbound_communication()
        if not comm or not (comm.get("content") or "").strip():
            return ""

        attribution = self._quote_attribution(comm)
        header = f"<p>{html_escape(attribution)}</p>" if attribution else ""
        return (
            f'<p class="{QUOTED_REPLY_MARKER}"></p>'
            f"{header}"
            f"<blockquote>{comm['content']}</blockquote>"
        )

    @property
    def portal_uri(self):
        root_uri = frappe.utils.get_url()
        return f"{root_uri}/helpdesk/my-tickets/{self.name}"

    @frappe.whitelist()
    def new_comment(self, content: str, attachments: list[str] = []):
        if not is_agent():
            frappe.throw(
                _("You are not permitted to add a comment"), frappe.PermissionError
            )
        c = frappe.new_doc("HD Ticket Comment")
        c.commented_by = frappe.session.user
        c.content = content
        c.is_pinned = False
        c.reference_ticket = self.name
        c.save()
        for attachment in attachments:
            self.attach_file_with_doc(
                "HD Ticket Comment", c.name, attachment.get("file_url")
            )

    @frappe.whitelist()
    def reply_via_agent(
        self,
        message: str,
        from_email: dict | None = None,
        to: str | None = None,
        cc: str | None = None,
        bcc: str | None = None,
        attachments: list[str] = [],
    ):
        if not is_agent():
            frappe.throw(
                _("You are not permitted to reply as an agent"), frappe.PermissionError
            )
        skip_email_workflow = self.skip_email_workflow()
        medium = "" if skip_email_workflow else "Email"
        subject = self.outgoing_subject()

        # The quick reply bars send only what the agent typed; the full
        # composer appends its own quote client-side and marks it. Fill the gap
        # here, before the Communication is built, so the stored thread and the
        # outgoing email say the same thing.
        if not skip_email_workflow and QUOTED_REPLY_MARKER not in (message or ""):
            message = (message or "") + self.quoted_thread_html()

        from_email_id = from_email.get("email_id") if from_email else None
        email_account_name = from_email.get("email_account") if from_email else None
        sender = from_email_id or frappe.session.user
        recipients = to

        sender_email = None
        if not skip_email_workflow:
            sender_email, email_account_name = self._resolve_sender_email(
                email_account_name, from_email_id
            )

        if recipients == "Administrator":
            recipients = frappe.get_value("User", "Administrator", "email")

        communication = frappe.get_doc(
            {
                "bcc": bcc,
                "cc": cc,
                "communication_medium": medium,
                "communication_type": "Communication",
                "content": message,
                "doctype": "Communication",
                "email_account": email_account_name,
                "email_status": "Open",
                "recipients": recipients,
                "reference_doctype": "HD Ticket",
                "reference_name": self.name,
                "sender": sender,
                "sent_or_received": "Sent",
                "status": "Linked",
                "subject": subject,
            }
        )

        last_communication = self.get_last_communication()
        if last_communication and last_communication.message_id:
            communication.in_reply_to = last_communication.name

        communication.insert(ignore_permissions=True)
        capture_event("agent_replied")

        _attachments = []

        for attachment in attachments:
            file_url = frappe.db.get_value("File", attachment, "file_url")
            self.attach_file_with_doc("Communication", communication.name, file_url)
            self.attach_file_with_doc("HD Ticket", self.name, file_url)
            _attachments.append({"file_url": file_url})

        if skip_email_workflow or not frappe.db.get_single_value(
            "HD Settings", "enable_reply_email_via_agent"
        ):
            return

        if not sender_email:
            frappe.throw(
                _("Unable to send email. Please setup default outgoing email account.")
            )

        message = self.parse_content(message)

        reply_to_email = sender_email.email_id
        rendered_template: str | None = None
        if self.via_customer_portal:
            email_content = frappe.db.get_single_value(
                "HD Settings", "reply_via_agent_email_content"
            )
            default_email_content = get_default_email_content("reply_via_agent")
            try:
                rendered_template = self._get_rendered_template(
                    email_content,
                    default_email_content,
                    {"message": message, "ticket_url": self.portal_uri},
                )
            except Exception as e:
                frappe.throw(_("Could not an email due to: {0}").format(e))

        send_delayed = True
        send_now = False

        if self.instantly_send_email():
            send_delayed = False
            send_now = True

        try:
            frappe.sendmail(
                attachments=_attachments,
                bcc=bcc,
                cc=cc,
                communication=communication.name,
                delayed=send_delayed,
                expose_recipients="header",
                message=rendered_template if rendered_template is not None else message,
                as_markdown=True,
                now=send_now,
                recipients=recipients,
                reference_doctype="HD Ticket",
                reference_name=self.name,
                reply_to=reply_to_email,
                sender=reply_to_email,
                subject=subject,
                with_container=False,
                in_reply_to=last_communication.name if last_communication else None,
            )
        except Exception as e:
            frappe.throw(str(e))

    @frappe.whitelist()
    # flake8: noqa
    def create_communication_via_contact(
        self, message: str, attachments: list[dict] = [], new_ticket: bool = False
    ):
        if not new_ticket and frappe.db.get_single_value(
            "HD Settings", "enable_reply_email_to_agent"
        ):
            # send email to assigned agents
            self.send_reply_email_to_agent(message)

        # if self.status_category == "Paused" and not new_ticket:
        if not new_ticket:
            self.status = self.ticket_reopen_status
            self.save(ignore_permissions=True)

        c = frappe.new_doc("Communication")
        c.communication_type = "Communication"
        c.communication_medium = "Email"
        c.sent_or_received = "Received"
        c.email_status = "Open"
        c.subject = f"Re: {self.subject}"
        c.sender = frappe.session.user
        c.content = message
        c.status = "Linked"
        c.reference_doctype = "HD Ticket"
        c.reference_name = self.name
        c.ignore_permissions = True
        c.ignore_mandatory = True
        c.save(ignore_permissions=True)

        _attachments = self.get("attachments") or attachments or []
        if not len(_attachments):
            return
        QBFile = frappe.qb.DocType("File")
        condition_name = [QBFile.name == i["name"] for i in _attachments]
        frappe.qb.update(QBFile).set(QBFile.attached_to_name, c.name).set(
            QBFile.attached_to_doctype, "Communication"
        ).where(Criterion.any(condition_name)).run()

        # attach files to ticket
        file_urls = frappe.get_all(
            "File", filters={"attached_to_name": c.name}, pluck="file_url"
        )
        for url in file_urls:
            self.attach_file_with_doc("HD Ticket", self.name, url)

    def handle_inline_media_new_ticket(self):
        soup = BeautifulSoup(self.description, "html.parser")
        files = []  # List of file URLs
        for tag in soup.find_all(["img", "video"]):
            if tag.has_attr("src"):
                src = tag["src"]
                files.append(src)
        for f in files:
            file = frappe.db.exists(
                "File",
                {
                    "file_url": f,
                    "attached_to_doctype": ["is", "Not Set"],
                    "owner": frappe.session.user,
                },
            )
            if file:
                doc = frappe.get_doc("File", file)
                doc.attached_to_doctype = "HD Ticket"
                doc.attached_to_name = self.name
                doc.save()

    def send_reply_email_to_agent(
        self, message: str = "Please check the latest update on the portal."
    ):
        assigned_agents = self.get_assigned_agents()
        if not assigned_agents:
            return

        recipients = [a.get("name") for a in self.get_assigned_agents()]

        email_content = frappe.db.get_single_value(
            "HD Settings", "reply_email_to_agent_content"
        )
        default_email_content = get_default_email_content("reply_to_agents")
        try:
            frappe.sendmail(
                recipients=recipients,
                subject=f"Re: {self.subject} - #{self.name}",
                message=self._get_rendered_template(
                    email_content,
                    default_email_content,
                    {
                        "ticket_url": frappe.utils.get_url(
                            "/helpdesk/tickets/" + str(self.name)
                        ),
                        "message": message,
                    },
                ),
                reference_doctype="HD Ticket",
                reference_name=self.name,
                now=True,
            )
        except Exception as e:
            frappe.throw(_(e))

    def _suppress_acknowledgement(self) -> bool:
        """True when the auto-acknowledgement should be skipped because the ticket
        came from an automated/bot sender or has an automated subject — the same
        senders/subjects the AI enricher skips. Prevents "We've received your
        request" bounce-backs to no-reply monitoring, refund work orders, auto-
        replies and bounces. Fails open (sends the ack) on any lookup error.
        """
        try:
            _, addr = parseaddr(self.raised_by or "")
            sender = (addr or self.raised_by or "").lower()
            subject = (self.subject or "").lower()

            sender_patterns = list(_AUTOMATED_SENDER_DEFAULTS) + _split_ack_patterns(
                frappe.db.get_single_value("HD Settings", "pyek_ai_excluded_senders")
            )
            if any(p in sender for p in sender_patterns):
                return True

            subject_patterns = list(_AUTOMATED_SUBJECT_DEFAULTS) + _split_ack_patterns(
                frappe.db.get_single_value("HD Settings", "pyek_ai_excluded_subjects")
            )
            return any(p in subject for p in subject_patterns)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "HD ack suppression check failed")
            return False

    def _is_camera_drop_alert(self) -> bool:
        """A single Ubiquiti camera going offline or coming back.

        Narrow on purpose — see AUTO_CLOSE_SUBJECT_RE. Both halves must hold: the
        sender is Ubiquiti AND the subject uses the possessive "NVR's <camera>".
        A whole-recorder or whole-site alert matches neither and stays open.
        """
        _, addr = parseaddr(self.raised_by or "")
        sender = (addr or self.raised_by or "").lower()
        if AUTO_CLOSE_SENDER_HINT not in sender:
            return False
        return bool(AUTO_CLOSE_SUBJECT_RE.search(self.subject or ""))

    def _auto_close_if_camera_alert(self):
        """Close camera-drop alerts on arrival so they never enter the queue.

        Flagged with pyek_auto_closed rather than closed silently, so "how often
        did the Front Gate Scanner drop last month" is still answerable — the
        record is kept, only the triage is skipped.

        Never allowed to break ticket creation: if the marker field isn't
        provisioned, or anything else fails, the ticket is left exactly as it
        would have been and the error is logged.
        """
        try:
            if not self._is_camera_drop_alert():
                return
            self.db_set("status", "Closed", update_modified=False)
            try:
                self.db_set(AUTO_CLOSE_FIELD, 1, update_modified=False)
            except Exception:
                # Field not provisioned yet — closing is still the right outcome,
                # it just won't show up in the camera-drop report until it is.
                frappe.log_error(frappe.get_traceback(), "HD auto-close marker not set")
            log_ticket_activity(self.name, "auto-closed a camera offline alert")
        except Exception:
            frappe.log_error(frappe.get_traceback(), "HD camera auto-close failed")

    def _defer_or_send_acknowledgement(self):
        """Hand the acknowledgement to the scheduled sweep instead of sending now.

        The requester's one email should say what we understood the request to be,
        and that needs the enricher's pyek_summary — which is written by a separate
        worker up to a minute after insert. So mark the ticket pending and let
        send_pending_acknowledgements() send it once the summary exists.

        Falls back to sending immediately if the marker can't be written (e.g. the
        pyek_ack_state field isn't provisioned on this site): a missing field must
        never cost the requester their acknowledgement, or break ticket creation.
        """
        try:
            self.db_set(ACK_STATE_FIELD, ACK_PENDING, update_modified=False)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), "HD ack deferral failed; sending immediately"
            )
            self.send_acknowledgement_email()

    def send_confirmation_summary_email(self):
        """The upgraded acknowledgement: what we understood, so the requester can
        correct us early instead of after an agent has built the wrong thing.

        Sent as Echo Finley — see helpdesk.helpdesk.utils.echo for who she is and
        why the sending address deliberately isn't hers.

        Deliberately omits the IT troubleshooting steps — those are the agent's
        internal checklist (revoking tokens, confirming approval with a system
        owner) and don't belong in requester-facing mail. What IS included is the
        list of details we still need, since that's the whole point of asking now.
        """
        urgent = echo.is_urgent(self)
        subject = (
            _("Ticket #{0} — we're on it").format(self.name)
            if urgent
            else _("Ticket #{0} — got it! A couple of questions").format(self.name)
        )
        frappe.sendmail(
            recipients=[self.raised_by],
            subject=subject,
            message=self._build_confirmation_summary(urgent=urgent),
            reference_doctype="HD Ticket",
            reference_name=self.name,
            now=True,
            expose_recipients="header",
            email_headers={"X-Auto-Generated": "hd-acknowledgement"},
        )

    def _build_confirmation_summary(self, urgent: bool = False) -> str:
        """Echo's acknowledgement.

        The detail rows the old version printed ("System: inbox / User: Sara
        Parriott / Access level: access to Lily Young's inbox") are gone. They
        restated the summary sentence directly above them in worse English —
        they were the enricher's ``access_request`` object rendered field by
        field, which is how the system thinks about a request, not how the
        person who sent it does.
        """
        summary = html_escape(self.get("pyek_summary") or "")
        _details, missing = self._confirmation_details()
        greeting = echo.first_name(self)

        parts = []
        if greeting:
            parts.append(echo.paragraph(f"Hi {html_escape(greeting)},"))

        if urgent:
            parts.append(
                echo.paragraph(
                    _(
                        "Logged as ticket <strong>#{0}</strong> and marked urgent, so it's "
                        "in front of the team now."
                    ).format(self.name)
                )
            )
        else:
            parts.append(
                echo.paragraph(echo.setting("pyek_echo_greeting", name=self.name))
            )

        if summary:
            parts.append(echo.heading(_("What I understood")))
            parts.append(echo.paragraph(summary))

        if urgent:
            parts.append(
                echo.callout(
                    _(
                        "<strong>If this is stopping work right now, call {0}.</strong> That "
                        "reaches a person straight away and beats waiting on email."
                    ).format(echo.PHONE)
                )
            )
            if missing:
                parts.append(echo.heading(_("This will speed things up")))
                parts.append(echo.numbered([html_escape(m) for m in missing]))
            parts.append(
                echo.paragraph(
                    _(
                        "A technician is picking this up now. Reply here with anything else "
                        "you notice."
                    )
                )
            )
            parts.append(echo.signature(include_phone=False))
            return echo.wrap("".join(parts))

        if missing:
            parts.append(echo.heading(_("What I need from you")))
            lead = (
                _("One quick thing and I'll send this down the line:")
                if len(missing) == 1
                else _("{0} quick things and I'll send this down the line:").format(
                    len(missing)
                )
            )
            parts.append(echo.paragraph(lead))
            parts.append(echo.numbered([html_escape(m) for m in missing]))

        parts.append(echo.heading(_("What happens next")))
        parts.append(echo.paragraph(echo.setting("pyek_echo_next_steps")))
        parts.append(echo.paragraph(echo.setting("pyek_echo_signoff")))
        parts.append(echo.signature())
        return echo.wrap("".join(parts))

    def _confirmation_details(self):
        """(detail rows, missing items) pulled from whichever enricher branch ran.

        POS tickets carry a build sheet whose extracted fields are exactly the
        "did we get this right" list. IT tickets carry the access request. Returns
        empty lists when pyek_suggestions is absent or malformed — the summary
        paragraph alone is still a useful acknowledgement.
        """
        raw = self.get("pyek_suggestions")
        if not raw:
            return [], []
        try:
            data = json.loads(raw) or {}
        except (ValueError, TypeError):
            return [], []

        details = []
        build_sheet = data.get("build_sheet") or {}
        it_assist = data.get("it_assist") or {}
        branch = build_sheet or it_assist

        for field in build_sheet.get("fields") or []:
            if isinstance(field, dict) and field.get("label") and field.get("value"):
                details.append((str(field["label"]), str(field["value"])))

        access = it_assist.get("access_request") or {}
        if isinstance(access, dict):
            for key, label in (
                ("system", _("System")),
                ("user", _("User")),
                ("scope", _("Access level")),
            ):
                if access.get(key):
                    details.append((label, str(access[key])))

        missing = [
            str(m)
            for m in (branch.get("missing") or [])
            if isinstance(m, str) and m.strip()
        ]
        return details, missing

    def send_acknowledgement_email(self):
        acknowledgement_email_content = frappe.db.get_single_value(
            "HD Settings", "acknowledgement_email_content"
        )
        default_acknowledgement_email_content = get_default_email_content(
            "acknowledgement"
        )

        try:
            frappe.sendmail(
                recipients=[self.raised_by],
                subject=_("Ticket #{0}: We've received your request").format(self.name),
                # The editable template already closes with Echo's name and the
                # phone number, so this appends the picture block without a
                # second phone line under it.
                message=echo.wrap(
                    self._get_rendered_template(
                        acknowledgement_email_content,
                        default_acknowledgement_email_content,
                    )
                    + echo.signature(include_phone=False)
                ),
                reference_doctype="HD Ticket",
                reference_name=self.name,
                now=True,
                expose_recipients="header",
                email_headers={"X-Auto-Generated": "hd-acknowledgement"},
            )
        except Exception as e:
            frappe.throw(
                _("Could not send an acknowledgement email due to: {0}").format(e)
            )

    @frappe.whitelist()
    def mark_seen(self):
        self.add_viewed(
            unique_views=True, force=True
        )  # Document class method, no way to add unique_views via document settings, hence used force and unique_views=True
        self.add_seen()
        clear_notifications(ticket=self.name)

    def set_sla(self):
        """
        Find an SLA to apply to this ticket.
        """
        if sla := get_sla(self):
            self.sla = sla.name

    def apply_sla(self):
        """
        Apply SLA if set.
        """
        if sla := frappe.get_last_doc("HD Service Level Agreement", {"name": self.sla}):
            sla.apply(self)

    def get_sla(self):
        return frappe.get_doc("HD Service Level Agreement", {"name": self.sla})

    def is_currently_outside_working_hours(self):
        """Return True if current time is outside this SLA's working hours."""

        sla = self.get_sla()
        current_date = getdate()
        now = now_datetime()

        current_td = timedelta(
            hours=now.hour,
            minutes=now.minute,
            seconds=now.second,
            microseconds=now.microsecond,
        )

        day_name = current_date.strftime("%A")
        Holiday = DocType("HD Holiday")

        # Check holidays for this SLA
        holidays = (
            frappe.qb.from_(Holiday)
            .select(Holiday.holiday_date)
            .where(Holiday.parent == sla.name)
            .run(pluck=True)
        )

        if current_date in holidays:
            return True

        working_hours = sla.get_working_hours()
        # No working hours today
        if day_name not in working_hours:
            return True

        start_time, end_time = working_hours[day_name]

        # Outside working hours
        if not (start_time <= current_td < end_time):
            return True
        return False

    def set_default_status(self):
        if self.is_new():
            self.status = self.default_open_status

    def set_status_category(self):
        self.status_category = self.status_category or frappe.get_value(
            "HD Ticket Status",
            self.status,
            "category",
        )

    def get_merge_target(self):
        # Follow the chain of merged tickets to the final, non-merged ticket. Return None
        # if the chain dead-ends on a missing ticket or loops back on itself (a corrupt
        # cycle), so a reply is never redirected onto another merged ticket.
        current_ticket_name = self.merged_with
        visited_ticket_names = {self.name}
        while current_ticket_name and current_ticket_name not in visited_ticket_names:
            ticket = frappe.db.get_value(
                "HD Ticket",
                current_ticket_name,
                ["is_merged", "merged_with"],
                as_dict=True,
            )
            if not ticket:
                return None
            visited_ticket_names.add(current_ticket_name)
            if not ticket.is_merged:
                return current_ticket_name
            if not ticket.merged_with:
                return None
            current_ticket_name = ticket.merged_with
        return None

    def redirect_communication_to_merge_target(self, communication):
        merge_target_name = self.get_merge_target()
        if not merge_target_name:
            return False
        communication.db_set("reference_name", merge_target_name)
        merge_target = frappe.get_doc("HD Ticket", merge_target_name)
        merge_target.on_communication_update(communication)
        return True

    # `on_communication_update` is a special method exposed from `Communication` doctype.
    # It is called when a communication is updated. Beware of changes as this effectively
    # is an external dependency. Refer `communication.py` of Frappe framework for more.
    # Since this is called from communication itself, `c` is the communication doc.
    def on_communication_update(self, c):
        # A reply to a merged ticket belongs to its merge target; redirect it there. If no
        # safe target resolves (cycle/dead-end), fall through and handle it here so the
        # reply isn't dropped.
        if c.sent_or_received == "Received" and self.is_merged and self.merged_with:
            if self.redirect_communication_to_merge_target(c):
                return

        # If communication is incoming, then it is a reply from customer, and ticket must
        # be reopened.
        # handle re opening tickets for email
        if c.sent_or_received == "Received":
            # PYEK: an inbound "Automated Message" is our own outbound mail
            # echoed back through an alias (see CustomInboundMail._is_self_echo).
            # It is not a customer reply — reopening / stamping
            # last_customer_response off it caused the Waiting-on-Customer →
            # Open ping-pong visible on long threads.
            if c.communication_type == "Automated Message":
                return
            # check if agent has replied

            if self.has_agent_replied:
                self.status = self.ticket_reopen_status
            else:
                self.status = self.default_open_status
            # if received that means customer has replied
            self.last_customer_response = frappe.utils.now_datetime()
            # Whoever is working this ticket wants to know the requester came back.
            self.notify_assignees_of_reply(c)
        # If communication is outgoing, it must be a reply from agent
        if c.sent_or_received == "Sent":
            # Ignore system notifications
            if c.communication_type and c.communication_type == "Automated Message":
                return
            # Set first response date if not set already
            self.first_responded_on = (
                self.first_responded_on or frappe.utils.now_datetime()
            )
            self.last_agent_response = frappe.utils.now_datetime()

            # TODO: remove this feature once we add automation feature
            if frappe.db.get_single_value("HD Settings", "auto_update_status"):
                self.status = frappe.db.get_single_value(
                    "HD Settings", "update_status_to"
                )

        # Fetch description from communication if not set already. This might not be needed
        # anymore as a communication is created when a ticket is created.
        self.description = self.description or c.content
        # Save the ticket, allowing for hooks to run.
        self.save()

    def attach_file_with_doc(self, doctype, docname, file_url):
        if frappe.db.exists(
            "File",
            {
                "file_url": file_url,
                "attached_to_doctype": doctype,
                "attached_to_name": docname,
            },
        ):
            return
        file_doc = frappe.new_doc("File")
        file_doc.attached_to_doctype = doctype
        file_doc.attached_to_name = docname
        file_doc.file_url = file_url
        file_doc.save(ignore_permissions=True)

    @staticmethod
    def default_list_data(show_customer_portal_fields=False):
        columns = [
            {
                "label": "ID",
                "type": "Int",
                "key": "name",
                "width": "auto",
            },
            {
                "label": "Subject",
                "type": "Data",
                "key": "subject",
                "width": "25rem",
            },
            {
                "label": "Status",
                "type": "Select",
                "key": "status",
                "width": "8rem",
            },
            {
                "label": "First response",
                "type": "Datetime",
                "key": "response_by",
                "width": "8rem",
            },
            {
                "label": "Resolution",
                "type": "Datetime",
                "key": "resolution_by",
                "width": "8rem",
            },
            {
                "label": "Assigned To",
                "type": "MultipleAvatar",
                "key": "_assign",
                "width": "8rem",
            },
            {
                "label": "Customer",
                "type": "Link",
                "key": "customer",
                "options": "HD Customer",
                "width": "8rem",
            },
            {
                "label": "Priority",
                "type": "Link",
                "options": "HD Ticket Priority",
                "key": "priority",
                "width": "10rem",
            },
            {
                "label": "Type",
                "type": "Link",
                "options": "HD Ticket Type",
                "key": "ticket_type",
                "width": "11rem",
            },
            {
                "label": "Team",
                "type": "Link",
                "options": "HD Team",
                "key": "agent_group",
                "width": "10rem",
            },
            {
                "label": "Contact",
                "type": "Link",
                "key": "contact",
                "options": "Contact",
                "width": "8rem",
            },
            {
                "label": "Rating",
                "type": "Rating",
                "key": "feedback_rating",
                "width": "10rem",
            },
            {
                "label": "Created",
                "type": "Datetime",
                "key": "creation",
                "options": "Contact",
                "width": "8rem",
            },
        ]
        customer_portal_columns = [
            {
                "label": "ID",
                "type": "Int",
                "key": "name",
                "width": "5rem",
            },
            {
                "label": "Subject",
                "type": "Data",
                "key": "subject",
                "width": "22rem",
            },
            {
                "label": "Status",
                "type": "Select",
                "key": "status",
                "width": "11rem",
            },
            {
                "label": "Priority",
                "type": "Link",
                "options": "HD Ticket Priority",
                "key": "priority",
                "width": "10rem",
            },
            {
                "label": "First response",
                "type": "Datetime",
                "key": "response_by",
                "width": "8rem",
            },
            {
                "label": "Resolution",
                "type": "Datetime",
                "key": "resolution_by",
                "width": "8rem",
            },
            {
                "label": "Team",
                "type": "Link",
                "options": "HD Team",
                "key": "agent_group",
                "width": "10rem",
            },
            {
                "label": "Created",
                "type": "Datetime",
                "key": "creation",
                "options": "Contact",
                "width": "8rem",
            },
        ]
        rows = [
            "name",
            "subject",
            "status",
            "priority",
            "ticket_type",
            "agent_group",
            "contact",
            "agreement_status",
            "response_by",
            "resolution_by",
            "customer",
            "first_responded_on",
            "modified",
            "creation",
            "_assign",
            "resolution_date",
        ]
        return {
            "columns": (
                customer_portal_columns if show_customer_portal_fields else columns
            ),
            "rows": rows,
        }

    def parse_content(self, content):
        """
        Finds 'src' attribute of img/video and replaces it  with 'embed' attribute
        embed tag is important because framework replaces it with <img src="cid:content_id">
        this in turn is displayed as an image in the mail sent to the customer
        """
        if not content:
            return ""

        soup = BeautifulSoup(content, "html.parser")

        # comments (e.g. Outlook MSO conditionals in quoted replies) get mangled
        # by the markdown conversion in sendmail and show up as visible text
        for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
            comment.extract()

        for tag in soup.find_all(["img", "video"]):
            if tag.name == "img":
                tag["embed"] = tag.get("src")
            elif tag.name == "video":
                tag["embed"] = tag.get("src")

        return str(soup)

    @staticmethod
    def filter_standard_fields(fields):
        for f in fields:
            if f["name"] in customer_not_allowed_fields:
                fields.remove(f)
        return fields


# Check if `user` has access to this specific ticket (`doc`). This implements extra
# permission checks which is not possible with standard permission system. This function
# is being called from hooks. `doc` is the ticket to check against
def has_permission(doc, user=None):
    user = user or frappe.session.user
    if is_admin(user):
        return True
    if user in (doc.contact, doc.raised_by, doc.owner):
        return True
    if _is_customer_manager(doc.customer, user):
        return True
    if not is_agent(user):
        return False
    return _agent_has_permission(doc, user)


def _is_customer_manager(customer: str, user: str) -> bool:
    return any(
        c.get("name") == customer and c.get("is_manager")
        for c in get_customers(user, get_roles=True)
    )


def _agent_has_permission(doc, user: str) -> bool:
    if not frappe.db.get_single_value("HD Settings", "restrict_tickets_by_agent_group"):
        return True
    show_tickets_without_team = frappe.db.get_single_value(
        "HD Settings", "do_not_restrict_tickets_without_an_agent_group"
    )
    if show_tickets_without_team and not doc.get("agent_group"):
        return True

    if doc.get("_assign"):
        try:
            if user in json.loads(doc._assign):
                return True
        except (ValueError, TypeError):
            return False

    teams = get_agents_team()
    if any(team.get("ignore_restrictions") for team in teams):
        return True

    team_names = [t.team_name for t in teams]
    is_team_member = frappe.db.exists(
        "HD Team Member", {"parent": ["in", team_names], "user": frappe.session.user}
    )
    return bool(is_team_member) and doc.get("agent_group") in team_names


# Custom perms for list query. Only the `WHERE` part
# https://frappeframework.com/docs/user/en/python-api/hooks#modify-list-query
def permission_query(user: str | None = None):
    user = user or frappe.session.user
    if is_admin(user):
        return
    if not is_agent(user):
        return _customer_query(user)
    return _agent_query(user)


def _customer_query(user: str) -> str:
    """Non-agents see their own tickets, plus all tickets of customers they manage."""
    query = _get_base_visibility(user)
    managed_customers = _get_managed_customers(user)
    if managed_customers:
        query += " OR " + _build_in_clause("customer", managed_customers)
    return query


def _agent_query(user: str) -> str | None:
    query = _get_base_visibility(user)

    if not frappe.db.get_single_value("HD Settings", "restrict_tickets_by_agent_group"):
        return  # Restrictions disabled, return all tickets

    show_tickets_without_team = frappe.db.get_single_value(
        "HD Settings", "do_not_restrict_tickets_without_an_agent_group"
    )
    if show_tickets_without_team:
        query += " OR (`tabHD Ticket`.agent_group is null OR `tabHD Ticket`.agent_group = '')"

    # An agent on a team with `ignore_restrictions` set can see every team's tickets.
    teams = get_agents_team()
    if any(team.get("ignore_restrictions") for team in teams):
        all_teams = frappe.get_all("HD Team", pluck="name")
        if not all_teams:
            return query
        query += " OR (" + _build_in_clause("agent_group", all_teams) + ")"
        if not show_tickets_without_team:
            query += " OR (`tabHD Ticket`.agent_group is null)"
        return query

    query += " OR (JSON_SEARCH(`tabHD Ticket`._assign, 'all', {u}) IS NOT NULL)".format(
        u=frappe.db.escape(user)
    )
    team_names = [t.get("team_name") for t in teams]
    if team_names:
        query += " OR (" + _build_in_clause("agent_group", team_names) + ")"
    return query


def _get_base_visibility(user: str) -> str:
    """WHERE fragment for tickets a user is directly tied to: owner, contact, or raiser."""

    return "(`tabHD Ticket`.owner = {u} OR `tabHD Ticket`.contact = {u} OR `tabHD Ticket`.raised_by = {u})".format(
        u=frappe.db.escape(user)
    )


def _get_managed_customers(user: str) -> list[str]:
    return [
        str(c.get("name"))
        for c in get_customers(user, get_roles=True)
        if c.get("is_manager")
    ]


def _build_in_clause(field: str, values: list[str]) -> str:
    _values = ", ".join(frappe.db.escape(v) for v in values)
    return f"`tabHD Ticket`.{field} in ({_values})"


def set_guest_ticket_creation_permission():
    doctype = "HD Ticket"
    add_permission(doctype, "Guest", 0)

    role = "Guest"
    permlevel = 0
    ptype = ["read", "write", "create", "if_owner"]

    for p in ptype:
        # update permissions
        update_permission_property(doctype, role, permlevel, p, 1)


def remove_guest_ticket_creation_permission():
    doctype = "HD Ticket"
    role = "Guest"
    permlevel = 0
    remove(doctype, role, permlevel, 1)


customer_not_allowed_fields = ["customer"]


def send_pending_acknowledgements():
    """Send the deferred requester acknowledgement for tickets marked pending.

    Scheduled (see hooks.scheduler_events). Each pending ticket gets exactly one
    email: the confirmation summary once the enricher has written pyek_summary, or
    the plain acknowledgement if enrichment hasn't arrived within the grace window.
    Either way the state moves off "pending", so no ticket is mailed twice.

    Only tickets explicitly marked pending at insert are considered, so historical
    tickets — which read back NULL — are never re-acknowledged.
    """
    if not frappe.db.get_single_value("HD Settings", "send_acknowledgement_email"):
        return

    try:
        pending = frappe.get_all(
            "HD Ticket",
            filters={
                ACK_STATE_FIELD: ACK_PENDING,
                # Upper-bound the retry window: a ticket that keeps failing to send
                # is abandoned (left "pending" for diagnosis) rather than retried
                # every tick forever. Also keeps the batch small.
                "creation": (">", add_to_date(now_datetime(), hours=-24)),
            },
            fields=["name", "creation", "pyek_enriched", "pyek_summary"],
            order_by="creation asc",
            limit=ACK_SWEEP_BATCH,
        )
    except Exception:
        # Most likely pyek_ack_state isn't provisioned on this site. Log once per
        # run rather than failing the whole scheduler tick.
        frappe.log_error(frappe.get_traceback(), "HD ack sweep: could not list pending")
        return

    now = now_datetime()
    for row in pending:
        enriched = bool(row.get("pyek_enriched")) and bool(row.get("pyek_summary"))
        waited = (now - get_datetime(row.get("creation"))).total_seconds()
        if not enriched and waited < ACK_ENRICHMENT_GRACE_SECONDS:
            continue  # still within the window — try again next tick

        try:
            doc = frappe.get_doc("HD Ticket", row["name"])
            # Re-check suppression: the HD Settings pattern lists are editable, so a
            # sender may have been excluded between insert and now.
            if doc._suppress_acknowledgement():
                doc.db_set(ACK_STATE_FIELD, ACK_FALLBACK, update_modified=False)
                frappe.db.commit()
                continue
            if enriched:
                doc.send_confirmation_summary_email()
                state = ACK_SENT
            else:
                doc.send_acknowledgement_email()
                state = ACK_FALLBACK
            doc.db_set(ACK_STATE_FIELD, state, update_modified=False)
            frappe.db.commit()
        except Exception:
            # Leave the ticket pending so the next tick retries it, but roll back the
            # partial transaction so one bad ticket can't poison the rest of the batch.
            frappe.db.rollback()
            frappe.log_error(
                frappe.get_traceback(),
                f"HD ack sweep failed for {row.get('name')}",
            )


def close_tickets_after_n_days():
    if frappe.db.get_single_value("HD Settings", "auto_close_tickets") == 0:
        return

    status, days_threshold = frappe.db.get_value(
        "HD Settings", "HD Settings", ["auto_close_status", "auto_close_after_days"]
    )
    days_threshold = cint(days_threshold)

    # Compute the cutoff in the system timezone to match how communication_date is
    # stored. Using the database's NOW() instead would select the wrong tickets when
    # the DB server runs in a different timezone (e.g. UTC) than the Frappe system.
    inactivity_cutoff = add_to_date(now_datetime(), days=-days_threshold)

    tickets_to_close = (
        frappe.db.sql(
            """
                SELECT t.name
                FROM `tabHD Ticket` t
                INNER JOIN (
                    SELECT reference_name, MAX(communication_date) as last_communication_date
                    FROM `tabCommunication`
                    WHERE reference_doctype = 'HD Ticket'
                    GROUP BY reference_name
                ) latest_comm ON t.name = latest_comm.reference_name
                WHERE t.status = %(status)s
                AND latest_comm.last_communication_date < %(inactivity_cutoff)s
            """,
            {"inactivity_cutoff": inactivity_cutoff, "status": status},
            pluck="name",
        )
        or []
    )
    tickets_to_close = list(set(tickets_to_close))

    # cant do set_value because SLA will not be applied as setting directly to db and doc is not running.
    for ticket in tickets_to_close:
        doc = frappe.get_doc("HD Ticket", ticket)
        doc.status = "Closed"
        doc.flags.ignore_validate = True
        try:
            doc.save(ignore_permissions=True)
            # activity log for auto closing the ticket
            log_ticket_activity(
                doc.name,
                f"automatically closed the ticket after {days_threshold} day{'s' if days_threshold > 1 else ''} of inactivity",
            )
        except Exception as e:
            frappe.log_error(
                message=f"Failed to auto close ticket {doc.name} after {days_threshold} days. Error: {e}",
                title="Auto Close Ticket Failed",
            )
            continue

        frappe.db.commit()  # nosemgrep


def update_sla_status_in_ticket():
    stale_tickets = frappe.get_all(
        "HD Ticket",
        filters={
            "status_category": ["=", "Open"],
            "sla": ["is", "set"],
        },
        pluck="name",
    )
    for ticket in stale_tickets:
        doc = frappe.get_doc("HD Ticket", ticket)
        sla = frappe.get_doc("HD Service Level Agreement", doc.sla)
        sla.handle_agreement_status(doc)
        try:
            frappe.db.set_value(
                "HD Ticket",
                doc.name,
                "agreement_status",
                doc.agreement_status,
                update_modified=False,
            )

        except Exception as e:
            frappe.log_error(
                message=f"Failed to update agreement status for ticket {doc.name}. Error: {e}",
                title="Update SLA Status Failed",
            )
            continue
        frappe.db.commit()  # nosemgrep
