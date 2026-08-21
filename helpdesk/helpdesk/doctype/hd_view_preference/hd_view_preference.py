# Copyright (c) 2026, PYEK and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class HDViewPreference(Document):
    """One user's personal list arrangement for one HD View.

    A saved view is a shared definition — the AP queues are public and several
    agents work out of the same ones. Sorting a queue used to either be thrown
    away on navigation or (for managers) rewrite the view for everybody. This
    doctype is the per-user layer in between: it records how *this* agent last
    left the list, and the view record itself is never touched.
    """

    def validate(self):
        self.validate_unique_preference()

    def validate_unique_preference(self):
        duplicate = frappe.db.exists(
            "HD View Preference",
            {
                "user": self.user,
                "dt": self.dt,
                "view": self.view,
                "name": ("!=", self.name),
            },
        )
        if duplicate:
            frappe.throw(
                _("A preference for {0} already exists for {1}").format(
                    self.view, self.user
                ),
                frappe.DuplicateEntryError,
            )
