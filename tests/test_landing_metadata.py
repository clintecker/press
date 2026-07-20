"""The book landing page declares structured metadata generated from the
book's own config, and invents nothing (#158): a canonical URL and social
image appear only with a site-url (and a cover), so an offline build never
claims a false canonical.
"""

from __future__ import annotations

import json
import re
from types import SimpleNamespace

from press import build


def _book(**over):
    base = dict(title="A Book", authors=("A. Author", "B. Author"),
                publisher="Example Press", description="One honest sentence.",
                year="2026", site_url="")
    base.update(over)
    return SimpleNamespace(**base)


def _jsonld(head: str) -> dict:
    m = re.search(r'<script type="application/ld\+json">\n(.*?)\n</script>', head, re.S)
    assert m, "no JSON-LD block"
    return json.loads(m.group(1))


def test_without_a_site_url_no_canonical_or_url_is_claimed():
    head = build.landing_head_metadata(_book(), has_cover=True, format_names=["b.pdf"])
    assert "rel=\"canonical\"" not in head
    assert "og:url" not in head
    node = _jsonld(head)
    assert node["@type"] == "Book" and node["name"] == "A Book"
    assert "url" not in node and "image" not in node and "workExample" not in node
    # Facts the book does carry are present.
    assert [a["name"] for a in node["author"]] == ["A. Author", "B. Author"]
    assert node["publisher"]["name"] == "Example Press"


def test_with_a_site_url_canonical_url_image_and_formats_appear():
    book = _book(site_url="https://me.test/book")
    head = build.landing_head_metadata(
        book, has_cover=True, format_names=["book.pdf", "book.epub", "book.txt"])
    assert 'rel="canonical" href="https://me.test/book/"' in head
    node = _jsonld(head)
    assert node["url"] == "https://me.test/book/"
    assert node["image"] == "https://me.test/book/cover.jpg"
    encs = {e["encodingFormat"] for e in node["workExample"]}
    assert encs == {"application/pdf", "application/epub+zip"}  # txt is not a book format


def test_absent_facts_are_omitted_not_invented():
    book = _book(site_url="https://me.test/book", description="", authors=(),
                 publisher="", year="")
    head = build.landing_head_metadata(book, has_cover=False, format_names=["b.pdf"])
    node = _jsonld(head)
    assert "description" not in node and "author" not in node
    assert "publisher" not in node and "datePublished" not in node
    assert "image" not in node  # no cover -> no image even with a site-url
    assert "og:image" not in head


def _pages_with(tmp_path, jsonld_name="A Book", canonical=None):
    """A minimal dist/pages/index.html carrying a JSON-LD Book node."""
    import json as _json
    pages = tmp_path / "pages"
    pages.mkdir()
    node = {"@context": "https://schema.org", "@type": "Book", "name": jsonld_name}
    if canonical:
        node["url"] = canonical
    head = ""
    if canonical:
        head = f'<link rel="canonical" href="{canonical}">'
    (pages / "index.html").write_text(
        "<html><head>" + head
        + '<script type="application/ld+json">\n'
        + _json.dumps(node, indent=2) + "\n</script></head><body>x</body></html>",
        encoding="utf-8")
    return pages


def test_verifier_accepts_matching_metadata(tmp_path):
    from press import verify_pages
    pages = _pages_with(tmp_path, "A Book", canonical="https://me.test/b/")
    assert verify_pages.check_landing_metadata(pages, "A Book", "https://me.test/b") == []


def test_verifier_catches_a_stale_title(tmp_path):
    from press import verify_pages
    pages = _pages_with(tmp_path, "Old Title")
    fails = verify_pages.check_landing_metadata(pages, "A Book", "")
    assert any("Old Title" in f for f in fails)


def test_verifier_catches_a_false_canonical(tmp_path):
    from press import verify_pages
    pages = _pages_with(tmp_path, "A Book", canonical="https://me.test/b/")
    fails = verify_pages.check_landing_metadata(pages, "A Book", "")  # no site-url
    assert any("no site-url" in f for f in fails)


def test_verifier_catches_a_missing_canonical(tmp_path):
    from press import verify_pages
    pages = _pages_with(tmp_path, "A Book")  # no canonical
    fails = verify_pages.check_landing_metadata(pages, "A Book", "https://me.test/b")
    assert any("no canonical" in f for f in fails)


def test_verifier_refuses_a_page_without_jsonld(tmp_path):
    from press import verify_pages
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "index.html").write_text("<html><body>no metadata</body></html>", encoding="utf-8")
    assert verify_pages.check_landing_metadata(pages, "A Book", "") == [
        "landing page carries no JSON-LD structured metadata"]
