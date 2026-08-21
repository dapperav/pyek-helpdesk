# Small per-agent UI settings.
#
# These are display choices that belong to one agent and nobody else — how
# zoomed the invoice preview opens, for instance. Both endpoints scope every
# read and write to frappe.session.user, so an agent can only ever see or
# change their own.

import frappe
from frappe import _

# Settings the frontend is allowed to store. An allowlist keeps this from
# turning into an open per-user scratch space that anything can write to.
ALLOWED_KEYS = {"ap_invoice_zoom"}

MAX_VALUE_LENGTH = 200


def _require_user() -> str:
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(
            _("You must be signed in to save a preference."), frappe.PermissionError
        )
    return user


def _validate_key(key: str) -> str:
    if key not in ALLOWED_KEYS:
        frappe.throw(_("{0} is not a known preference.").format(key))
    return key


@frappe.whitelist()
def get_user_preferences() -> dict:
    """This user's settings, keyed by pref_key."""
    user = _require_user()
    rows = frappe.get_all(
        "HD User Preference",
        filters={"user": user, "pref_key": ("in", sorted(ALLOWED_KEYS))},
        fields=["pref_key", "pref_value"],
    )
    return {row.pref_key: row.pref_value for row in rows}


@frappe.whitelist()
def set_user_preference(key: str, value: str) -> dict:
    """Store one setting for this user."""
    user = _require_user()
    _validate_key(key)

    value = "" if value is None else str(value)
    if len(value) > MAX_VALUE_LENGTH:
        frappe.throw(_("That preference value is too long to save."))

    name = frappe.db.get_value(
        "HD User Preference", {"user": user, "pref_key": key}, "name"
    )
    if name:
        doc = frappe.get_doc("HD User Preference", name)
    else:
        doc = frappe.new_doc("HD User Preference")
        doc.update({"user": user, "pref_key": key})

    doc.pref_value = value
    doc.save(ignore_permissions=True)
    return {"saved": True}
