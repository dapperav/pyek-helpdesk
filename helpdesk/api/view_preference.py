# Per-user list arrangement for saved views.
#
# HD View holds the shared definition of a view; the AP queues are public, so
# writing an agent's sort back into the view record would reorder the queue for
# everyone. These endpoints keep each agent's own arrangement (sort, filters,
# columns, page length) in HD View Preference and always scope it to the
# session user, so one agent can never read or overwrite another's.

import json

import frappe
from frappe import _
from frappe.utils import cint

# The list-state fields we remember. Anything else in the payload is ignored.
PREFERENCE_FIELDS = ("order_by", "filters", "columns", "rows", "page_length")

# Stored as JSON so that an empty choice survives the round trip: "" is how the
# list says "use the doctype's default columns", and it has to come back as ""
# rather than as "nothing was saved".
JSON_FIELDS = ("filters", "columns", "rows")

# Guards against a runaway column/filter payload filling the table.
MAX_FIELD_LENGTH = 100_000


def _require_user() -> str:
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(
            _("You must be signed in to save a view preference."),
            frappe.PermissionError,
        )
    return user


def _dump(value) -> str | None:
    """Serialise a filters/columns/rows value for storage."""
    if value is None:
        return None
    return json.dumps(value)


def _load(value):
    """Parse a stored filters/columns/rows value back out."""
    if value in (None, ""):
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        # Tolerate a hand-edited row rather than breaking the agent's list.
        return value


@frappe.whitelist()
def get_view_preferences(dt: str) -> dict:
    """Every saved arrangement this user has for `dt`, keyed by view name."""
    user = _require_user()
    rows = frappe.get_all(
        "HD View Preference",
        filters={"user": user, "dt": dt},
        fields=["view", *PREFERENCE_FIELDS],
    )

    preferences = {}
    for row in rows:
        preferences[row.view] = {
            "order_by": row.order_by or None,
            "filters": _load(row.filters),
            "columns": _load(row.columns),
            "rows": _load(row.rows),
            "page_length": row.page_length or None,
        }
    return preferences


@frappe.whitelist()
def save_view_preference(dt: str, view: str, preference: dict | str) -> dict:
    """Replace this user's arrangement for one view with `preference`.

    The caller sends the whole snapshot rather than a partial patch, so the
    stored row always matches what the agent is currently looking at.
    """
    user = _require_user()
    if not view:
        frappe.throw(_("A view is required to save a preference."))

    if isinstance(preference, str):
        preference = json.loads(preference)
    if not isinstance(preference, dict):
        frappe.throw(_("Invalid view preference."))

    values = {"page_length": cint(preference.get("page_length")) or 0}
    values["order_by"] = preference.get("order_by") or None
    for field in JSON_FIELDS:
        dumped = _dump(preference.get(field))
        if dumped and len(dumped) > MAX_FIELD_LENGTH:
            frappe.throw(
                _("View preference for {0} is too large to save.").format(field)
            )
        values[field] = dumped

    name = frappe.db.get_value(
        "HD View Preference", {"user": user, "dt": dt, "view": view}, "name"
    )
    if name:
        doc = frappe.get_doc("HD View Preference", name)
    else:
        doc = frappe.new_doc("HD View Preference")
        doc.update({"user": user, "dt": dt, "view": view})

    doc.update(values)
    doc.save(ignore_permissions=True)
    return {"saved": True}


@frappe.whitelist()
def clear_view_preference(dt: str, view: str) -> dict:
    """Drop this user's arrangement so the view falls back to its definition."""
    user = _require_user()
    names = frappe.get_all(
        "HD View Preference",
        filters={"user": user, "dt": dt, "view": view},
        pluck="name",
    )
    for name in names:
        frappe.delete_doc(
            "HD View Preference", name, ignore_permissions=True, force=True
        )
    return {"cleared": len(names)}
