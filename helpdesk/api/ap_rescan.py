"""Proxy the AP helpdesk "Scan invoice" button to the enricher's on-demand
re-extract endpoint.

The enricher poll loop only ever revisits pyek_enriched=0 tickets, so a vendor
reply that arrives WITH an invoice on an already-processed ticket is never re-read.
This calls the enricher's POST /rescan to re-extract one ticket's CURRENT
attachments and repopulate the AP fields.

The shared secret stays server-side (site_config) so the browser never sees it and
the SPA makes no cross-origin call.

site_config.json keys:
  rescan_token  (required)  the X-Auth-Token shared secret set on the enricher
  rescan_url    (optional)  defaults to the enricher's Railway /rescan URL
"""
import frappe
import requests
from frappe import _

DEFAULT_RESCAN_URL = "https://pyek-ap-enricher-production.up.railway.app/rescan"


@frappe.whitelist()
def rescan(ticket: str):
    """Re-extract one ticket's current invoice attachments and repopulate the AP
    fields. Returns {"ok": True, "rescanned": 0|1} or {"ok": False, "error": ...}."""
    if not ticket:
        frappe.throw(_("A ticket is required."))
    if not frappe.db.exists("HD Ticket", ticket):
        frappe.throw(_("Ticket {0} not found.").format(ticket))
    # Caller must be able to see the ticket (agents can); also blocks poking at
    # arbitrary ids.
    frappe.has_permission("HD Ticket", "read", doc=ticket, throw=True)

    # Token comes from site_config if set, else the "Rescan Token" field on the
    # HD Settings single (an admin-only, server-read field — never sent to the
    # browser). FC's site-config UI only allows preset keys, so HD Settings is the
    # practical place to paste it.
    token = frappe.conf.get("rescan_token") or frappe.db.get_single_value(
        "HD Settings", "rescan_token"
    )
    if not token:
        return {"ok": False, "error": _("Invoice scanning isn't configured yet.")}
    url = (
        frappe.conf.get("rescan_url")
        or frappe.db.get_single_value("HD Settings", "rescan_url")
        or DEFAULT_RESCAN_URL
    )

    try:
        resp = requests.post(
            url,
            json={"ticket": ticket},
            headers={"X-Auth-Token": token, "Content-Type": "application/json"},
            timeout=120,
        )
    except requests.RequestException as exc:
        frappe.log_error(f"AP rescan {ticket}: {exc}", "AP rescan")
        return {"ok": False, "error": _("Couldn't reach the scanner. Try again.")}

    if resp.status_code != 200:
        frappe.log_error(
            f"AP rescan {ticket}: HTTP {resp.status_code} {resp.text[:200]}",
            "AP rescan",
        )
        return {"ok": False, "error": _("Scan failed ({0}).").format(resp.status_code)}

    try:
        data = resp.json()
    except ValueError:
        data = {}
    return {"ok": True, "rescanned": data.get("rescanned", 0)}


def ensure_rescan_field():
    """Idempotently add a 'Rescan Token' field to HD Settings so the shared secret
    can be pasted in the admin (System-Manager only, server-read — never sent to the
    browser). FC's site-config UI only allows preset keys, so this is where the token
    lives. Runs on after_migrate. Data (not Password) so `get_single_value` returns it
    verbatim to match the enricher's X-Auth-Token."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    create_custom_fields(
        {
            "HD Settings": [
                {
                    "fieldname": "rescan_token",
                    "label": "Rescan Token",
                    "fieldtype": "Data",
                    "description": (
                        "Shared secret (X-Auth-Token) for the AP invoice enricher's "
                        "/rescan endpoint. Paste the value of the enricher's "
                        "RESCAN_TOKEN Railway variable here."
                    ),
                }
            ]
        },
        ignore_validate=True,
    )
