"""The SOS life ring (Mark's approved Wave design, 2026-08-15).

When the site is objectively slammed — awaiting-first-reply at or above the
threshold — a life ring surfaces on the mobile Home. Tapping it (behind a
confirm) pushes to EVERY agent with a registered device, deliberately
bypassing per-type preferences and quiet hours: it goes through
`notify_user` directly rather than `should_push`, which is the whole point
of an SOS. Guardrails: the threshold is enforced server-side too, one SOS
per site per 30 minutes, and the sender is named in the push.
"""

import frappe
from frappe import _

from helpdesk.utils import agent_only

# Tunable via a `pyek_sos_threshold` Int field on HD Settings if one is ever
# provisioned (same guard pattern as pyek_auto_closed); this is the default.
SOS_THRESHOLD_DEFAULT = 8
SOS_COOLDOWN_SECONDS = 30 * 60
_CACHE_KEY = "pyek_sos_last_sent"


def _threshold() -> int:
    try:
        if frappe.get_meta("HD Settings").has_field("pyek_sos_threshold"):
            value = frappe.db.get_single_value("HD Settings", "pyek_sos_threshold")
            if value:
                return int(value)
    except Exception:
        pass
    return SOS_THRESHOLD_DEFAULT


def _cooldown_remaining() -> int:
    last = frappe.cache().get_value(_CACHE_KEY)
    if not last:
        return 0
    elapsed = frappe.utils.now_datetime() - frappe.utils.get_datetime(last)
    remaining = SOS_COOLDOWN_SECONDS - int(elapsed.total_seconds())
    return max(0, remaining)


@frappe.whitelist()
@agent_only
def get_sos_state() -> dict:
    """What the buoy needs: the trigger threshold and any active cooldown."""
    return {
        "threshold": _threshold(),
        "cooldown_remaining": _cooldown_remaining(),
    }


@frappe.whitelist()
@agent_only
def send_sos() -> dict:
    from helpdesk.api.pyek_home import get_home_stats
    from helpdesk.helpdesk.web_push import notify_user

    waiting = int(get_home_stats().get("awaiting_first_reply") or 0)
    threshold = _threshold()
    if waiting < threshold:
        frappe.throw(
            _("SOS needs at least {0} tickets awaiting a first reply (currently {1}).").format(
                threshold, waiting
            )
        )

    remaining = _cooldown_remaining()
    if remaining:
        frappe.throw(
            _("An SOS already went out — the next one unlocks in {0} minutes.").format(
                max(1, remaining // 60)
            )
        )

    sender = frappe.session.user
    sender_name = (
        frappe.db.get_value("User", sender, "full_name") or sender
    ).split(" ")[0]

    # Everyone with a registered device except the person yelling.
    recipients = [
        r.user
        for r in frappe.get_all(
            "HD Push Subscription", fields=["user"], distinct=True
        )
        if r.user and r.user != sender
    ]

    view = frappe.db.get_value(
        "HD View", {"label": "Awaiting first reply", "public": 1}, "name"
    )
    url = f"/helpdesk/tickets?view={view}" if view else "/helpdesk/tickets"

    title = _("🚨 SOS from {0}").format(sender_name)
    body = _(
        "{0} tickets waiting on a first reply — queues are overflowing. Jump in if you can."
    ).format(waiting)

    for user in recipients:
        notify_user(user, title=title, body=body, url=url, tag="pyek-sos")

    frappe.cache().set_value(
        _CACHE_KEY, frappe.utils.now(), expires_in_sec=SOS_COOLDOWN_SECONDS
    )
    # The record for the log: who pulled the ring, when, and how wide it went.
    # Error Log is where every PMIT push event already lives, so it goes there
    # too, greppable under one title prefix.
    frappe.log_error(
        title=f"PMIT SOS: {sender} alerted {len(recipients)} agents",
        message=f"waiting={waiting} threshold={threshold} recipients={recipients}",
    )

    return {"sent_to": len(recipients), "waiting": waiting}
