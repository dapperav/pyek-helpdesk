import unittest

from helpdesk.helpdesk.utils.inline_images import (
    embed_site_images,
    inlined_file_urls,
    site_file_path,
)


class TestSiteFilePath(unittest.TestCase):
    """The gate that decides whether a picture travels with the mail or stays a
    URL. Getting it wrong in either direction breaks a picture."""

    def test_relative_upload_paths(self):
        self.assertEqual(site_file_path("/files/logo.png"), "/files/logo.png")
        self.assertEqual(
            site_file_path("/private/files/shot.png"), "/private/files/shot.png"
        )
        self.assertEqual(site_file_path("/assets/helpdesk/img/x.png"), "/assets/helpdesk/img/x.png")

    def test_absolute_url_to_this_site(self):
        """Frappe rewrites relative URLs to absolute when a reply is quoted back
        into a later one, so the second round trip arrives in this shape."""
        self.assertEqual(
            site_file_path("https://it.pyekmail.com/private/files/shot.png"),
            "/private/files/shot.png",
        )

    def test_query_string_is_dropped(self):
        self.assertEqual(
            site_file_path("/private/files/shot.png?fid=abc123"),
            "/private/files/shot.png",
        )

    def test_foreign_and_non_http_sources_are_refused(self):
        """These have nothing on disk to attach — stripping their src would turn
        a working picture into the broken box this module exists to fix."""
        for src in (
            "https://cdn.example.com/logo.png",
            "cid:AbC123",
            "data:image/png;base64,iVBORw0KGgo=",
            "/app/some/other/path.png",
            "",
        ):
            self.assertEqual(site_file_path(src), "", src)


class TestEmbedSiteImages(unittest.TestCase):
    def test_src_is_replaced_not_supplemented(self):
        """The whole bug: an <img> that keeps its src ends up with TWO of them
        once the framework writes src="cid:..." over the embed, and Outlook
        resolved that pair to the URL copy it cannot open."""
        out = embed_site_images('<p><img src="/private/files/shot.png"></p>')

        self.assertIn('embed="/private/files/shot.png"', out)
        self.assertNotIn("src=", out)

    def test_sizing_attributes_survive(self):
        """Outlook ignores max-width on images, so the width attribute is the
        only thing standing between a 3000px screenshot and a wrecked layout."""
        out = embed_site_images(
            '<img src="/private/files/shot.png" width="640" height="360" '
            'alt="Till 3" style="max-width:100%;height:auto">'
        )

        self.assertIn('width="640"', out)
        self.assertIn('height="360"', out)
        self.assertIn('alt="Till 3"', out)
        self.assertIn("max-width:100%", out)

    def test_external_image_is_left_alone(self):
        out = embed_site_images('<img src="https://cdn.example.com/logo.png">')

        self.assertIn('src="https://cdn.example.com/logo.png"', out)
        self.assertNotIn("embed=", out)

    def test_srcset_is_dropped_on_embedded_images(self):
        """A surviving srcset would win over the cid: src and put us right back
        where we started."""
        out = embed_site_images(
            '<img src="/files/logo.png" srcset="/files/logo@2x.png 2x">'
        )

        self.assertNotIn("srcset", out)
        self.assertIn('embed="/files/logo.png"', out)

    def test_mixed_thread_embeds_only_what_it_owns(self):
        """Ticket #0606's shape: a signature logo we host, a hotlinked tracker,
        and the screenshot the agent pasted."""
        out = embed_site_images(
            '<img src="/files/sig-logo.png">'
            '<img src="https://track.example.com/p.gif">'
            '<img src="/private/files/screenshot.png">'
        )

        self.assertIn('embed="/files/sig-logo.png"', out)
        self.assertIn('embed="/private/files/screenshot.png"', out)
        self.assertIn('src="https://track.example.com/p.gif"', out)
        self.assertNotIn('src="/files/sig-logo.png"', out)
        self.assertNotIn('src="/private/files/screenshot.png"', out)

    def test_outlook_conditional_comments_are_stripped(self):
        out = embed_site_images("<p>Hi</p><!--[if mso]><i>x</i><![endif]-->")

        self.assertNotIn("mso", out)
        self.assertIn("Hi", out)

    def test_video_keeps_its_src(self):
        """Deliberately unchanged: no mail client plays a src="cid:..." video,
        so rewriting it would trade one dead tag for another."""
        out = embed_site_images('<video src="/private/files/clip.mp4"></video>')

        self.assertIn('src="/private/files/clip.mp4"', out)
        self.assertIn('embed="/private/files/clip.mp4"', out)

    def test_empty_content(self):
        self.assertEqual(embed_site_images(""), "")
        self.assertEqual(embed_site_images(None), "")


class TestTicket0606(unittest.TestCase):
    """The two failures in one real delivered message (Email Queue 1gl2vm80iu,
    ticket #0606, 2026-08-26 14:14). Six pictures, one cid: reference between
    them, and a red X in Outlook for all six."""

    # A signature graphic that arrived on an inbound Outlook mail. Frappe stores
    # these with a ?fid= query, which rode into the embed attribute and made
    # get_filecontent_from_path miss the file on disk — so the framework
    # stripped the embed and left only a private URL nobody can open.
    SIGNATURE_SRC = "/private/files/image2bf151.png?fid=ee37e5b298"

    def test_pasted_screenshot_ships_one_src(self):
        out = embed_site_images(
            '<img data-align="center" height="766" '
            'src="/private/files/image43ce97.png" width="1407">'
        )

        self.assertEqual(out.count("src="), 0)
        self.assertIn('embed="/private/files/image43ce97.png"', out)
        self.assertIn('width="1407"', out)
        self.assertIn('data-align="center"', out)

    def test_query_string_never_reaches_the_embed(self):
        """The whole file lookup is a path check against disk; a ?fid= on the
        end makes it miss, and a missed lookup deletes the embed outright."""
        out = embed_site_images(f'<img alt="image003.png" src="{self.SIGNATURE_SRC}">')

        self.assertIn('embed="/private/files/image2bf151.png"', out)
        self.assertNotIn("fid=", out)
        self.assertIn('alt="image003.png"', out)


class TestInlinedFileUrls(unittest.TestCase):
    """Callers use this to keep a picture from arriving twice — once in the text
    and once as a download beside it."""

    def test_reads_src_and_embed_alike(self):
        before = '<img src="/private/files/a.png"><img src="/files/b.png">'
        after = embed_site_images(before)

        self.assertEqual(
            inlined_file_urls(before), {"/private/files/a.png", "/files/b.png"}
        )
        self.assertEqual(inlined_file_urls(after), inlined_file_urls(before))

    def test_ignores_foreign_images(self):
        self.assertEqual(
            inlined_file_urls('<img src="https://cdn.example.com/logo.png">'), set()
        )

    def test_empty_content(self):
        self.assertEqual(inlined_file_urls(""), set())


if __name__ == "__main__":
    unittest.main()
