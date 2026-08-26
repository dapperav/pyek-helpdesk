"""Work a ticket from your mailbox.

When an agent is assigned or @mentioned on a ticket we send them the whole
conversation so far, and they can answer the requester by replying to that
email — no different from typing the reply in the desk. Two halves, each behind
its own HD Settings switch so either can be turned off without a deploy:

``pyek_agent_thread_email``
    Outbound. The notification carries the ticket header, the conversation, the
    internal comments, and a link into the desk. It is sent as a real
    ``Communication`` on the ticket (type "Automated Message", so it stays out
    of the visible thread and out of SLA) which is what lets the reply thread
    back — Frappe matches the reply's In-Reply-To against the Email Queue row
    and resolves the ticket from there.

``pyek_agent_email_reply``
    Inbound. A reply from an agent's own mailbox is recorded as *their* reply
    and relayed to the requester, instead of Frappe's default of filing every
    inbound email as a message received from the customer.

Everything the requester must never see — internal comments, the quoted
history — sits below :data:`REPLY_MARKER`, and an inbound reply is cut at that
marker before a single byte is relayed. If the cut can't be made confidently
the relay is refused rather than guessed at; see :func:`strip_reply`.
"""

import re

import frappe
from frappe.utils import get_url, pretty_date

from helpdesk.helpdesk.utils import echo
from helpdesk.helpdesk.utils.inline_images import (
    embed_site_images,
    inlined_file_urls,
)

# Cut here on the way back in. Wording matters: it is the one instruction the
# agent sees, and every mail client quotes it back to us verbatim.
REPLY_MARKER = "##- Please type your reply above this line -##"

# Stamped on every internal-comment block. If this survives the cut, the reply
# still contains internal notes and must not go to the requester.
INTERNAL_SENTINEL = "pyek-internal-note"

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_SPACE_ENTITIES = {"&nbsp;", "&#160;", "&#32;", "&#xa0;", "&#x00a0;"}
# The marker, tolerant of the whitespace and case mangling clients apply to it.
_MARKER_RE = re.compile(
    r"#\s*#\s*-\s*please\s+type\s+your\s+reply\s+above\s+this\s+line\s*-\s*#\s*#",
    re.IGNORECASE,
)


def is_thread_email_enabled() -> bool:
    return bool(
        int(frappe.db.get_single_value("HD Settings", "pyek_agent_thread_email") or 0)
    )


def is_email_reply_enabled() -> bool:
    return bool(
        int(frappe.db.get_single_value("HD Settings", "pyek_agent_email_reply") or 0)
    )


def split_aliases(raw: str | None) -> set[str]:
    """Parse an HD Agent's alias list.

    Accepts commas, semicolons and newlines, and tolerates the ``smtp:`` prefix
    that Entra's ``proxyAddresses`` carries, so the field can be pasted in from
    a directory export unedited.
    """
    if not raw:
        return set()

    addresses = set()
    for chunk in re.split(r"[,;\n\r]+", raw):
        address = chunk.strip().lower()
        if address.startswith("smtp:"):
            address = address[5:]
        if "@" in address:
            addresses.add(address)
    return addresses


def agent_user_for_email(email: str) -> str | None:
    """The active HD Agent who sends from this address, or None.

    Checked against the Frappe user id, ``User.email``, and the agent's alias
    list — in that order. The alias list is what makes this work in practice:
    Mark's Frappe id and ``User.email`` are both ``mi@pyekgroup.com``, but
    Outlook sends as ``mark.immler@pyek.com``, and matching only the first two
    filed his reply as a message from the customer.

    Returning None is the safe answer: the reply is recorded the way Frappe
    always recorded it, and nothing is relayed to the requester.
    """
    if not email:
        return None

    email = email.strip().lower()
    users = frappe.get_all(
        "User",
        filters={"enabled": 1},
        or_filters={"name": email, "email": email},
        fields=["name"],
        limit=2,
    )
    for user in users:
        if frappe.db.exists("HD Agent", {"user": user.name, "is_active": 1}):
            return user.name

    for agent in frappe.get_all(
        "HD Agent", filters={"is_active": 1}, fields=["user", "pyek_email_aliases"]
    ):
        if email in split_aliases(agent.pyek_email_aliases):
            return agent.user

    return None


def _visible_text(html: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", html or ""))


def strip_reply(html: str) -> str | None:
    """Return just what the agent typed, or None if that can't be established.

    Cuts the raw HTML at :data:`REPLY_MARKER`. The marker is located in the
    *visible* text — clients split it across tags, rewrite the whitespace and
    wrap it in their own quote markup — and the offset is mapped back to the
    HTML so the cut lands in the right place.

    Returning None means "refuse to relay": either the marker never arrived, or
    internal notes survived the cut. The caller falls back to filing the reply
    without sending it on.
    """
    if not html:
        return None

    # Walk the HTML once, recording where each visible character came from, so
    # a match against the visible text can be mapped back to an HTML offset.
    # Non-breaking spaces count as whitespace here: Outlook rewrites the spaces
    # inside the marker as &nbsp; often enough that ignoring them would mean
    # refusing to relay most of Brannan's replies.
    offsets: list[int] = []
    visible: list[str] = []
    in_tag = False
    i = 0
    while i < len(html):
        char = html[i]
        if char == "<":
            in_tag = True
            i += 1
            continue
        if char == ">":
            in_tag = False
            i += 1
            continue
        if in_tag:
            i += 1
            continue
        if char == "&":
            end = html.find(";", i, i + 10)
            if end != -1 and html[i : end + 1].lower() in _SPACE_ENTITIES:
                visible.append(" ")
                offsets.append(i)
                i = end + 1
                continue
        visible.append(char)
        offsets.append(i)
        i += 1

    flat = _WS_RE.sub(" ", "".join(visible))
    # Collapsing whitespace shifts the offsets; rebuild the map alongside it.
    flat_offsets: list[int] = []
    previous_was_space = False
    for char, offset in zip("".join(visible), offsets, strict=True):
        if char.isspace():
            if previous_was_space:
                continue
            previous_was_space = True
        else:
            previous_was_space = False
        flat_offsets.append(offset)

    match = _MARKER_RE.search(flat)
    if not match or match.start() >= len(flat_offsets):
        return None

    reply = html[: flat_offsets[match.start()]]

    # A quoting client may open the quote block before the marker, leaving the
    # cut inside dangling markup — harmless, sanitize_html closes it. What is
    # not harmless is an internal note surviving above the marker.
    if INTERNAL_SENTINEL in reply:
        return None

    # Nothing above the marker means the agent hit reply and sent the quote
    # back untouched — there is no reply to pass on.
    if not _visible_text(reply).strip():
        return None

    return reply.strip()


_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_SRC_RE = re.compile(r"""(?:src|embed)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)

# Bounds on what gets attached. A thread that re-embeds a signature on every
# quoted reply can carry a dozen near-identical images; past these limits the
# rest become markers and the agent opens the ticket.
MAX_INLINE_IMAGES = 6
MAX_INLINE_BYTES = 3 * 1024 * 1024

_IMAGE_MARKER = (
    '<span style="font-size:12px;color:#98a5b3;border:1px solid #e5e9ee;'
    'border-radius:3px;padding:1px 5px">[image]</span>'
)


def _file_path_from_src(src: str) -> str:
    """The site-relative file path an <img> points at, or "".

    Frappe stores inline images as files and rewrites the mail's ``cid:`` refs
    to their URLs, which arrive here absolute and with a ``?fid=`` query.
    """
    if not src:
        return ""
    path = src.split("?", 1)[0]
    for prefix in ("http://", "https://"):
        if path.startswith(prefix):
            path = "/" + path.split("/", 3)[3] if path.count("/") >= 3 else ""
            break
    return path if path.startswith(("/files/", "/private/files/")) else ""


def _inline_plan(communications: list[dict]) -> dict[str, bool]:
    """Which image paths in this thread are worth attaching: ``{path: True}``.

    Images in the quoted history point at ``/private/files/...``, which needs a
    logged-in session — and a mail client has none, so every one of them renders
    as a broken box. Anything kept has to travel with the message instead.

    The judgement of what's worth keeping is the one the ticket view already
    makes: ``mark_noise_attachments`` marks signature furniture, tracking pixels
    and images quoted back from an earlier reply, and only the survivors are
    attached.
    """
    from helpdesk.helpdesk.doctype.hd_ticket.api import mark_noise_attachments

    ordered = sorted(communications, key=lambda c: c.get("creation") or "")
    names = [c["name"] for c in ordered if c.get("name")]
    if not names:
        return {}

    files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Communication",
            "attached_to_name": ["in", names],
        },
        fields=["name", "file_url", "file_size", "content_hash", "attached_to_name"],
    )
    by_comm: dict[str, list] = {}
    for f in files:
        by_comm.setdefault(f.attached_to_name, []).append(dict(f))

    shaped = [
        frappe._dict(
            name=c["name"],
            content=c.get("content") or "",
            attachments=by_comm.get(c["name"], []),
        )
        for c in ordered
    ]
    try:
        mark_noise_attachments(shaped)
    except Exception:
        # Losing the noise judgement is survivable; losing the email is not.
        frappe.log_error(frappe.get_traceback(), "HD thread image triage failed")
        return {}

    plan: dict[str, bool] = {}
    budget = MAX_INLINE_BYTES
    for shaped_comm in shaped:
        for attachment in shaped_comm.attachments:
            url = attachment.get("file_url") or ""
            if not url or url in plan:
                continue
            size = attachment.get("file_size") or 0
            keep = (
                not attachment.get("is_noise")
                and len(plan) < MAX_INLINE_IMAGES
                and size <= budget
            )
            plan[url] = keep
            if keep:
                budget -= size
    return plan


def _rewrite_images(html: str, plan: dict[str, bool], attached: set[str]) -> str:
    """Swap each <img> for an inline attachment or a small [image] marker.

    ``attached`` carries across the whole email so the same picture is embedded
    once, however many quoted copies of it the thread contains.
    """
    if not html:
        return html

    def swap(match):
        src = _SRC_RE.search(match.group(0))
        path = _file_path_from_src(src.group(1) if src else "")
        if not path or not plan.get(path) or path in attached:
            return _IMAGE_MARKER
        attached.add(path)
        # embed= is what frappe's set_part_html turns into a cid: attachment.
        return f'<img embed="{path}" style="max-width:100%;height:auto" />'

    return _IMG_RE.sub(swap, html)


def _comment_block(comment: dict) -> str:
    author = comment.get("commented_by") or "Unknown"
    return f"""
<div class="{INTERNAL_SENTINEL}" style="border-left:3px solid #f0b429;padding:8px 12px;margin:12px 0;background:#fffbeb">
  <div style="font-size:12px;color:#8a6d1f;margin-bottom:4px">
    Internal note — {frappe.utils.escape_html(author)} · {pretty_date(comment.get("creation"))}
  </div>
  <div style="font-size:14px;color:#1f272e">{comment.get("content") or ""}</div>
</div>"""


def _communication_block(comm: dict, body: str) -> str:
    direction = "to requester" if comm.get("sent_or_received") == "Sent" else "from"
    who = comm.get("sender") or ""
    return f"""
<div style="border-top:1px solid #e5e9ee;padding:12px 0">
  <div style="font-size:12px;color:#6b7b8f;margin-bottom:6px">
    {frappe.utils.escape_html(direction)} {frappe.utils.escape_html(who)} · {pretty_date(comm.get("creation"))}
  </div>
  <div style="font-size:14px;color:#1f272e">{body}</div>
</div>"""


def build_thread_html(ticket, event: str, actor: str | None = None) -> str:
    """The notification body: what happened, the ticket at a glance, the reply
    marker, then the conversation and the internal notes below it."""
    link = get_url(f"/helpdesk/tickets/{ticket.name}")
    actor_name = (
        frappe.get_cached_value("User", actor, "full_name") if actor else None
    ) or "Someone"

    communications = frappe.get_all(
        "Communication",
        filters={
            "reference_doctype": "HD Ticket",
            "reference_name": ticket.name,
            "communication_type": "Communication",
        },
        fields=["name", "sender", "sent_or_received", "content", "creation"],
        order_by="creation desc",
    )
    plan = _inline_plan(communications)
    attached: set[str] = set()
    comments = frappe.get_all(
        "HD Ticket Comment",
        filters={"reference_ticket": ticket.name},
        fields=["commented_by", "content", "creation"],
        order_by="creation desc",
    )

    headline = (
        f"{frappe.utils.escape_html(actor_name)} mentioned you on this ticket"
        if event == "Mention"
        else f"{frappe.utils.escape_html(actor_name)} assigned this ticket to you"
    )

    facts = "".join(
        f'<tr><td style="padding:2px 12px 2px 0;color:#6b7b8f;font-size:13px">{label}</td>'
        f'<td style="padding:2px 0;font-size:13px;color:#1f272e">{frappe.utils.escape_html(str(value or "—"))}</td></tr>'
        for label, value in (
            ("Requester", ticket.raised_by),
            ("Status", ticket.status),
            ("Priority", ticket.priority),
            ("Team", ticket.agent_group),
        )
    )

    # Echo signs it so an agent can see at a glance that it is automated, but
    # the body stays terse — this is the email Brannan works from several times
    # a day, not one he reads. Her block sits above the reply marker, since
    # everything below the marker is cut from his reply.
    return f"""
<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1f272e">
  <p style="font-size:15px;margin:0 0 4px">{headline}.</p>
  <p style="font-size:18px;font-weight:600;margin:0 0 12px">
    #{ticket.name} — {frappe.utils.escape_html(ticket.subject or "")}
  </p>
  <table style="border-collapse:collapse;margin-bottom:16px">{facts}</table>
  <p style="margin:0 0 20px">
    <a href="{link}" style="background:#1f272e;color:#fff;text-decoration:none;padding:9px 16px;border-radius:6px;font-size:14px;display:inline-block">
      Open ticket #{ticket.name}
    </a>
  </p>
  <p style="font-size:13px;color:#6b7b8f;margin:0 0 24px">
    Or just reply to this email — your reply goes to {frappe.utils.escape_html(ticket.raised_by or "the requester")}
    and is recorded on the ticket.
  </p>
  {echo.signature(subtitle=f"{echo.TEAM} · automated", include_phone=False)}
  <div style="font-size:12px;color:#98a5b3;border-top:1px dashed #cbd5e1;padding-top:10px;margin-top:20px">
    {REPLY_MARKER}
  </div>
  {"".join(_communication_block(c, _rewrite_images(c.get("content") or "", plan, attached)) for c in communications)}
  {"".join(_comment_block(c) for c in comments)}
</div>"""


def will_send_thread_email(for_user: str) -> bool:
    """Whether :func:`send_thread_email` would send to this recipient.

    Kept separate so the Notification Log override can suppress the framework's
    plain assignment email on exactly the same condition that made the ToDo
    hook send the thread email — never on a guess, so a recipient who is not an
    agent still gets Frappe's own notification.
    """
    return is_thread_email_enabled() and bool(agent_user_for_email(for_user))


def send_thread_email(
    ticket_name: str, for_user: str, event: str, actor: str | None = None
):
    """Email one agent the ticket thread. Safe to call for any notification —
    it no-ops unless the feature is on and the recipient is a real agent."""
    if not will_send_thread_email(for_user):
        return False

    ticket = frappe.get_doc("HD Ticket", ticket_name)
    recipient = frappe.db.get_value("User", for_user, "email") or for_user

    account = ticket.sender_email()
    if not account:
        frappe.log_error(
            title=f"HD agent thread email for {ticket_name}: no outgoing account"
        )
        return False

    # A real Communication is what makes the reply findable: frappe.sendmail
    # records its message_id on the Email Queue row, and InboundMail resolves a
    # reply's In-Reply-To through that row back to this ticket. "Automated
    # Message" keeps it out of the visible thread (get_communications filters
    # it) and out of first_responded_on (on_communication_update ignores it).
    body = build_thread_html(ticket, event, actor)

    communication = frappe.get_doc(
        {
            "doctype": "Communication",
            "communication_type": "Automated Message",
            "communication_medium": "Email",
            "content": body,
            "email_account": account.name,
            "email_status": "Open",
            "recipients": recipient,
            "reference_doctype": "HD Ticket",
            "reference_name": ticket.name,
            "sender": account.email_id,
            "sent_or_received": "Sent",
            "status": "Linked",
            "subject": f"Re: {ticket.subject} (#{ticket.name})",
        }
    ).insert(ignore_permissions=True)

    frappe.sendmail(
        communication=communication.name,
        # `body`, not `communication.content`: inserting the Communication runs
        # Frappe's HTML sanitiser, which strips the non-standard `embed`
        # attribute — and `embed` is exactly what set_part_html turns into the
        # inline cid: attachments. Sending the round-tripped copy is why Echo's
        # avatar and every quoted image arrived broken.
        message=body,
        now=True,
        recipients=recipient,
        reference_doctype="HD Ticket",
        reference_name=ticket.name,
        reply_to=account.email_id,
        sender=account.email_id,
        subject=communication.subject,
        with_container=False,
    )
    return True


def _own_addresses() -> set[str]:
    """Every address this site sends and receives on — never relay back to one."""
    return {
        (row.email_id or "").lower()
        for row in frappe.get_all("Email Account", fields=["email_id"])
        if row.email_id
    }


def relay_agent_reply(ticket, communication) -> bool:
    """Send an agent's emailed reply on to the requester.

    The agent replied to a notification addressed to them, so the requester
    never saw it. Sending it from the ticket's own account (not the agent's
    mailbox) keeps SPF and DKIM intact and keeps the thread on one address.
    """
    recipients = ticket.raised_by
    if not recipients:
        return False

    account = ticket.sender_email()
    if not account:
        frappe.log_error(
            title=f"HD agent reply relay for {ticket.name}: no outgoing account"
        )
        return False

    own = _own_addresses()
    cc = []
    for raw in (communication.cc or "").replace(";", ",").split(","):
        address = raw.strip()
        if address and address.lower() not in own:
            cc.append(address)

    # The agent's mail client wrote this HTML and its pictures point at site
    # URLs the requester can't open. Same treatment the portal's own replies get
    # (see helpdesk.helpdesk.utils.inline_images) — without it the relay is the
    # one reply surface that still arrives as a wall of broken boxes.
    body = embed_site_images(communication.content)
    inline = inlined_file_urls(body)

    attachments = [
        {"file_url": file_url}
        for file_url in frappe.get_all(
            "File",
            filters={
                "attached_to_doctype": "Communication",
                "attached_to_name": communication.name,
            },
            pluck="file_url",
        )
        # An embedded picture already travels with the message. Attaching it
        # again would show the requester the screenshot in the text and an
        # identical download sitting beside it.
        if file_url not in inline
    ]

    frappe.sendmail(
        attachments=attachments,
        cc=cc or None,
        communication=communication.name,
        expose_recipients="header",
        message=body,
        recipients=recipients,
        reference_doctype="HD Ticket",
        reference_name=ticket.name,
        reply_to=account.email_id,
        sender=account.email_id,
        subject=communication.subject or f"Re: {ticket.subject} (#{ticket.name})",
        with_container=False,
    )
    return True


def note_unrelayed_reply(ticket, communication) -> None:
    """Record that an agent's emailed reply was filed but not forwarded.

    Only happens when the reply came back without the marker, which means the
    quoted history — including internal notes — can't be separated from what
    the agent wrote. Better a visible note than a silent leak.
    """
    frappe.get_doc(
        {
            "doctype": "HD Ticket Comment",
            "reference_ticket": ticket.name,
            "commented_by": communication.user or "Administrator",
            "content": (
                "<p>This reply arrived by email but was <b>not sent to the "
                "requester</b> — the reply marker was missing, so the quoted "
                "history (which can contain internal notes) could not be "
                "separated from the new text. Send it from here if the "
                "requester still needs it.</p>"
            ),
            "is_pinned": False,
        }
    ).insert(ignore_permissions=True)
