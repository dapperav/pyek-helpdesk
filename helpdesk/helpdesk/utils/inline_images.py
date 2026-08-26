"""Make the pictures in an outgoing email actually render.

Mark, 2026-08-26, with a screenshot of ticket #0606 open in Outlook: a red X
where every screenshot should be, the requester's own signature graphics broken
in the quoted history, and the actual bytes sitting in a "6 attachments (1 MB)"
row he'd have to click through to see any of it. *"we like to have inline images
for easy read and without the end users having to download them to see."*

## What was wrong

Getting a picture into a mail body is a two-step handoff, and nobody owned both
ends of it. Helpdesk's ``parse_content`` copied an ``<img>``'s ``src`` into an
``embed`` attribute — the marker Frappe looks for — but left the original
``src`` sitting there. Frappe's ``replace_filename_with_cid`` then does a
*literal* substitution of ``embed='…'`` for ``src="cid:…"`` (frappe/email/
email_body.py, identical in v15 and v16). That produced **two failures**, both
visible in one delivered message: Email Queue ``1gl2vm80iu``, ticket #0606,
2026-08-26 14:14 — six pictures, one ``cid:`` reference between them, a red X
in Outlook for all six.

**One: the tag shipped with two src attributes.** The screenshot an agent pasted
went down the wire as::

    <img data-align="center" src="cid:P0re5xWX13" height="766"
         src="https://it.pyekmail.com/private/files/image43ce97.png" width="1407">

Outlook renders HTML through Word, and Word resolved that to the URL copy — a
private file behind a login it doesn't have. The ``cid:`` part it was handed,
pointing at the real picture already attached to the very same message, was
never used. (Do not reason about which duplicate "wins" from the HTML spec: the
spec says first, the observed behaviour here was the URL. The fix is to not
create the duplicate at all.)

**Two: a ``?fid=`` query killed the lookup outright.** The other five were
signature graphics off an inbound Outlook mail, which Frappe stores with a
cache-busting query — ``/private/files/image2bf151.png?fid=ee37e5b298``. That
whole string went into the ``embed``, and ``get_filecontent_from_path`` is a
path check against disk, so it missed. A missed lookup makes Frappe **delete the
embed attribute**, leaving nothing but the private URL. Those five were never
even attached inline; they were only ever downloads.

Public ``/files/`` uploads survived both by accident: their URL happens to
resolve without a session. That is why one email could show a signature logo
perfectly and a screenshot as a red X — the tell that made this diagnosable.

## The rule

When we hand the mail a file that lives on this site, the ``src`` has to **go**,
not be joined by an ``embed``. There is nothing left for a URL to do: the bytes
travel with the message.

External images are the opposite case and must be left completely alone. A
hotlinked logo or a tracking pixel has nothing on disk to attach, so stripping
its ``src`` would turn a working picture into the broken box we're fixing. It
keeps its ``src`` and gets no ``embed``.

``<video>`` is deliberately untouched. It has the same duplicate-src shape, but
no mail client plays a ``src="cid:…"`` video, so "fixing" it would trade a
harmless dead tag for a harmless dead tag while quietly changing what gets
attached. Left exactly as it was.
"""

from bs4 import BeautifulSoup, Comment

# Where a file this site owns can live. ``/assets/`` is app static (Frappe's own
# ``get_filecontent_from_path`` reads it), the other two are uploads.
SITE_FILE_PREFIXES = ("/files/", "/private/files/", "/assets/")


def site_file_path(src: str) -> str:
    """The site-relative path an ``<img src>`` points at, or ``""``.

    Handles the three shapes that reach us: a relative path straight from the
    editor, an absolute URL (Frappe rewrites relative URLs to absolute when a
    reply is quoted back into a later one), and either of those with a ``?fid=``
    query on the end.

    Returns ``""`` for anything that isn't a file on this site — external URLs,
    ``data:`` URIs, ``cid:`` references that are already inline — because those
    must keep the ``src`` they came with.
    """
    if not src:
        return ""

    path = src.split("?", 1)[0].strip()
    if path.startswith(("http://", "https://")):
        # Drop scheme + host, keep the rest. A bare "https://host" has no path.
        rest = path.split("/", 3)
        path = "/" + rest[3] if len(rest) > 3 else ""

    return path if path.startswith(SITE_FILE_PREFIXES) else ""


def embed_site_images(content: str) -> str:
    """Rewrite every site-hosted ``<img>`` so the framework will inline it.

    ``src`` is replaced by ``embed`` rather than supplemented with it — see the
    module docstring for the duplicate-attribute bug that made the distinction
    load-bearing. Everything else on the tag survives: ``width``, ``height``,
    ``alt`` and ``style`` are what keep a screenshot from blowing the layout out
    in Outlook, which ignores ``max-width`` on images.
    """
    if not content:
        return ""

    soup = BeautifulSoup(content, "html.parser")

    # Comments (Outlook's MSO conditionals, which ride along in every quoted
    # reply) get mangled by the markdown conversion in sendmail and surface as
    # visible text in the delivered mail.
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()

    for tag in soup.find_all("img"):
        path = site_file_path(tag.get("src") or "")
        if not path:
            continue
        tag["embed"] = path
        del tag["src"]
        # A srcset would win over the cid: src the framework is about to write,
        # putting us straight back where we started.
        if tag.has_attr("srcset"):
            del tag["srcset"]

    # Preserved from the code this replaced: <video> keeps both attributes.
    for tag in soup.find_all("video"):
        if tag.get("src"):
            tag["embed"] = tag.get("src")

    return str(soup)


def inlined_file_urls(content: str) -> set[str]:
    """The site files this HTML will carry inline, as their ``file_url``s.

    For callers that also build an attachment list off the same document: a file
    the body embeds is already travelling with the message, and attaching it a
    second time shows the requester one picture in the text and an identical
    download beside it.

    Reads ``src`` and ``embed`` both, so it gives the same answer before and
    after :func:`embed_site_images`.
    """
    if not content:
        return set()

    soup = BeautifulSoup(content, "html.parser")
    urls = set()
    for tag in soup.find_all("img"):
        path = site_file_path(tag.get("embed") or tag.get("src") or "")
        if path:
            urls.add(path)
    return urls
