# Copyright (c) 2026, PYEK and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class HDUserPreference(Document):
    """One small per-agent UI setting, keyed by user + pref_key.

    Deliberately a plain key/value store rather than a column per setting: these
    are one-agent-at-a-time display choices (how zoomed the invoice preview
    opens, and whatever comes next), and each one should not need a migration.
    Fieldnames are pref_key/pref_value because `key` and `value` are reserved
    words in MySQL.
    """

    def validate(self):
        self.validate_unique_preference()

    def validate_unique_preference(self):
        duplicate = frappe.db.exists(
            "HD User Preference",
            {
                "user": self.user,
                "pref_key": self.pref_key,
                "name": ("!=", self.name),
            },
        )
        if duplicate:
            frappe.throw(
                _("{0} is already set for {1}").format(self.pref_key, self.user),
                frappe.DuplicateEntryError,
            )
