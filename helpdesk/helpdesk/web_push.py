# Copyright (c) 2026, PYEK Group and contributors
# For license information, please see license.txt

"""Web push for the PMIT PWA.

Why this exists: an installed PWA is an icon on a home screen. With the app
closed, an assignment reached an agent only by email — the in-app count sat on
the "Menu" tab where you had to already be looking. Badging fixed the "app is
open somewhere" case; this fixes the "app is closed" case.

## The service-worker constraint (read before changing the SW)

PR 95 shipped `selfDestroying: true` because a *caching* service worker served
stale JS chunks after a deploy and wedged the PWA. Push needs a service worker,
so that flag is gone — but the replacement (`desk/src/sw.js`) does no caching
and has NO fetch handler at all. It cannot reintroduce that bug, because it
never answers a request. Do not add caching to it.

## Keys

VAPID keys are generated on first use and persisted to the SITE CONFIG, not the
database, so the private key doesn't sit in a table anyone with DB read can see.
That also means zero manual setup: the first call to `get_vapid_public_key`
mints them. If you'd rather manage them yourself, set `pyek_vapid_public_key`
and `pyek_vapid_private_key` in site config and this never generates anything.

## Failure policy

Sending is best-effort and fires from a background job. A push that fails must
never break the thing that triggered it — an assignment has to succeed even if
Apple's push service is down, or if a library signature here turns out to be
wrong. Every failure path logs to Error Log and returns.
"""

import hashlib
import json

import frappe
from frappe.utils import now

# Endpoints reply with these when a subscription is permanently dead (the user
# uninstalled the PWA, cleared data, or the browser rotated the endpoint). Prune
# on sight, otherwise the table grows forever and every send retries a corpse.
DEAD_SUBSCRIPTION_CODES = (404, 410)

PUBLIC_KEY_SETTING = "pyek_vapid_public_key"
PRIVATE_KEY_SETTING = "pyek_vapid_private_key"

# Per-agent push preferences, stored as Check fields on HD Agent (all default
# ON). With four notification sources live, the only alternative opt-out is
# disabling push entirely — which is how the whole feature gets muted.
# `notification_type` values are the HD Notification Select options.
PUSH_PREF_FIELDS = {
    "Assignment": "pyek_push_assignment",
    "Mention": "pyek_push_mention",
    "Reaction": "pyek_push_reaction",
    "Team": "pyek_push_team",
    "Reply": "pyek_push_reply",
    "SLA due": "pyek_push_sla",
}

# Quiet hours (Mark's call, 2026-08-14 review): default ON for everyone,
# 21:00–07:00 SITE time (US Central), Urgent tickets still push. A NULL on an
# existing agent row reads as enabled-with-defaults, so shipping this changes
# nights immediately without a backfill. Per-agent adjustable in settings.
QUIET_ENABLED_FIELD = "pyek_push_quiet"
QUIET_START_FIELD = "pyek_push_quiet_start"
QUIET_END_FIELD = "pyek_push_quiet_end"
QUIET_START_DEFAULT = "21:00"
QUIET_END_DEFAULT = "07:00"

# VAPID requires a contact address so a push service can reach us about abuse.
# A constant rather than a DB lookup: HD Settings has no outgoing-account field,
# and this runs in a background job where a failed lookup would cost the send.
VAPID_CONTACT = "help.pyek@pyekgroup.com"


def _endpoint_hash(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()


def _generate_vapid_keys() -> tuple[str, str]:
    """Mint a P-256 keypair in the raw base64url form both sides want.

    The browser's `applicationServerKey` must be the uncompressed X9.62 public
    point (65 bytes), and pywebpush accepts the private key as the raw 32-byte
    scalar. Returning both in that shape avoids PEM round-tripping.
    """
    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid
    from py_vapid.utils import b64urlencode

    vapid = Vapid()
    vapid.generate_keys()

    private_scalar = vapid.private_key.private_numbers().private_value
    private_b64 = b64urlencode(private_scalar.to_bytes(32, "big"))
    public_b64 = b64urlencode(
        vapid.public_key.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
    )
    return public_b64, private_b64


def _get_keys() -> tuple[str | None, str | None]:
    """Read the keypair from site config, generating and persisting it once."""
    public = frappe.conf.get(PUBLIC_KEY_SETTING)
    private = frappe.conf.get(PRIVATE_KEY_SETTING)
    if public and private:
        return public, private

    try:
        from frappe.installer import update_site_config

        public, private = _generate_vapid_keys()
        # Persist so every worker and every later request signs with the SAME
        # key. Re-minting per process would invalidate every live subscription.
        update_site_config(PUBLIC_KEY_SETTING, public)
        update_site_config(PRIVATE_KEY_SETTING, private)
        # update_site_config rewrites the file; keep this process consistent too.
        frappe.conf[PUBLIC_KEY_SETTING] = public
        frappe.conf[PRIVATE_KEY_SETTING] = private
        return public, private
    except Exception:
        frappe.log_error(
            title="PMIT push: could not provision VAPID keys",
            message=frappe.get_traceback(),
        )
        return None, None


@frappe.whitelist()
def get_vapid_public_key() -> str:
    """The application server key the browser needs to subscribe.

    Public by design — it's the half that's meant to be handed out — but still
    agent-gated so we're not minting keys for anonymous traffic.
    """
    from helpdesk.utils import is_agent

    if not is_agent():
        frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

    public, _ = _get_keys()
    return public or ""


@frappe.whitelist()
def subscribe(subscription: str) -> dict:
    """Store (or refresh) this browser's push subscription for the current user.

    Keyed on a hash of the endpoint so a browser that re-subscribes updates its
    row instead of piling up duplicates — re-subscription is routine, because
    browsers rotate endpoints on their own schedule.
    """
    from helpdesk.utils import is_agent

    if not is_agent():
        frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

    if isinstance(subscription, str):
        subscription = json.loads(subscription)

    endpoint = (subscription or {}).get("endpoint")
    keys = (subscription or {}).get("keys") or {}
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")

    if not (endpoint and p256dh and auth):
        frappe.throw(frappe._("Incomplete push subscription"))

    digest = _endpoint_hash(endpoint)
    user_agent = frappe.get_request_header("User-Agent") or ""

    existing = frappe.db.get_value(
        "HD Push Subscription", {"endpoint_hash": digest}, "name"
    )
    if existing:
        doc = frappe.get_doc("HD Push Subscription", existing)
        # An endpoint belongs to whoever is holding the browser now — a shared
        # park iPad can change hands between agents.
        doc.user = frappe.session.user
        doc.p256dh = p256dh
        doc.auth = auth
        doc.user_agent = user_agent[:140]
        doc.last_seen = now()
        doc.save(ignore_permissions=True)
        return {"status": "updated"}

    frappe.get_doc(
        {
            "doctype": "HD Push Subscription",
            "user": frappe.session.user,
            "endpoint_hash": digest,
            "endpoint": endpoint,
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": user_agent[:140],
            "last_seen": now(),
        }
    ).insert(ignore_permissions=True)
    return {"status": "created"}


@frappe.whitelist()
def unsubscribe(endpoint: str) -> dict:
    """Forget one endpoint. Scoped to the caller so nobody can mute a colleague."""
    name = frappe.db.get_value(
        "HD Push Subscription",
        {"endpoint_hash": _endpoint_hash(endpoint), "user": frappe.session.user},
        "name",
    )
    if name:
        frappe.delete_doc("HD Push Subscription", name, ignore_permissions=True)
    return {"status": "ok"}


def _parse_hhmm(value: str | None, fallback: str) -> tuple[int, int]:
    """'21:00' -> (21, 0). Anything unparseable falls back to the default —
    a typo in a settings field must not decide whether pushes flow."""
    raw = (value or fallback).strip()
    try:
        h, m = raw.split(":")
        h, m = int(h), int(m)
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
    except Exception:
        pass
    h, m = fallback.split(":")
    return int(h), int(m)


def _in_quiet_hours(user: str) -> bool:
    """Is `user` inside their quiet window right now (site time)?

    Quiet hours default ON (NULL reads as enabled with the 21:00–07:00
    window). Unlike the type prefs this fails CLOSED-to-noise, not
    closed-to-silence: a lookup ERROR returns False (push flows) so a broken
    query can't mute urgent traffic — only a working window suppresses.
    """
    try:
        row = frappe.db.get_value(
            "HD Agent",
            {"user": user},
            [QUIET_ENABLED_FIELD, QUIET_START_FIELD, QUIET_END_FIELD],
            as_dict=True,
        )
        if not row:
            return False
        enabled = row.get(QUIET_ENABLED_FIELD)
        if enabled is not None and not int(enabled):
            return False
        sh, sm = _parse_hhmm(row.get(QUIET_START_FIELD), QUIET_START_DEFAULT)
        eh, em = _parse_hhmm(row.get(QUIET_END_FIELD), QUIET_END_DEFAULT)
        now = frappe.utils.now_datetime()
        minutes = now.hour * 60 + now.minute
        start, end = sh * 60 + sm, eh * 60 + em
        if start == end:
            return False  # zero-length window = no quiet hours
        if start < end:
            return start <= minutes < end
        # Overnight window (the default 21:00–07:00 wraps midnight).
        return minutes >= start or minutes < end
    except Exception:
        frappe.log_error(
            title="PMIT push: quiet-hours lookup failed",
            message=f"user={user}\n{frappe.get_traceback()}",
        )
        return False


def should_push(
    user: str, notification_type: str | None, ticket: str | None = None
) -> bool:
    """Has `user` opted out of pushes for this notification type — or is it
    their quiet hours?

    Type prefs fail OPEN, matching the team-notification filter's policy: an
    unknown type, a missing agent row, or a lookup error must never silently
    mute a notification. Only an explicit 0 on the agent's own pref field
    skips. Quiet hours suppress everything except tickets whose priority is
    Urgent at send time (a park-offline alert still buzzes at 2am).
    """
    field = PUSH_PREF_FIELDS.get(notification_type or "")
    if field:
        try:
            value = frappe.db.get_value("HD Agent", {"user": user}, field)
            if value is not None and not int(value):
                return False
        except Exception:
            frappe.log_error(
                title="PMIT push: pref lookup failed",
                message=f"user={user} type={notification_type}\n{frappe.get_traceback()}",
            )

    if _in_quiet_hours(user):
        try:
            priority = (
                frappe.db.get_value("HD Ticket", ticket, "priority")
                if ticket
                else None
            )
        except Exception:
            priority = None
        if priority != "Urgent":
            return False

    return True


@frappe.whitelist()
def get_push_prefs() -> dict:
    """The session agent's per-type push switches, for the settings UI."""
    from helpdesk.utils import is_agent

    if not is_agent():
        frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

    row = frappe.db.get_value(
        "HD Agent",
        {"user": frappe.session.user},
        list(PUSH_PREF_FIELDS.values())
        + [QUIET_ENABLED_FIELD, QUIET_START_FIELD, QUIET_END_FIELD],
        as_dict=True,
    )
    # No agent row (should not happen behind is_agent, but fail open the same
    # way the send path does): everything reads as enabled.
    prefs = {
        key: bool(int(row[field])) if row and row.get(field) is not None else True
        for key, field in PUSH_PREF_FIELDS.items()
    }
    quiet_enabled = row.get(QUIET_ENABLED_FIELD) if row else None
    prefs["_quiet"] = {
        "enabled": bool(int(quiet_enabled)) if quiet_enabled is not None else True,
        "start": "%02d:%02d"
        % _parse_hhmm(row.get(QUIET_START_FIELD) if row else None, QUIET_START_DEFAULT),
        "end": "%02d:%02d"
        % _parse_hhmm(row.get(QUIET_END_FIELD) if row else None, QUIET_END_DEFAULT),
    }
    return prefs


@frappe.whitelist()
def set_push_pref(notification_type: str, enabled) -> dict:
    """Flip one of the session agent's push switches. Scoped to the caller."""
    from helpdesk.utils import is_agent

    if not is_agent():
        frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

    field = PUSH_PREF_FIELDS.get(notification_type)
    if not field:
        frappe.throw(frappe._("Unknown notification type"))

    name = frappe.db.get_value("HD Agent", {"user": frappe.session.user}, "name")
    if not name:
        frappe.throw(frappe._("No agent record"))

    value = 1 if frappe.utils.cint(enabled) else 0
    frappe.db.set_value("HD Agent", name, field, value)
    return {notification_type: bool(value)}


@frappe.whitelist()
def set_quiet_hours(enabled, start: str | None = None, end: str | None = None) -> dict:
    """Set the session agent's quiet window. Times are HH:MM, site time."""
    import re as _re

    from helpdesk.utils import is_agent

    if not is_agent():
        frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

    name = frappe.db.get_value("HD Agent", {"user": frappe.session.user}, "name")
    if not name:
        frappe.throw(frappe._("No agent record"))

    hhmm = _re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")
    updates = {QUIET_ENABLED_FIELD: 1 if frappe.utils.cint(enabled) else 0}
    for field, value in ((QUIET_START_FIELD, start), (QUIET_END_FIELD, end)):
        if value is not None:
            if not hhmm.match(value.strip()):
                frappe.throw(frappe._("Times must be HH:MM, e.g. 21:00"))
            updates[field] = value.strip()
    for field, value in updates.items():
        frappe.db.set_value("HD Agent", name, field, value)
    return {"ok": True}


def notify_user(user: str, title: str, body: str, url: str, tag: str | None = None):
    """Queue a push to every device `user` has registered.

    Enqueued rather than sent inline: the caller is usually an assignment or a
    mention, and neither should wait on (or fail because of) a third-party push
    service.
    """
    if not user or user == "Administrator":
        return
    if not frappe.db.exists("HD Push Subscription", {"user": user}):
        return

    frappe.enqueue(
        "helpdesk.helpdesk.web_push.send_now",
        queue="short",
        enqueue_after_commit=True,
        user=user,
        title=title,
        body=body,
        url=url,
        tag=tag,
    )


def send_now(user: str, title: str, body: str, url: str, tag: str | None = None):
    """Background worker: deliver to each of the user's endpoints, prune corpses."""
    try:
        from pywebpush import WebPushException, webpush
    except Exception:
        frappe.log_error(
            title="PMIT push: pywebpush unavailable",
            message=frappe.get_traceback(),
        )
        return

    public, private = _get_keys()
    if not private:
        return

    payload = json.dumps(
        {"title": title, "body": body, "url": url, "tag": tag or "pmit"}
    )
    claims = {"sub": f"mailto:{VAPID_CONTACT}"}

    rows = frappe.get_all(
        "HD Push Subscription",
        filters={"user": user},
        fields=["name", "endpoint", "p256dh", "auth"],
    )

    for row in rows:
        try:
            webpush(
                subscription_info={
                    "endpoint": row.endpoint,
                    "keys": {"p256dh": row.p256dh, "auth": row.auth},
                },
                data=payload,
                vapid_private_key=private,
                vapid_claims=dict(claims),
            )
        except WebPushException as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in DEAD_SUBSCRIPTION_CODES:
                frappe.delete_doc(
                    "HD Push Subscription", row.name, ignore_permissions=True
                )
                continue
            frappe.log_error(
                title="PMIT push: send failed",
                message=f"user={user} status={status}\n{frappe.get_traceback()}",
            )
        except Exception:
            # Never let a push problem escape into the caller's transaction.
            frappe.log_error(
                title="PMIT push: unexpected send error",
                message=f"user={user}\n{frappe.get_traceback()}",
            )

    frappe.db.commit()
