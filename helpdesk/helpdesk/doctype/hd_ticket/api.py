import json
import re
from datetime import timedelta

import frappe
from bs4 import BeautifulSoup
from frappe import _
from frappe.model.document import get_controller
from frappe.utils import (
    add_to_date,
    get_datetime,
    get_user_info_for_avatar,
    now_datetime,
)
from frappe.utils.caching import redis_cache
from pypika import Criterion, Order

from helpdesk.api.doc import handle_at_me_support
from helpdesk.consts import DEFAULT_TICKET_TEMPLATE
from helpdesk.helpdesk.doctype.hd_form_script.hd_form_script import get_form_script
from helpdesk.helpdesk.doctype.hd_settings.helpers import get_rendered_banner_msg
from helpdesk.helpdesk.doctype.hd_ticket_activity.hd_ticket_activity import (
    log_ticket_activity,
)
from helpdesk.helpdesk.doctype.hd_ticket_template.api import get_fields_meta
from helpdesk.helpdesk.doctype.hd_ticket_template.api import get_one as get_template
from helpdesk.utils import (
    agent_only,
    check_permissions,
    get_customers,
    is_agent,
    parse_call_logs,
)


@frappe.whitelist()
# flake8: noqa
def new(doc: dict, attachments: list[dict] = []):
    doc["doctype"] = "HD Ticket"
    doc["via_customer_portal"] = bool(frappe.session.user)
    doc["attachments"] = attachments
    doc["raised_by"] = frappe.session.user
    d = frappe.get_doc(doc).insert()
    return d


@frappe.whitelist()
def get_one(name: str, is_customer_portal: bool = False):
    frappe.has_permission("HD Ticket", "read", name, throw=True)
    QBContact = frappe.qb.DocType("Contact")
    QBTicket = frappe.qb.DocType("HD Ticket")

    _is_agent = is_agent()

    query = (
        frappe.qb.from_(QBTicket)
        .select(QBTicket.star)
        .where(QBTicket.name == name)
        .limit(1)
    )

    if not _is_agent:
        query = query.where(get_customer_criteria())

    ticket = query.run(as_dict=True)
    if not len(ticket):
        frappe.throw(_("Ticket not found"), frappe.DoesNotExistError)
    ticket = ticket.pop()

    contact = (
        frappe.qb.from_(QBContact)
        .select(
            QBContact.company_name,
            QBContact.email_id,
            QBContact.image,
            QBContact.mobile_no,
            QBContact.name,
            QBContact.phone,
        )
        .where(QBContact.name == ticket.contact)
        .run(as_dict=True)
    )
    if contact:
        contact = contact[0]
    else:
        contact = {
            "email_id": ticket.raised_by,
            "name": ticket.raised_by.split("@")[0],
        }
    template = ticket.template or DEFAULT_TICKET_TEMPLATE

    linked_calls = frappe.db.get_all(
        "Dynamic Link",
        filters={"link_name": ticket["name"], "parenttype": "TP Call Log"},
        pluck="parent",
    )

    calls = []

    for call in linked_calls:
        call = frappe.get_cached_doc(
            "TP Call Log",
            call,
            fields=[
                "name",
                "caller",
                "receiver",
                "duration",
                "type",
                "status",
                "from",
                "to",
                "recording_url",
                "creation",
            ],
        ).as_dict()

        calls.append(call)

    call_logs = parse_call_logs(calls)

    return {
        **ticket,
        "comments": get_comments(name),
        "communications": get_communications(name),
        "history": get_history(name),
        "views": get_views(name),
        "contact": contact,
        "tags": get_tags(name),
        "template": get_template(template),
        "_form_script": get_form_script(
            "HD Ticket", is_customer_portal=is_customer_portal
        ),
        "fields": get_meta(template),
        "calls": call_logs,
    }


def get_meta(template: str):
    default_fields = ["ticket_type", "agent_group", "priority", "customer"]
    DocField = frappe.qb.DocType("DocField")

    fields = (
        frappe.qb.from_(DocField)
        .select(DocField.star)
        .where(DocField.parent == "HD Ticket")
        .where(DocField.fieldname.isin(default_fields))
        .run(as_dict=True)
    )
    meta_fields = get_fields_meta(template)
    meta_fields = [f for f in meta_fields if f["fieldname"] not in default_fields]

    fields.extend(meta_fields)
    return fields


def get_customer_criteria():
    QBTicket = frappe.qb.DocType("HD Ticket")
    user = frappe.session.user
    conditions = [
        QBTicket.contact == user,
        QBTicket.raised_by == user,
        QBTicket.owner == user,
    ]
    customer = get_customers(user)
    for c in customer:
        conditions.append(QBTicket.customer == c)
    return Criterion.any(conditions)


def get_assignee(_assign: str):
    j = frappe.parse_json(_assign)
    if not j or len(j) < 1:
        return
    return get_user_info_for_avatar(j.pop())


def get_communications(ticket: str):
    if not frappe.has_permission("HD Ticket", "read", ticket):
        return []
    QBCommunication = frappe.qb.DocType("Communication")
    communications = (
        frappe.qb.from_(QBCommunication)
        .select(
            QBCommunication.bcc,
            QBCommunication.cc,
            QBCommunication.content,
            QBCommunication.creation,
            QBCommunication.communication_date,
            QBCommunication.name,
            QBCommunication.sender,
            QBCommunication.recipients,
            QBCommunication.subject,
            QBCommunication.delivery_status,
            QBCommunication.sent_or_received,
            QBCommunication.user,
        )
        .where(QBCommunication.reference_doctype == "HD Ticket")
        .where(QBCommunication.reference_name == ticket)
        # Agent thread emails are stored as "Automated Message" Communications
        # so replies to them can be traced back to the ticket. They are
        # plumbing, not conversation — keep them out of the thread.
        .where(QBCommunication.communication_type == "Communication")
        .orderby(QBCommunication.creation, order=Order.asc)
        .run(as_dict=True)
    )
    for c in communications:
        # get_attachments sits behind @redis_cache, which can hand back None
        # for an empty result; the noise pass iterates every c.attachments.
        c.attachments = get_attachments("Communication", c.name) or []
        user_id = c.user if c.sent_or_received == "Sent" and c.user else c.sender
        c.user = get_user_info_for_avatar(user_id)

    # Wrapped: a ticket that won't open is far worse than a noisy chip list, so
    # any failure here degrades to showing everything, exactly as before.
    try:
        mark_noise_attachments(communications)
    except Exception:
        frappe.log_error(
            title=f"HD attachment noise pass failed for {ticket}",
            message=frappe.get_traceback(),
        )

    # Same contract: a failure here leaves every email rendering exactly as it
    # did before, which is a working ticket rather than a broken one.
    try:
        mark_compact_communications(communications)
    except Exception:
        frappe.log_error(
            title=f"HD compact render pass failed for {ticket}",
            message=frappe.get_traceback(),
        )

    return communications


def get_comments(ticket: str):
    if not frappe.has_permission("HD Ticket Comment", "read"):
        return []
    QBComment = frappe.qb.DocType("HD Ticket Comment")
    comments = (
        frappe.qb.from_(QBComment)
        .select(
            QBComment.commented_by,
            QBComment.content,
            QBComment.creation,
            QBComment.is_pinned,
            QBComment.name,
        )
        .where(QBComment.reference_ticket == ticket)
        .orderby(QBComment.creation, order=Order.asc)
        .run(as_dict=True)
    )
    for c in comments:
        c.user = get_user_info_for_avatar(c.commented_by)
        c.attachments = get_attachments("HD Ticket Comment", c.name)
    return comments


def get_history(ticket: str):
    if not frappe.has_permission("HD Ticket Activity", "read"):
        return []
    QBActivity = frappe.qb.DocType("HD Ticket Activity")
    history = (
        frappe.qb.from_(QBActivity)
        .select(
            QBActivity.name, QBActivity.action, QBActivity.owner, QBActivity.creation
        )
        .where(QBActivity.ticket == str(ticket))
        .orderby(QBActivity.creation, order=Order.desc)
    )
    history = history.run(as_dict=True)
    for h in history:
        h.user = get_user_info_for_avatar(h.owner)
    return history


def get_views(ticket: str):
    if not frappe.has_permission("HD Ticket", "read", ticket):
        return []
    QBViewLog = frappe.qb.DocType("View Log")
    views = (
        frappe.qb.from_(QBViewLog)
        .select(
            QBViewLog.creation,
            QBViewLog.name,
            QBViewLog.viewed_by,
        )
        .where(QBViewLog.reference_doctype == "HD Ticket")
        .where(QBViewLog.reference_name == ticket)
        .orderby(QBViewLog.creation, order=Order.desc)
        .run(as_dict=True)
    )
    for v in views:
        v.user = get_user_info_for_avatar(v.viewed_by)
    return views


def get_tags(ticket: str):
    QBTag = frappe.qb.DocType("Tag Link")
    rows = (
        frappe.qb.from_(QBTag)
        .select(QBTag.tag)
        .where(QBTag.document_type == "HD Ticket")
        .where(QBTag.document_name == ticket)
        .orderby(QBTag.creation, order=Order.asc)
        .run(as_dict=True)
    )
    res = []
    for tag in rows:
        res.append(tag.tag)
    return res


def get_call_logs(ticket: str):
    linked_calls = frappe.db.get_all(
        "Dynamic Link",
        filters={"link_name": ticket, "parenttype": "TP Call Log"},
        pluck="parent",
    )

    calls = []

    for call in linked_calls:
        call = frappe.get_cached_doc(
            "TP Call Log",
            call,
            fields=[
                "name",
                "caller",
                "receiver",
                "duration",
                "type",
                "status",
                "from",
                "to",
                "recording_url",
                "creation",
            ],
        ).as_dict()

        calls.append(call)

    call_logs = parse_call_logs(calls)
    return call_logs


@redis_cache()
def get_attachments(doctype, name):
    QBFile = frappe.qb.DocType("File")

    return (
        frappe.qb.from_(QBFile)
        .select(
            QBFile.name,
            QBFile.file_url,
            QBFile.file_name,
            QBFile.file_size,
            QBFile.content_hash,
        )
        .where(QBFile.attached_to_doctype == doctype)
        .where(QBFile.attached_to_name == name)
        .run(as_dict=True)
    )


# Inline images below this are logos, social icons and tracking pixels, never
# a document somebody meant to send. Measured over the live corpus: the real
# attachments start around 60KB, the boilerplate clusters under 1KB.
SIGNATURE_MAX_BYTES = 4096


# --- compact rendering of short automated alerts -----------------------------
#
# A machine-sent alert is almost entirely layout scaffolding: across 520 live
# communications the median is 10,727 characters of HTML carrying 453
# characters of visible text, about 4%. Ticket 0349 is 12,155 characters with
# eight nested tables for five lines of content, which is why one short alert
# fills the whole reading pane and gets its own scrollbar inside the feed's.
#
# This is DELIBERATELY NARROW. Measured over the real senders, flattening is
# only an improvement for the short ones:
#
#   Ubiquiti device alerts   5 lines    -> much better compact
#   disputes@ refunds        39 lines   -> label/value pairs split across
#                                          lines, so flattening reads worse
#   config check reports     316 lines  -> the table IS the content
#
# So anything over the line budget keeps its original HTML and renders exactly
# as it does today. Nothing is allowed to get worse than the status quo.
COMPACT_MAX_LINES = 15
COMPACT_MAX_CHARS = 900

# Chrome that every one of these alerts carries and nobody reads.
_COMPACT_NOISE = re.compile(
    r"you don't often get email|learn why this is important|unsubscribe|"
    r"view (this|it) in (your )?browser|all rights reserved|privacy policy|"
    r"if you need further assistance|contact \w+ support|"
    r"^\s*(sent from|this is an automated)|"
    # Postal footer: "685 Third Ave. New York, NY 10017"
    r"\b[A-Z]{2}\s+\d{5}(-\d{4})?\b",
    re.IGNORECASE,
)


def _automated_sender(sender: str) -> bool:
    """Same definition of 'machine' the ack suppression and the AI skip use."""
    from helpdesk.helpdesk.doctype.hd_ticket.hd_ticket import (
        _AUTOMATED_SENDER_DEFAULTS,
        _split_ack_patterns,
    )

    addr = (sender or "").lower()
    patterns = list(_AUTOMATED_SENDER_DEFAULTS) + _split_ack_patterns(
        frappe.db.get_single_value("HD Settings", "pyek_ai_excluded_senders")
    )
    return any(p in addr for p in patterns)


# The mobile bubble thread trims long mail instead of giving up on it —
# unlike compact_lines, the bubble is a reading surface with the original
# always one tap away, so losing the tail is acceptable there and only there.
BUBBLE_MAX_LINES = 40
BUBBLE_MAX_CHARS = 2500

# Reply chains quote the whole prior thread below the new text; a bubble must
# show only the new text. Frappe's own composer wraps the tail in a
# <blockquote> (decomposed during parsing); clients that inline it instead are
# caught by these header lines. Deliberately conservative — a missed quote
# header just means a longer bubble, while a false match eats real content.
_QUOTE_HEADER = re.compile(
    r"^on .{0,140}wrote:?$|^-{2,}\s*original message\s*-{2,}$|^_{5,}$",
    re.IGNORECASE,
)


def _visible_lines(html: str, strip_quotes: bool = False):
    """The visible text lines of an email, block-structure aware.

    Uses the block structure rather than a naive tag strip so a table row
    doesn't run into the next one.
    """
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "head", "title"]):
        tag.decompose()
    if strip_quotes:
        for tag in soup.find_all("blockquote"):
            tag.decompose()
    # Block boundaries become newlines; cells within a row stay on one line so
    # "Device Name: Typhoon Texas Austin" survives as a single readable line.
    for tag in soup.find_all(["br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4"]):
        tag.append("\n")
    for tag in soup.find_all(["td", "th"]):
        tag.append(" ")

    lines = []
    for raw in soup.get_text().replace("\xa0", " ").split("\n"):
        line = " ".join(raw.split())
        if not line or _COMPACT_NOISE.search(line):
            continue
        if strip_quotes and _QUOTE_HEADER.match(line):
            break
        # These alerts lay their fields out as one table row per label and
        # another per value, so a bare strip leaves "Device Name:" stranded
        # above "Typhoon Texas Austin". Rejoin the pair.
        if lines and lines[-1].endswith(":"):
            lines[-1] = f"{lines[-1]} {line}"
            continue
        # Alert mail repeats its own subject in the body; a repeat straight
        # after the same line is never information.
        if lines and lines[-1] == line:
            continue
        lines.append(line)

    # A label with nothing after it tells the reader less than nothing.
    return [x for x in lines if not x.endswith(":")]


def _compact_lines(html: str):
    """Visible lines of an email, or None when flattening would lose something.

    Returns None for anything long enough that the markup is probably
    carrying meaning — nothing is allowed to get worse than the status quo.
    """
    lines = _visible_lines(html)
    if not lines:
        return None
    if len(lines) > COMPACT_MAX_LINES:
        return None
    if sum(len(x) for x in lines) > COMPACT_MAX_CHARS:
        return None
    return lines


def _bubble_text(html: str):
    """(lines, truncated) for the mobile bubble thread. Never gives up on a
    message the way _compact_lines does — it trims and flags instead."""
    lines = _visible_lines(html, strip_quotes=True)
    if not lines:
        return None, False
    out, chars, truncated = [], 0, False
    for line in lines:
        if len(out) >= BUBBLE_MAX_LINES or chars > BUBBLE_MAX_CHARS:
            truncated = True
            break
        out.append(line)
        chars += len(line)
    return out, truncated


# Trailing contact-info furniture, only ever peeled from the END of a bubble
# so a phone number quoted mid-message survives. Measured against real PYEK
# signatures (2026-08-16 live check on ticket 0392):
#   "D 346.388.4180"            -> letter-prefixed phone
#   "O 346.788.PYEK"            -> phone with a vanity-letter tail
#   "allannha.eyerly@pyekgroup.com"
#   "www.pyek.com 24616 Kingsland Blvd. Katy, Texas 77494"
#                               -> URL and postal line FLATTENED TOGETHER,
#                                  which is why the URL rule allows a tail
_SIGNATURE_FURNITURE = re.compile(
    r"^(www\.|https?://)\S+(\s.*)?$"  # URL line, possibly merged with an address
    r"|^[\w.+-]+@[\w.-]+\.\w+$"  # bare email address
    # Phone with optional letter prefix ("D", "O") or vanity tail ("PYEK");
    # at least six digits so "10 000 units" style content never matches.
    r"|^[a-z]{0,2}[\s:.]*(?:[ .()+-]*\d){6,}[ .()+-]*[a-z]{0,8}$",

    re.IGNORECASE,
)


def _trim_signature(lines, comm):
    """Drop a trailing signature block from bubble lines.

    Two passes, both bubble-only (the original email keeps its signature —
    that's the point of "sends like an email, reads like a text"):
    1. If the sender's own name appears as a line in the tail, cut there —
       that's where a signature block starts. Candidates: the resolved
       avatar display name AND the sender address's local part with dots/
       underscores as spaces ("john.pham@…" -> "john pham"), which covers
       senders with no User record.
    2. Then peel trailing furniture lines (phones, emails, URLs).
    Never empties the bubble: a cut that would leave nothing is skipped.
    """
    if not lines:
        return lines
    user = comm.get("user") or {}
    candidates = set()
    if isinstance(user, dict):
        for key in ("full_name", "name"):
            value = (user.get(key) or "").strip().lower()
            # An unresolved avatar echoes the email address back; that's not
            # a display name and never appears as a signature line.
            if value and "@" not in value:
                candidates.add(value)
    sender = (comm.get("sender") or "").strip().lower()
    if "@" in sender:
        candidates.add(re.sub(r"[._]+", " ", sender.split("@", 1)[0]).strip())
    if candidates:
        tail_start = max(1, len(lines) - 8)
        for i in range(len(lines) - 1, tail_start - 1, -1):
            if lines[i].strip().lower() in candidates:
                lines = lines[:i]
                break
    while len(lines) > 1 and _SIGNATURE_FURNITURE.match(lines[-1].strip()):
        lines = lines[:-1]
    return lines


def mark_compact_communications(communications):
    """Flag machine mail and, where it is short, precompute its readable lines.

    Done server-side so the rule lives in one testable place and the panel
    stays a renderer. `compact_lines` is None whenever the original HTML
    should be shown, which is the default for anything uncertain.
    `bubble_lines` is the mobile thread's plain-text rendering and exists for
    every email that has any visible text at all.
    """
    for c in communications:
        c["is_automated"] = _automated_sender(c.get("sender"))
        c["compact_lines"] = (
            _compact_lines(c.get("content")) if c["is_automated"] else None
        )
        lines, truncated = _bubble_text(c.get("content"))
        # c["user"] was already resolved to the avatar dict by
        # get_communications before this pass runs; _trim_signature reads it.
        c["bubble_lines"] = _trim_signature(lines, c)
        c["bubble_truncated"] = truncated


def _ticket_spread(content_hashes):
    """How many DISTINCT tickets each image appears in.

    This is the signal that separates a signature from a screenshot. A logo
    turns up across many unrelated tickets; a screenshot someone sent belongs
    to exactly one, however many times the reply thread quotes it back.
    """
    content_hashes = [h for h in content_hashes if h]
    if not content_hashes:
        return {}

    QBFile = frappe.qb.DocType("File")
    QBComm = frappe.qb.DocType("Communication")
    rows = (
        frappe.qb.from_(QBFile)
        .join(QBComm)
        .on(QBComm.name == QBFile.attached_to_name)
        .select(QBFile.content_hash, QBComm.reference_name)
        .where(QBFile.attached_to_doctype == "Communication")
        .where(QBComm.reference_doctype == "HD Ticket")
        .where(QBFile.content_hash.isin(content_hashes))
        .distinct()
        .run(as_dict=True)
    )

    spread = {}
    for r in rows:
        spread.setdefault(r.content_hash, set()).add(r.reference_name)
    return {k: len(v) for k, v in spread.items()}


def mark_noise_attachments(communications):
    """Flag the attachments that are signature furniture rather than content.

    An emailed thread re-embeds every signature graphic on every quoted reply,
    so one ticket can show sixteen chips holding four distinct images. Nothing
    is dropped here — each attachment gets `is_noise` and the frontend decides
    what to show, so a wrong call is always recoverable by the reader.

    `communications` must be ordered oldest-first: an image is kept on its first
    appearance in the ticket and suppressed on the quotes that follow.
    """

    def key(a):
        return a.get("content_hash") or a.get("name")

    spread = _ticket_spread({key(a) for c in communications for a in c.attachments})

    first_seen = {}
    for c in communications:
        for a in c.attachments:
            first_seen.setdefault(key(a), c.name)

    for c in communications:
        body = c.get("content") or ""
        seen = set()
        for a in c.attachments:
            k = key(a)
            url = a.get("file_url") or ""
            # Frappe rewrites cid: refs to the stored file URL, so an image the
            # body points at was embedded rather than deliberately attached.
            inline = bool(url) and url in body
            size = a.get("file_size") or 0

            if k in seen:
                reason = "duplicate"
            elif not inline:
                reason = None
            elif size < SIGNATURE_MAX_BYTES:
                reason = "icon"
            elif spread.get(k, 1) > 1:
                reason = "boilerplate"
            elif first_seen.get(k) != c.name:
                reason = "quoted"
            else:
                reason = None

            a["is_noise"] = bool(reason)
            a["noise_reason"] = reason
            seen.add(k)


@frappe.whitelist()
@agent_only
def merge_ticket(source: str, target: str):
    # check if source and target exists
    if not frappe.db.exists("HD Ticket", source):
        frappe.throw(_("Source ticket does not exist"))
    if not frappe.db.exists("HD Ticket", target):
        frappe.throw(_("Target ticket does not exist"))
    if source == target:
        frappe.throw(_("Source and target ticket cannot be same"))

    controller = get_controller("HD Ticket")

    source_comments = frappe.db.get_list(
        "HD Ticket Comment", filters={"reference_ticket": source}, pluck="name"
    )
    duplicate_list_retain_timestamp(
        "HD Ticket Comment", source_comments, target, controller
    )

    source_communications = frappe.db.get_list(
        "Communication",
        filters={"reference_doctype": "HD Ticket", "reference_name": source},
        pluck="name",
    )
    duplicate_list_retain_timestamp(
        "Communication", source_communications, target, controller
    )

    source_attachments = frappe.db.get_list(
        "File",
        filters={"attached_to_doctype": "HD Ticket", "attached_to_name": source},
        pluck="name",
    )
    duplicate_list_retain_timestamp("File", source_attachments, target, controller)

    doc = frappe.get_doc("HD Ticket", source)

    doc.status = "Closed"
    doc.is_merged = 1
    doc.merged_with = target
    doc.save()

    message = _(
        "This ticket (#{0}) has been merged with ticket <a href = '/helpdesk/tickets/{1}'>#{1}</a>."
    ).format(source, target)
    controller.reply_via_agent(
        doc,
        message=message,
    )

    # comment in target ticket that
    c = frappe.new_doc("HD Ticket Comment")
    c.commented_by = frappe.session.user
    c.reference_ticket = target
    source_link = frappe.utils.get_url("/helpdesk/tickets/" + str(source))
    target_link = frappe.utils.get_url("/helpdesk/tickets/" + str(target))
    c.content = _(
        f"Ticket <a href={source_link}> #{source}</a>  has been merged with ticket #{target}."
    )
    c.save()


def duplicate_list_retain_timestamp(doctype, activities: list, target: str, controller):
    for activity in activities:
        attachments = get_attachments(
            "HD Ticket Comment",
            activity,
        )

        original_doc = frappe.get_doc(doctype, activity)

        duplicate_doc = frappe.copy_doc(original_doc)

        if doctype == "Communication":
            duplicate_doc.reference_name = target
            attachments = get_attachments(
                "Communication",
                activity,
            )

        elif doctype == "HD Ticket Comment":
            duplicate_doc.reference_ticket = target
            attachments = get_attachments(
                "Communication",
                activity,
            )

        elif doctype == "File":
            duplicate_doc.attached_to_name = target

        duplicate_doc.insert(ignore_permissions=True)

        if doctype == "File":
            return

        attachments = get_attachments(
            doctype,
            activity,
        )
        for attachment in attachments:
            controller.attach_file_with_doc(
                duplicate_doc, doctype, duplicate_doc.name, attachment["file_url"]
            )

        frappe.db.set_value(
            duplicate_doc.doctype,
            duplicate_doc.name,
            {
                "creation": original_doc.creation,
                "modified": original_doc.modified,
                "owner": original_doc.owner,
                "modified_by": original_doc.modified_by,
            },
            update_modified=False,
        )


@frappe.whitelist()
@agent_only
def split_ticket(subject: str, communication_id: str):
    communicaton_creation_time = frappe.db.get_value(
        "Communication", communication_id, "creation"
    )

    ticket_id = frappe.db.get_value("Communication", communication_id, "reference_name")
    ticket_doc = frappe.get_doc("HD Ticket", ticket_id)
    new_ticket = duplicate_ticket(ticket_doc, subject)

    # update emails
    frappe.db.set_value(
        "Communication",
        {
            "reference_doctype": "HD Ticket",
            "reference_name": ticket_id,
            "creation": [">=", communicaton_creation_time],
        },
        "reference_name",
        new_ticket,
        update_modified=False,
    )

    # update comments
    frappe.db.set_value(
        "HD Ticket Comment",
        {
            "reference_ticket": ticket_id,
            "creation": [">=", communicaton_creation_time],
        },
        "reference_ticket",
        new_ticket,
        update_modified=False,
    )

    # update activities
    frappe.db.set_value(
        "HD Ticket Activity",
        {
            "ticket": ticket_id,
            "creation": [">=", communicaton_creation_time],
        },
        "ticket",
        new_ticket,
        update_modified=False,
    )

    # update attachments
    frappe.db.set_value(
        "File",
        {
            "attached_to_doctype": "HD Ticket",
            "attached_to_name": ticket_id,
            "creation": [">=", communicaton_creation_time],
        },
        "attached_to_name",
        new_ticket,
        update_modified=False,
    )

    new_ticket_link = frappe.utils.get_url("/helpdesk/tickets/" + str(new_ticket))

    controller = get_controller("HD Ticket")
    controller.reply_via_agent(
        ticket_doc,
        message=_(
            "This ticket has been split to a new ticket. Please follow up on ticket <a href={0}>#{1}</a>."
        ).format(new_ticket_link, new_ticket),
    )

    # Email on the old ticket that it has been split to new_ticket
    return new_ticket


def duplicate_ticket(ticket_doc, subject):
    from copy import deepcopy

    new_ticket = deepcopy(ticket_doc)
    new_ticket.subject = subject
    new_ticket.status = "Open"
    new_ticket.ticket_split_from = ticket_doc.name
    new_ticket.description = None
    new_ticket.first_response_time = 0
    new_ticket.first_responded_on = None

    new_ticket.creation = now_datetime()
    new_ticket.opening_date = frappe.utils.nowdate()
    new_ticket.opening_time = frappe.utils.nowtime()

    new_ticket.is_merged = 0
    new_ticket.merged_with = None

    if new_ticket.sla:
        new_ticket.sla = None
        new_ticket.agreement_status = "First Response Due"
        new_ticket.resolution_by = None
        new_ticket.service_level_agreement_creation = now_datetime()
        new_ticket.on_hold_since = None
        new_ticket.total_hold_time = None
        new_ticket.response_by = None
        new_ticket.response_date = None
        new_ticket.resolution_date = None
        new_ticket.resolution_time = None
        new_ticket.user_resolution_time = None

    new_ticket.insert(ignore_permissions=True)

    return new_ticket.name


@frappe.whitelist()
@agent_only
def get_ticket_customizations():
    # get form script
    # get default ticket template
    custom_fields = frappe.get_all(
        "HD Ticket Template Field",
        filters={"parent": "Default"},
        fields=["fieldname", "required", "placeholder", "url_method"],
        order_by="idx",
    )
    form_scripts = get_form_script("HD Ticket")
    return {"custom_fields": custom_fields, "_form_script": form_scripts}


@frappe.whitelist()
# TODO: make it bette, on mount fetch only once and cache it
def get_navigation_tickets(ticket: str, current_view: str | None = None):
    """
    Get a list of tickets to navigate
    """

    filters = get_navigation_filters(ticket, current_view)
    order_by = get_navigation_order_by(current_view)

    try:
        tickets = frappe.get_list(
            "HD Ticket",
            pluck="name",
            filters=filters,
            order_by=order_by,
            limit=40,
        )

        # Extract just the ticket IDs
        ticket_ids = [ticket, *tickets]
        # print("\n\n", ticket_ids, "\n\n")
        return ticket_ids

    except Exception as e:
        frappe.log_error(f"Error in get_navigation_tickets: {str(e)}")
        # Return empty list if there's an error
        return []


def get_navigation_filters(ticket: str, current_view: str = None):
    conditions = _to_conditions(_get_view_filters(current_view))
    # Custom filter "__assigned_on" is not available in any doctype
    conditions = [c for c in conditions if c[0] != "__assigned_on"]
    conditions.append(["name", "!=", ticket])
    return handle_at_me_support(conditions)


def _get_view_filters(current_view: str | None) -> dict | list:
    filters = _parse_view_filters(
        frappe.get_value("HD View", current_view, "filters") if current_view else None
    )
    if filters:
        return filters
    return _parse_view_filters(
        frappe.db.get_value(
            "HD View",
            {"dt": "HD Ticket", "is_default": 1, "user": frappe.session.user},
            "filters",
        )
    )


def _parse_view_filters(raw) -> dict | list:
    if not raw:
        return []
    try:
        return (json.loads(raw) if isinstance(raw, str) else raw) or []
    except (json.JSONDecodeError, TypeError):
        return []


def _to_conditions(filters: dict | list) -> list:
    """Normalize dict filters (legacy saved views) to a list of conditions."""
    if isinstance(filters, dict):
        return [
            [key, *value] if isinstance(value, list) else [key, "=", value]
            for key, value in filters.items()
        ]
    return [c for c in filters if isinstance(c, list) and len(c) >= 3]


def get_navigation_order_by(view):
    if not view:
        order_by = frappe.get_value(
            "HD View",
            {"dt": "HD Ticket", "is_default": 1, "user": frappe.session.user},
            "order_by",
        )
    elif view:
        order_by = frappe.get_value("HD View", view, "order_by")

    if order_by:
        return order_by
    return "modified desc"


@frappe.whitelist()
def get_ticket_contact(ticket: str):
    frappe.has_permission("HD Ticket", "read", ticket, throw=True)
    if not frappe.db.exists("HD Ticket", ticket):
        return None
    contact = frappe.db.get_value("HD Ticket", ticket, "contact")
    if not contact:
        raised_by = frappe.db.get_value("HD Ticket", ticket, "raised_by")
        return {
            "email_id": raised_by,
            "name": raised_by.split("@")[0],
            "phone": "",
            "mobile_no": "",
            "image": "",
        }

    return frappe.db.get_value(
        "Contact",
        contact,
        ["name", "email_id", "phone", "mobile_no", "image"],
        as_dict=1,
    )


@frappe.whitelist()
@agent_only
def rerun_ai_enrichment(ticket: str):
    """Ask the AI enricher to re-analyse this ticket. Agent-only.

    For when the AI got it wrong — a mis-extracted price, a build sheet missing a
    field. Until now the only remedy was someone clearing pyek_enriched by hand.

    This doesn't do the work: it clears the processed flag so the enricher (a separate
    Railway worker, polling roughly every minute) picks the ticket up again, and sets
    pyek_rerun_requested so that pass regenerates the AI fields WITHOUT overwriting
    priority and category. Those two are normally AI-owned on the first pass only,
    which is what lets a manual re-triage stick — a re-run must not silently undo it.

    Deliberately does NOT touch pyek_ack_state: the requester has already had their
    confirmation email, and the sweep only picks up 'pending', so re-running can never
    send a second one.

    Logged as ticket activity so there's a record of who asked and when.
    """
    ticket = str(ticket)
    frappe.has_permission("HD Ticket", "write", ticket, throw=True)
    if not frappe.db.exists("HD Ticket", ticket):
        frappe.throw(_("Ticket {0} not found").format(ticket), frappe.DoesNotExistError)

    doc = frappe.get_doc("HD Ticket", ticket)
    try:
        # Single-field form, matching the proven usage elsewhere in this app.
        doc.db_set("pyek_enriched", 0, update_modified=False)
        doc.db_set("pyek_rerun_requested", 1, update_modified=False)
    except Exception:
        # Most likely the custom fields aren't provisioned on this site. Surface it
        # rather than reporting a queued re-run that will never happen.
        frappe.log_error(frappe.get_traceback(), f"AI re-run request failed for {ticket}")
        frappe.throw(
            _("Could not queue a re-run — the AI enrichment fields are missing on this site."),
        )

    log_ticket_activity(ticket, "requested an AI re-run")
    return {
        "queued": True,
        "message": _("Queued — the AI will re-analyse this ticket within a minute or two."),
    }


@frappe.whitelist()
def get_recent_similar_tickets(ticket: str):
    frappe.has_permission("HD Ticket", "read", str(ticket), throw=True)
    if not frappe.db.exists("HD Ticket", ticket):
        return {"recent_tickets": [], "similar_tickets": [], "kb_matches": []}

    recent_tickets = get_recent_tickets(ticket)
    similar_tickets = get_similar_tickets(ticket)
    # Agent-gated inside get_kb_matches — these include internal Draft SOPs.
    kb_matches = get_kb_matches(ticket)
    return {
        "recent_tickets": recent_tickets,
        "similar_tickets": similar_tickets,
        "kb_matches": kb_matches,
    }


_SIMILAR_STOPWORDS = {
    "the", "and", "for", "with", "need", "needs", "please", "new", "conf",
    "confirmation", "order", "help", "support", "request", "ticket", "our",
    "this", "that", "you", "your", "have", "has", "from",
}


def _similar_keywords(text: str, limit: int = 6) -> list:
    """Alphabetic keywords from text (drops numbers, ids, currency, punctuation,
    stopwords) — the FTS AND-matches tokens, so only content-bearing words help."""
    out = []
    for tok in re.findall(r"[A-Za-z]{3,}", text or ""):
        w = tok.lower()
        if w in _SIMILAR_STOPWORDS or w in out:
            continue
        out.append(w)
        if len(out) >= limit:
            break
    return out


def get_similar_tickets(ticket: str, limit: int = 4) -> list:
    """FTS (SQLite) over indexed tickets/comments/replies to surface similar
    RESOLVED or CLOSED tickets — the "learn from past tickets" signal for the
    sidebar. Matches on subject + the AI summary, resolves comment/communication
    hits back to their ticket, keeps only resolved/closed, and preserves search
    rank. Fails soft (returns []) if the search index isn't built yet."""
    meta = frappe.db.get_value(
        "HD Ticket", ticket, ["subject", "pyek_summary"], as_dict=True
    )
    if not meta:
        return []
    # The FTS AND-matches every token, so a raw subject+summary (full of order
    # numbers, amounts and [BR-] ids that no other ticket shares) matches
    # nothing. Build the query from cleaned keywords instead.
    keywords = _similar_keywords(meta.get("subject"))
    if len(keywords) < 2:
        keywords += _similar_keywords(meta.get("pyek_summary"))
    query = " ".join(keywords[:6])
    if len(query) < 2:
        return []

    try:
        from helpdesk.search_sqlite import HelpdeskSearch

        search = HelpdeskSearch()
        if not search.index_exists():
            return []
        response = search.search(query, filters={})
    except Exception:
        return []

    results = (
        response.get("results", []) if isinstance(response, dict) else (response or [])
    )
    ordered_names = []
    seen = {ticket}
    for hit in results:
        dt = hit.get("doctype")
        if dt == "HD Ticket":
            name = hit.get("name") or hit.get("id")
        elif dt == "HD Ticket Comment":
            name = hit.get("reference_ticket")
        elif dt == "Communication":
            name = hit.get("reference_name")
        else:
            name = None
        if not name or name in seen:
            continue
        seen.add(name)
        ordered_names.append(name)

    if not ordered_names:
        return []

    rows = frappe.get_all(
        "HD Ticket",
        filters={
            "name": ["in", ordered_names],
            "status": ["in", ["Resolved", "Closed"]],
        },
        fields=["name", "subject", "creation", "status"],
    )
    rank = {n: i for i, n in enumerate(ordered_names)}
    rows.sort(key=lambda r: rank.get(r["name"], 10**6))
    return rows[:limit]


# Cap on how much of the KB is scanned per call. The SOP set is small (tens of
# articles) and scoring in Python keeps the matching logic in one readable place;
# revisit with a real index if the KB ever outgrows this.
_KB_SCAN_LIMIT = 200
# How much longer one word may be than the other and still count as the same stem.
# Covers plurals and -ing/-ed ("book"/"booking"), stops short of joining distinct
# words ("pass"/"password").
_KB_INFLECTION_SLACK = 3
# Keep only articles scoring near the best match. Generic vocabulary — "access"
# appears in several SOP titles — otherwise pads every result out to `limit` with
# tangential hits, and a panel that's mostly noise gets ignored.
_KB_RELATIVE_FLOOR = 0.5


def _kb_keyword_hits(keywords: list, words: set) -> int:
    """How many keywords appear in `words`, matching whole words, not substrings.

    Plain `kw in text` was wrong: it counted "day" inside "birthdays" and "cab"
    inside "cabanas", which is how an unrelated booking-limits SOP kept surfacing.
    Exact set membership alone would be too strict (it misses "consignment" vs
    "consignments"), so a prefix match either way is allowed — but only to absorb
    inflection, never to bridge two different words.

    Hence the length cap: a bare 4+ char prefix rule matched "pass" (as in season
    pass) against "password" and put the 1Password SOP on a promo ticket. Requiring
    the words to be within a few characters keeps refund/refunds and
    consignment/consignments while rejecting pass/password.
    """
    hits = 0
    for kw in keywords:
        for word in words:
            if word == kw or (
                len(kw) >= 4
                and abs(len(word) - len(kw)) <= _KB_INFLECTION_SLACK
                and (word.startswith(kw) or kw.startswith(word))
            ):
                hits += 1
                break
    return hits


def get_kb_matches(ticket: str, limit: int = 3) -> list:
    """Internal SOP articles relevant to this ticket, for the agent-side panel.

    AGENT-ONLY, and the gate is load-bearing. The seeded SOPs are Draft on purpose:
    `status` is this app's only visibility control on an article, and the public
    endpoints (api/knowledge_base.get_article, whitelisted allow_guest=True) deny
    anything that isn't Published. This function deliberately reads Draft articles,
    so returning them to a non-agent would route around that gate. The caller,
    get_recent_similar_tickets, only checks HD Ticket read permission — which a
    contact satisfies for their own ticket — so the is_agent() check must live here.

    Reads HD Article directly rather than going through HelpdeskSearch, because
    search.py indexes status="Published" only, which makes the internal SOPs
    invisible to that index. Fails soft: retrieval is a convenience, never a reason
    for the sidebar to error.
    """
    if not is_agent():
        return []

    meta = frappe.db.get_value(
        "HD Ticket", ticket, ["subject", "pyek_summary"], as_dict=True
    )
    if not meta:
        return []

    keywords = _similar_keywords(meta.get("subject"), limit=8)
    for kw in _similar_keywords(meta.get("pyek_summary"), limit=8):
        if kw not in keywords:
            keywords.append(kw)
    if not keywords:
        return []

    try:
        articles = frappe.get_all(
            "HD Article",
            filters={"status": ["!=", "Archived"]},
            fields=["name", "title", "status", "category", "content"],
            limit=_KB_SCAN_LIMIT,
        )
    except Exception:
        return []

    categories = {
        c["name"]: c["category_name"]
        for c in frappe.get_all(
            "HD Article Category", fields=["name", "category_name"], limit=100
        )
    }

    scored = []
    for article in articles:
        title = (article.get("title") or "").lower()
        try:
            body = BeautifulSoup(article.get("content") or "", "html.parser").get_text(" ")
        except Exception:
            body = article.get("content") or ""
        body = body.lower()

        title_hits = _kb_keyword_hits(keywords, set(re.findall(r"[a-z]{3,}", title)))
        body_hits = _kb_keyword_hits(keywords, set(re.findall(r"[a-z]{3,}", body)))
        # Require the ticket's vocabulary to appear in the article TITLE. Body-only
        # matches proved to be noise: on a sample of real tickets, every correct SOP
        # had a title hit, while every wrong suggestion matched on body text alone —
        # and raw score can't separate them (a correct match scored the same 5 as an
        # unrelated one). SOP titles are descriptive, so this holds up, and it errs
        # toward showing nothing. That's the right bias: a wrong suggestion is worse
        # than none, because it teaches agents to ignore the panel.
        if not title_hits:
            continue
        # Body hits then rank among the candidates that cleared the title gate.
        scored.append((title_hits * 3 + body_hits, article))

    scored.sort(key=lambda pair: -pair[0])
    if scored:
        floor = scored[0][0] * _KB_RELATIVE_FLOOR
        scored = [pair for pair in scored if pair[0] >= floor]
    return [
        {
            "name": article["name"],
            "title": article["title"],
            "status": article["status"],
            "category": categories.get(article.get("category")),
            "score": score,
        }
        for score, article in scored[:limit]
    ]


def get_recent_tickets(ticket: str):
    fields = ["subject", "creation", "name", "status"]
    [raised_by, customer] = frappe.db.get_value(
        "HD Ticket", ticket, ["raised_by", "customer"]
    )
    org_tickets = []
    user_tickets = []
    if customer:
        org_tickets = (
            frappe.get_list(
                "HD Ticket",
                filters={
                    "name": ["!=", ticket],
                    "customer": customer,
                },
                fields=fields,
                order_by="creation desc",
                limit=2,
            )
            or []
        )

    if raised_by:
        # Exclude the current ticket and any already picked up as org tickets,
        # otherwise a ticket matching both `customer` and `raised_by` shows twice.
        excluded = [ticket] + [t.name for t in org_tickets]
        user_tickets = (
            frappe.get_list(
                "HD Ticket",
                filters={
                    "name": ["not in", excluded],
                    "raised_by": raised_by,
                },
                fields=fields,
                order_by="creation desc",
                limit=4 - len(org_tickets),
            )
            or []
        )
    return org_tickets + user_tickets


@frappe.whitelist()
def get_ticket_activities(ticket: str):
    frappe.has_permission("HD Ticket", "read", ticket, throw=True)
    activities = {
        "comments": get_comments(ticket),
        "communications": get_communications(ticket),
        "history": get_history(ticket),
        "views": get_views(ticket),
        "calls": get_call_logs(ticket),
    }
    return activities


@frappe.whitelist()
def get_ticket_assignees(ticket: str) -> list[dict]:
    frappe.has_permission("HD Ticket", "read", ticket, throw=True)
    assignee_names = json.loads(
        frappe.db.get_value("HD Ticket", ticket, "_assign") or "[]"
    )
    if not assignee_names:
        return []
    # Presence details are for the agent desk only; customers get plain names.
    if not is_agent():
        return [{"name": name} for name in assignee_names]
    # Enrich each assignee with their agent status so the UI can show presence
    # without a separate lookup. Non-agent assignees fall back to just the name.
    agents = {
        agent.name: agent
        for agent in frappe.get_all(
            "HD Agent",
            filters={"name": ["in", assignee_names]},
            fields=[
                "name",
                "agent_name",
                "user_image",
                "availability",
                "availability_changed_on",
            ],
        )
    }
    return [agents.get(name, {"name": name}) for name in assignee_names]


def show_banner_next_day(ticket):
    sla = ticket.get_sla()
    working_hours = sla.get_working_hours()
    now = now_datetime()
    creation_date = get_datetime(ticket.creation)
    next_date = add_to_date(creation_date, days=1)
    next_date_day_name = next_date.strftime("%A")
    if next_date_day_name not in working_hours:
        return True

    start_time = working_hours[next_date_day_name][0]

    next_day_start_datetime = (
        next_date.replace(hour=0, minute=0, second=0, microsecond=0) + start_time
    )
    if now > next_day_start_datetime:
        return False
    return True


@frappe.whitelist()
def show_outside_hours_banner(ticket_name: str):
    show_banner_settings = frappe.db.get_single_value(
        "HD Settings", "enable_outside_hours_banner"
    )
    if not show_banner_settings:
        return {"show": False}

    ticket = frappe.get_doc("HD Ticket", ticket_name)
    is_currently_outside = (
        ticket.is_currently_outside_working_hours()
        and ticket.raised_outside_working_hours
        and show_banner_next_day(ticket)
    )
    if is_currently_outside and not ticket.has_agent_replied:
        banner_data = get_rendered_banner_msg(ticket_name)

        return {"msg": banner_data.get("banner_msg"), "show": True}

    return {"show": False}
