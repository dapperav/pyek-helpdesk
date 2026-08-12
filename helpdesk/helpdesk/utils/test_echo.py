import json
import unittest

import frappe

from helpdesk.helpdesk.utils import echo


def ticket(**fields):
    """A stand-in for an HD Ticket — echo only ever calls .get() on it."""
    return frappe._dict(fields)


class TestEchoUrgency(unittest.TestCase):
    """Urgency decides whether Echo drops the mascot voice, so a wrong answer
    means a dolphin pun landing on someone whose registers are down."""

    def test_enricher_urgency(self):
        for word in ("urgent", "critical", "HIGH", "emergency"):
            doc = ticket(pyek_suggestions=json.dumps({"it_assist": {"urgency": word}}))
            self.assertTrue(echo.is_urgent(doc), word)

    def test_normal_urgency_is_not_urgent(self):
        doc = ticket(pyek_suggestions=json.dumps({"it_assist": {"urgency": "normal"}}))

        self.assertFalse(echo.is_urgent(doc))

    def test_priority_counts_too(self):
        """An agent raising the priority by hand is the same signal."""
        self.assertTrue(echo.is_urgent(ticket(priority="Urgent")))
        self.assertFalse(echo.is_urgent(ticket(priority="Medium")))

    def test_build_sheet_branch(self):
        doc = ticket(
            pyek_suggestions=json.dumps({"build_sheet": {"urgency": "urgent"}})
        )

        self.assertTrue(echo.is_urgent(doc))

    def test_unreadable_suggestions_are_not_urgent(self):
        """A malformed blob must not decide the tone by raising."""
        self.assertFalse(echo.is_urgent(ticket(pyek_suggestions="{not json")))
        self.assertFalse(echo.is_urgent(ticket()))


class TestEchoGreeting(unittest.TestCase):
    def test_separated_local_part(self):
        self.assertEqual(
            echo.first_name(ticket(raised_by="sara.parriott@typhoontexas.com")), "Sara"
        )
        self.assertEqual(
            echo.first_name(ticket(raised_by="mark_immler@pyek.com")), "Mark"
        )

    def test_squashed_local_part_gets_no_greeting(self):
        """'saraparriott@' would greet her as 'Saraparriott' — worse than nothing."""
        self.assertEqual(echo.first_name(ticket(raised_by="saraparriott@x.com")), "")

    def test_machine_and_role_senders_get_no_greeting(self):
        for address in (
            "no-reply@notifications.ui.com",
            "support@vendor.com",
            "order@tickets.typhoontexas.com",
            "svc01@x.com",
        ):
            self.assertEqual(echo.first_name(ticket(raised_by=address)), "", address)

    def test_missing_sender(self):
        self.assertEqual(echo.first_name(ticket()), "")


class TestEchoSettings(unittest.TestCase):
    def test_default_is_used_and_formatted(self):
        text = echo.setting("pyek_echo_greeting", name="0389")

        self.assertIn("#0389", text)

    def test_bad_placeholder_falls_back_to_default(self):
        """An editor typo in HD Settings must not break the send."""
        frappe.db.set_single_value("HD Settings", "pyek_echo_greeting", "Hi {nope}")
        try:
            text = echo.setting("pyek_echo_greeting", name="0389")
            self.assertIn("#0389", text)
        finally:
            frappe.db.set_single_value("HD Settings", "pyek_echo_greeting", "")


class TestEchoMarkup(unittest.TestCase):
    def test_signature_is_a_table_for_outlook(self):
        """Outlook renders through Word and ignores flexbox, which would drop
        the avatar and the name onto separate lines."""
        html = echo.signature()

        self.assertIn("<table", html)
        self.assertIn(echo.NAME, html)
        self.assertIn(echo.TAGLINE, html)

    def test_signature_subtitle_override(self):
        self.assertIn("automated", echo.signature(subtitle=f"{echo.TEAM} · automated"))

    def test_signature_can_drop_the_phone(self):
        self.assertIn(echo.PHONE, echo.signature())
        self.assertNotIn(echo.PHONE, echo.signature(include_phone=False))

    def test_greeting_default_lost_the_flipper(self):
        """Mark's one objection to the first live email (2026-08-12)."""
        self.assertNotIn("flipper", echo.setting("pyek_echo_greeting", name="0393"))
