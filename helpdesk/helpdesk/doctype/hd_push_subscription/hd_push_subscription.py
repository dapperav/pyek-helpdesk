# Copyright (c) 2026, PYEK Group and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class HDPushSubscription(Document):
    """One browser's push endpoint for one agent.

    Deliberately has NO permissions beyond System Manager: a subscription is a
    capability — anyone holding the endpoint plus keys can push to that device —
    so agents never read or write this table directly. Everything goes through
    the whitelisted methods in helpdesk/web_push.py, which scope every operation
    to frappe.session.user.
    """

    pass
