import unittest

from helpdesk.helpdesk.utils.agent_email import (
    INTERNAL_SENTINEL,
    REPLY_MARKER,
    split_aliases,
    strip_reply,
)

# What a mail client quotes back below the marker: the conversation, then the
# internal notes that must never reach the requester.
QUOTED = (
    f'<div style="color:#98a5b3">{REPLY_MARKER}</div>'
    "<div>from user@pyek.com</div><div>My laptop wont boot</div>"
    f'<div class="{INTERNAL_SENTINEL}">Internal note — out of warranty</div>'
)


class TestStripReply(unittest.TestCase):
    """strip_reply decides what leaves the building, so the interesting cases
    are the ones where it must refuse rather than guess."""

    def test_keeps_reply_and_drops_quoted_history(self):
        reply = strip_reply("<p>Rebooting it now.</p>" + QUOTED)

        self.assertIn("Rebooting it now.", reply)
        self.assertNotIn("laptop wont boot", reply)
        self.assertNotIn(INTERNAL_SENTINEL, reply)

    def test_marker_split_across_tags(self):
        mangled = REPLY_MARKER.replace("your reply", "your <b>reply</b>")
        reply = strip_reply(f"<p>Done.</p><div>{mangled}</div><div>old thread</div>")

        self.assertIn("Done.", reply)
        self.assertNotIn("old thread", reply)

    def test_marker_with_non_breaking_spaces(self):
        """Outlook rewrites the spaces inside the marker as &nbsp;."""
        nbsp = REPLY_MARKER.replace(" ", "&nbsp;")
        reply = strip_reply(f"<p>On it.</p><div>{nbsp}</div><div>old thread</div>")

        self.assertIn("On it.", reply)
        self.assertNotIn("old thread", reply)

    def test_marker_wrapped_across_lines(self):
        wrapped = REPLY_MARKER.replace(" above ", "\n   above\n")
        reply = strip_reply(f"<p>Sure.</p><div>{wrapped}</div><div>old thread</div>")

        self.assertIn("Sure.", reply)
        self.assertNotIn("old thread", reply)

    def test_refuses_when_marker_is_missing(self):
        self.assertIsNone(strip_reply("<p>Sure.</p><div>old thread</div>"))

    def test_refuses_when_an_internal_note_survives_the_cut(self):
        leaked = f'<p>Sure.</p><div class="{INTERNAL_SENTINEL}">secret</div>' + QUOTED

        self.assertIsNone(strip_reply(leaked))

    def test_refuses_when_nothing_was_typed(self):
        self.assertIsNone(strip_reply("<p> </p>" + QUOTED))

    def test_refuses_empty_input(self):
        self.assertIsNone(strip_reply(""))
        self.assertIsNone(strip_reply(None))


class TestSplitAliases(unittest.TestCase):
    def test_separators_and_case(self):
        raw = "Mark.Immler@pyek.com, mi@pyekgroup.com;\n MARK@pyek.com "

        self.assertEqual(
            split_aliases(raw),
            {"mark.immler@pyek.com", "mi@pyekgroup.com", "mark@pyek.com"},
        )

    def test_strips_the_entra_proxyaddresses_prefix(self):
        """proxyAddresses come out of Entra as SMTP:a@b / smtp:c@d."""
        self.assertEqual(
            split_aliases("SMTP:mark.immler@pyek.com\nsmtp:mi@pyekgroup.com"),
            {"mark.immler@pyek.com", "mi@pyekgroup.com"},
        )

    def test_ignores_junk_and_empties(self):
        self.assertEqual(split_aliases(""), set())
        self.assertEqual(split_aliases(None), set())
        self.assertEqual(split_aliases("not-an-address, , x@y.com"), {"x@y.com"})
