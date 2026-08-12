"""Echo Finley — the voice of everything PMIT sends by itself.

Echo is the IT mascot: a dolphin in a headset with a clipboard, and the name on
every automated email the helpdesk sends. Before this, the acknowledgement that
mattered most was assembled from bare ``<p>`` and ``<ul>`` tags and signed by
nobody, while the warm Echo-signed template sat on the fallback path that only
fires when enrichment times out.

Two decisions are worth knowing before editing anything here.

**The envelope does not change.** Echo's mailbox is
``notifications@pyekgroup.com`` and that is where her avatar comes from, but mail
still goes out as ``help.pyek@pyekgroup.com``. Frappe only reads two mailboxes,
and sending as an address it cannot read would drop every reply on the floor.
Echo is an identity in the body, not a sender.

**She reads the room.** Full mascot on ordinary requests; on anything the
enricher flagged urgent she keeps her name and face but writes plainly and leads
with the phone number, because someone whose registers are down should be
calling, not enjoying a dolphin pun.

The avatar is referenced with ``embed=`` rather than a URL: Frappe's
``set_part_html`` rewrites that attribute into a ``cid:`` reference and attaches
the image inline, which is the only form Outlook renders without the recipient
clicking "download pictures". Data URIs it ignores outright, and remote images it
blocks by default.
"""

import contextlib
import json

import frappe
from frappe.utils import escape_html

NAME = "Echo Finley"
TAGLINE = "the dolphin of digital solutions"
TEAM = "PYEK IT Support"
PHONE = "(346) 388-4180"

# Uploaded as a public File so `embed=` can resolve it. Deliberately its own
# path: the 96x96 rendition is byte-identical to the contact photo the enricher
# uploads for this mailbox, and Frappe's content dedup would have pointed Echo
# at /files/contact-photo-Notifications.png — a file the contact-photo pass owns
# and could clean up underneath her.
AVATAR_URL = "/files/echo-finley.png"
AVATAR_PX = 56

_INK = "#1f272e"
_SOFT = "#6b7b8f"
_FAINT = "#98a5b3"
_RULE = "#e5e9ee"
_ACCENT = "#0e7c86"
_FONT = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"

URGENT_WORDS = ("urgent", "high", "critical", "emergency")

# Editable from HD Settings so Echo's voice can be tuned without a deploy. The
# summary and the enricher's questions stay in code — those carry the actual
# content, and a typo in a loop should not be able to break them.
SETTING_DEFAULTS = {
    "pyek_echo_greeting": (
        "Echo here — I've logged your request as ticket <strong>#{name}</strong> "
        "and the IT pod can see it."
    ),
    "pyek_echo_next_steps": (
        "Reply to this email and a technician picks it up. Most requests are done "
        "and dusted within one business day (Mon–Fri, 9–5 Central)."
    ),
    "pyek_echo_signoff": (
        "Did I misread any of that? Tell me and I'll put it right — I've been "
        "known to misjudge a wave."
    ),
}


def setting(field: str, **fmt) -> str:
    """An HD Settings override, falling back to the shipped default.

    Formatting is a plain ``str.format`` on named placeholders, not Jinja: the
    fields are meant to be edited by whoever is on the helpdesk, and a bad
    ``{`` should degrade to the default rather than raise mid-send.
    """
    raw = None
    # A missing field (not yet migrated) is normal, not an error — fall back.
    with contextlib.suppress(Exception):
        raw = frappe.db.get_single_value("HD Settings", field)

    text = (raw or "").strip() or SETTING_DEFAULTS.get(field, "")
    try:
        return text.format(**fmt)
    except (KeyError, IndexError, ValueError):
        frappe.log_error(
            title=f"Echo setting {field} has a bad placeholder",
            message=f"value: {text!r}",
        )
        return SETTING_DEFAULTS.get(field, "").format(**fmt)


def is_urgent(ticket) -> bool:
    """Whether Echo should drop the mascot voice for this ticket.

    Reads the urgency the enricher already wrote — no new field, and nobody has
    to remember to set it. Ticket priority counts too, since an agent raising
    the priority by hand is the same signal.
    """
    try:
        if (ticket.get("priority") or "").strip().lower() in ("urgent", "high"):
            return True

        raw = ticket.get("pyek_suggestions")
        if not raw:
            return False
        data = json.loads(raw) or {}
        for branch in (data.get("it_assist") or {}, data.get("build_sheet") or {}):
            urgency = str(branch.get("urgency") or "").strip().lower()
            if urgency in URGENT_WORDS:
                return True
    except Exception:
        # An unreadable suggestion blob must not decide the tone by crashing.
        frappe.log_error(frappe.get_traceback(), "Echo urgency check failed")
    return False


def first_name(ticket) -> str:
    """Something to greet the requester by, or an empty string.

    Prefers the linked Contact. Falling back to the address only works when the
    local part is separated — ``sara.parriott@`` gives "Sara", but
    ``saraparriott@`` would give "Saraparriott", which is worse than no greeting
    at all. Returns "" in that case, and in every case we can't be confident
    about, and the caller simply drops the greeting line.
    """
    try:
        if ticket.get("contact"):
            name = frappe.db.get_value("Contact", ticket.contact, "first_name")
            if name and name.strip():
                return name.strip()

        local = (ticket.get("raised_by") or "").split("@")[0]
        if not local or any(ch.isdigit() for ch in local):
            return ""
        if local.lower() in (
            "info",
            "support",
            "help",
            "sales",
            "orders",
            "order",
            "noreply",
            "no-reply",
            "admin",
            "notifications",
        ):
            return ""

        parts = [p for p in local.replace("_", ".").split(".") if p]
        if len(parts) < 2:
            # One squashed token — could be a first name, could be a surname, could
            # be a department. Not worth getting wrong in the first line.
            return ""
        return parts[0].capitalize()
    except Exception:
        return ""


def avatar_html() -> str:
    """The inline avatar, or nothing if the File is missing.

    Missing is a real possibility — the image lives in site storage, not in the
    app — and an acknowledgement without a picture is far better than one that
    fails to send.
    """
    try:
        if not frappe.db.exists("File", {"file_url": AVATAR_URL}):
            return ""
    except Exception:
        return ""

    return (
        f'<img embed="{AVATAR_URL}" width="{AVATAR_PX}" height="{AVATAR_PX}" '
        f'alt="{NAME}" style="display:block;width:{AVATAR_PX}px;'
        f'height:{AVATAR_PX}px;border-radius:50%" />'
    )


def signature(subtitle: str | None = None, include_phone: bool = True) -> str:
    """Echo's block, at the foot of the email where a signature belongs.

    This started life as a band across the top. Mark's read on seeing a real one
    (2026-08-12): the block itself is right, its position was not — an email
    should open with what it has to say, not with who is saying it.

    A table, not flexbox: Outlook renders HTML through Word and ignores flex,
    which would drop the avatar and the name onto separate lines.
    """
    avatar = avatar_html()
    avatar_cell = (
        f'<td style="padding:0 12px 0 0;vertical-align:top">{avatar}</td>'
        if avatar
        else ""
    )
    team = escape_html(subtitle or TEAM)
    phone = (
        f'<div style="font-size:13px;color:{_SOFT};margin-top:2px">{PHONE} if it\'s '
        "urgent and you'd rather talk to a human</div>"
        if include_phone
        else ""
    )

    return (
        f'<div style="border-top:1px solid {_RULE};margin:20px 0 0 0;padding:14px 0 0 0">'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        'style="border-collapse:collapse"><tr>'
        f"{avatar_cell}"
        f'<td style="vertical-align:top;font-family:{_FONT}">'
        f'<div style="font-weight:700;font-size:15px;color:{_INK}">{NAME}</div>'
        f'<div style="font-size:13px;font-style:italic;color:{_SOFT}">{TAGLINE}</div>'
        f'<div style="font-size:11px;letter-spacing:.04em;text-transform:uppercase;'
        f'color:{_FAINT}">{team}</div>'
        f"{phone}"
        "</td></tr></table></div>"
    )


def heading(text: str) -> str:
    return (
        f'<div style="font-weight:700;font-size:14px;color:{_INK};margin:16px 0 4px 0">'
        f"{escape_html(text)}</div>"
    )


def paragraph(html: str) -> str:
    return f'<p style="margin:0 0 10px 0;font-size:14px;color:{_INK}">{html}</p>'


def callout(html: str) -> str:
    return (
        f'<div style="background:#f7ece5;border-left:3px solid #a8542a;'
        f'padding:10px 12px;margin:0 0 12px 0;font-size:14px;color:{_INK}">{html}</div>'
    )


def numbered(items: list[str]) -> str:
    rows = "".join(
        f'<li style="margin:0 0 6px 0">{item}</li>' for item in items if item
    )
    return f'<ol style="margin:0 0 12px 0;padding-left:22px;font-size:14px;color:{_INK}">{rows}</ol>'


def wrap(body: str) -> str:
    """Everything Echo sends, in one container, so the font holds in Outlook."""
    return f'<div style="font-family:{_FONT};line-height:1.6;color:{_INK}">{body}</div>'
