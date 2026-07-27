"""Damage tests for the book-surface metadata contract (#158).

Every check here is proven the house way: a known-bad fixture the verifier
must reject. The acceptance criteria name six damages the metadata verifier
must catch -- a stale title, a wrong slug/site-url, a missing cover, a
foreign edition, private-data contamination, and an unresolvable
local/sitemap URL -- and each has a test below that builds the broken page
and asserts the verifier turns red on it.
"""

from __future__ import annotations

import json

from press import verify_pages

TITLE = "A Book"
SITE = "https://me.test/b"
BASE = "https://me.test/b/"
DOWNLOADS = ["b.pdf", "b.epub"]


def _jsonld_script(node) -> str:
    return '<script type="application/ld+json">\n' + json.dumps(node, indent=2) + "\n</script>"


def _book_node(
    *, name=TITLE, url=BASE, image=BASE + "cover.jpg", work_url=BASE + "downloads/b.pdf"
):
    node = {"@context": "https://schema.org", "@type": "Book", "name": name, "url": url}
    if image:
        node["image"] = image
    if work_url:
        node["workExample"] = [
            {"@type": "Book", "bookFormat": "https://schema.org/EBook", "url": work_url}
        ]
    return node


def _head(*, canonical=BASE, og_image=BASE + "cover.jpg", node=None, extra=""):
    node = _book_node() if node is None else node
    tags = []
    if canonical:
        tags.append(f'<link rel="canonical" href="{canonical}">')
    tags.append(f'<meta property="og:title" content="{TITLE}">')
    tags.append('<meta name="twitter:card" content="summary_large_image">')
    if og_image:
        tags.append(f'<meta property="og:image" content="{og_image}">')
    tags.append(extra)
    tags.append(_jsonld_script(node))
    return "\n".join(t for t in tags if t)


def _site(tmp_path, *, index_head=None, site_url=SITE, with_cover=True, with_downloads=True):
    """A minimal but valid dist/pages, ready for one field to be damaged."""
    pages = tmp_path / "pages"
    pages.mkdir()
    head = _head() if index_head is None else index_head
    (pages / "index.html").write_text(
        f"<html><head>{head}</head><body>{TITLE}</body></html>", encoding="utf-8"
    )
    if with_cover:
        (pages / "cover.jpg").write_bytes(b"jpegbytes")
    if with_downloads:
        (pages / "downloads").mkdir()
        for name in DOWNLOADS:
            (pages / "downloads" / name).write_bytes(b"x")
    return pages


def _sitemap(pages, locs):
    body = "\n".join(f"  <url><loc>{loc}</loc></url>" for loc in locs)
    (pages / "sitemap.xml").write_text(
        f'<?xml version="1.0"?>\n<urlset>\n{body}\n</urlset>\n', encoding="utf-8"
    )


# --- The valid baseline: nothing is rejected. --------------------------------


def test_a_correct_site_is_accepted(tmp_path):
    pages = _site(tmp_path)
    assert verify_pages.check_metadata(pages, TITLE, SITE, DOWNLOADS) == []


# --- The six named damages, each rejected. -----------------------------------


def test_catches_a_stale_title(tmp_path):
    pages = _site(tmp_path, index_head=_head(node=_book_node(name="Old Title")))
    fails = verify_pages.check_metadata(pages, TITLE, SITE, DOWNLOADS)
    assert any("stale" in f or "Old Title" in f for f in fails)


def test_catches_a_wrong_site_url(tmp_path):
    # Canonical points at a different host than the configured site-url.
    head = _head(
        canonical="https://elsewhere.test/b/",
        node=_book_node(url="https://elsewhere.test/b/", image=None, work_url=None),
    )
    pages = _site(tmp_path, index_head=head)
    fails = verify_pages.check_metadata(pages, TITLE, SITE, DOWNLOADS)
    assert any("not under the site-url" in f for f in fails)


def test_catches_a_missing_cover(tmp_path):
    # The page claims an og:image but no cover file was shipped.
    pages = _site(
        tmp_path, with_cover=False, index_head=_head(node=_book_node(image=None, work_url=None))
    )
    fails = verify_pages.check_metadata(pages, TITLE, SITE, DOWNLOADS)
    assert any("missing cover" in f for f in fails)


def test_catches_a_foreign_edition(tmp_path):
    # JSON-LD names a download this book does not offer.
    head = _head(node=_book_node(work_url=BASE + "downloads/some-other-book.pdf"))
    pages = _site(tmp_path, index_head=head)
    fails = verify_pages.check_metadata(pages, TITLE, SITE, DOWNLOADS)
    assert any("foreign edition" in f for f in fails)


def test_catches_private_data_contamination(tmp_path):
    # A local build path leaks into the metadata head.
    head = _head(
        extra='<meta property="og:image:alt" content="/Users/someone/dist/pages/cover.jpg">'
    )
    pages = _site(tmp_path, index_head=head)
    fails = verify_pages.check_metadata(pages, TITLE, SITE, DOWNLOADS)
    assert any("private build data" in f for f in fails)


def test_catches_a_credential_marker(tmp_path):
    head = _head(extra='<meta property="og:url" content="https://me.test/b/?api_key=secret123">')
    pages = _site(tmp_path, index_head=head)
    fails = verify_pages.check_metadata(pages, TITLE, SITE, DOWNLOADS)
    assert any("private build data or a secret" in f for f in fails)


def test_catches_a_real_credential_in_a_url(tmp_path):
    # A real credential-shaped value in a URL field is still rejected: the
    # shape-based marker did not weaken the protection.
    head = _head(
        extra='<meta property="og:url" content="https://me.test/b/?apikey=sk_live_51H8xYzAbCdEf">'
    )
    pages = _site(tmp_path, index_head=head)
    fails = verify_pages.check_metadata(pages, TITLE, SITE, DOWNLOADS)
    assert any("private build data or a secret" in f for f in fails)


# --- The false positive the shape-based marker fixes. ------------------------


def test_a_book_titled_secrets_with_secret_prose_is_accepted(tmp_path):
    # The exact false-positive (#158): a book whose own title and description
    # legitimately carry 'secret'/'password' is not a leak. Only credential
    # SHAPE -- a key prefix, a bearer token, a query param, a key=value pair --
    # is. The bare English words in the title-and-prose the head carries pass.
    title = "Secrets of the Trade"
    desc = "A tale in which the secretary kept the password to herself."
    node = {
        "@context": "https://schema.org",
        "@type": "Book",
        "name": title,
        "url": BASE,
        "description": desc,
    }
    head = "\n".join(
        [
            f'<link rel="canonical" href="{BASE}">',
            f'<meta property="og:title" content="{title}">',
            f'<meta property="og:description" content="{desc}">',
            '<meta name="twitter:card" content="summary_large_image">',
            _jsonld_script(node),
        ]
    )
    pages = _site(tmp_path, index_head=head)
    assert verify_pages.check_metadata(pages, title, SITE, DOWNLOADS) == []


def test_catches_an_unresolvable_sitemap_url(tmp_path):
    pages = _site(tmp_path)
    _sitemap(pages, [BASE, BASE + "read/ghost.html"])
    fails = verify_pages.check_book_sitemap(pages, SITE)
    assert any("does not resolve" in f for f in fails)


def test_catches_a_canonical_absent_from_the_sitemap(tmp_path):
    pages = _site(tmp_path)
    _sitemap(pages, [BASE + "somewhere-else.html"])  # index canonical (BASE) is missing
    # Give the loc a real target so only the coverage failure fires.
    (pages / "somewhere-else.html").write_text("x", encoding="utf-8")
    fails = verify_pages.check_book_sitemap(pages, SITE)
    assert any("absent from the sitemap" in f for f in fails)


def test_a_sitemap_without_a_site_url_is_rejected(tmp_path):
    pages = _site(tmp_path, site_url="")
    _sitemap(pages, [BASE])
    fails = verify_pages.check_book_sitemap(pages, "")
    assert any("no site-url" in f for f in fails)


def test_offline_build_carries_no_canonical_and_no_sitemap(tmp_path):
    # No site-url: no canonical anywhere, and no sitemap is required or allowed.
    head = _head(
        canonical="",
        og_image="",
        node={"@context": "https://schema.org", "@type": "Book", "name": TITLE},
    )
    pages = _site(tmp_path, site_url="", with_cover=False, index_head=head)
    assert verify_pages.check_metadata(pages, TITLE, "", DOWNLOADS) == []
    assert verify_pages.check_book_sitemap(pages, "") == []
