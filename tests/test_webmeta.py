"""The shared web-metadata emitter (#158): the one place the no-public-base
law lives. These prove that with a base every URL-shaped tag appears, and
without one none does -- for the head tags and for the JSON-LD node alike.
"""

from __future__ import annotations

import json
import re

from press import webmeta


def _jsonld(head: str):
    m = re.search(r'<script type="application/ld\+json">\n(.*?)\n</script>', head, re.S)
    assert m, "no JSON-LD block"
    return json.loads(m.group(1))


def test_with_a_base_every_url_shaped_tag_is_emitted():
    node = {"@context": "https://schema.org", "@type": "Book", "name": "A Book",
            "url": "https://me.test/", "image": "https://me.test/cover.jpg"}
    head = webmeta.head_fragment(
        base="https://me.test/", title="A Book", description="One line.",
        og_type="book", site_name="Press", canonical="https://me.test/",
        image="https://me.test/cover.jpg", image_width=800, image_height=1200,
        image_alt="Cover of A Book",
        extra_properties=[("book:author", "A. Author")], jsonld=node)
    assert 'rel="canonical" href="https://me.test/"' in head
    assert '<meta property="og:url" content="https://me.test/">' in head
    assert '<meta property="og:image" content="https://me.test/cover.jpg">' in head
    assert '<meta property="og:image:width" content="800">' in head
    assert '<meta property="og:image:height" content="1200">' in head
    assert '<meta property="og:image:alt" content="Cover of A Book">' in head
    assert '<meta name="twitter:image" content="https://me.test/cover.jpg">' in head
    assert '<meta property="book:author" content="A. Author">' in head
    assert _jsonld(head)["url"] == "https://me.test/"


def test_without_a_base_nothing_url_shaped_survives():
    """The one law, enforced in one place: an empty base drops the canonical,
    og:url, and og:image even though the caller passed them, and strips the
    JSON-LD of url/image/@id/item."""
    node = {"@context": "https://schema.org", "@type": "Article", "name": "Ch. 1",
            "url": "https://me.test/1.html", "image": "https://me.test/cover.jpg",
            "isPartOf": {"@type": "Book", "name": "A Book", "@id": "https://me.test/"}}
    head = webmeta.head_fragment(
        base="", title="Ch. 1", description="One line.", og_type="article",
        canonical="https://me.test/1.html", image="https://me.test/cover.jpg",
        image_width=800, image_height=1200, jsonld=node)
    for forbidden in ("canonical", "og:url", "og:image", "https://me.test"):
        assert forbidden not in head, forbidden
    # Facts the page honestly has survive.
    assert '<meta property="og:title" content="Ch. 1">' in head
    assert '<meta property="og:description" content="One line.">' in head
    stripped = _jsonld(head)
    assert "url" not in stripped and "image" not in stripped
    assert stripped["name"] == "Ch. 1"
    assert stripped["isPartOf"] == {"@type": "Book", "name": "A Book"}


def test_description_meta_is_opt_in():
    with_meta = webmeta.head_fragment(
        base="", title="T", description="D", description_meta=True)
    without = webmeta.head_fragment(base="", title="T", description="D")
    assert '<meta name="description" content="D">' in with_meta
    assert '<meta name="description"' not in without


def test_values_are_html_escaped():
    head = webmeta.head_fragment(
        base="", title='A & "B"', description="x <y>")
    assert 'content="A &amp; &quot;B&quot;"' in head
    assert 'content="x &lt;y&gt;"' in head
