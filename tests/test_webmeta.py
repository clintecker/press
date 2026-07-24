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


# --- narrow-screen table labelling -------------------------------------------
#
# The contract: every body cell of a HEADED table carries its column's header,
# so a stacked card on a phone can show "Binding / perfect-bound" instead of an
# orphaned "perfect-bound". A table with no header row is left exactly as it
# was, because its first cell already is the label.


def _headed(rows: str, heads: str = "<th>Stage</th><th>What it does</th>") -> str:
    return f"<table><thead><tr>{heads}</tr></thead><tbody>{rows}</tbody></table>"


def test_each_cell_takes_its_own_column_header():
    out = webmeta.label_table_cells(
        _headed("<tr><td>Detect</td><td>turns RF into audio</td></tr>"))
    assert '<td data-label="Stage">Detect</td>' in out
    assert '<td data-label="What it does">turns RF into audio</td>' in out


def test_every_row_restarts_at_the_first_column():
    out = webmeta.label_table_cells(
        _headed("<tr><td>A</td><td>a</td></tr><tr><td>B</td><td>b</td></tr>"))
    assert out.count('data-label="Stage"') == 2
    assert out.count('data-label="What it does"') == 2


def test_a_table_without_a_header_row_is_untouched():
    # The reference records and the downloads table: the first cell IS the
    # label, so stacking them would invent a header that does not exist.
    plain = "<table><tbody><tr><td>pdf</td><td>the print edition</td></tr></tbody></table>"
    assert webmeta.label_table_cells(plain) == plain


def test_markup_inside_a_header_becomes_plain_text():
    out = webmeta.label_table_cells(
        _headed("<tr><td>x</td></tr>", heads="<th><code>print.profile</code></th>"))
    assert 'data-label="print.profile"' in out


def test_a_quote_in_a_header_cannot_break_out_of_the_attribute():
    out = webmeta.label_table_cells(
        _headed("<tr><td>x</td></tr>", heads='<th>The "big" one</th>'))
    assert 'data-label="The &quot;big&quot; one"' in out
    assert '"><' not in out.split("<tbody>")[1]


def test_an_entity_in_a_header_survives_one_round_trip():
    # "Trim &amp; interior" must label as "Trim &amp; interior", not
    # "Trim & interior" (which would be invalid) nor double-escaped.
    out = webmeta.label_table_cells(
        _headed("<tr><td>x</td></tr>", heads="<th>Trim &amp; interior</th>"))
    assert 'data-label="Trim &amp; interior"' in out


def test_extra_cells_beyond_the_headers_stay_bare():
    # Mislabelling a stray cell with a neighbour's header would be worse than
    # leaving it unlabelled.
    out = webmeta.label_table_cells(
        _headed("<tr><td>A</td><td>b</td><td>surplus</td></tr>"))
    assert "<td>surplus</td>" in out


def test_cells_outside_a_table_are_not_touched():
    prose = "<p>A paragraph mentioning &lt;td&gt; in text.</p>"
    assert webmeta.label_table_cells(prose) == prose


def test_two_tables_on_one_page_get_their_own_headers():
    first = _headed("<tr><td>A</td><td>a</td></tr>")
    second = _headed("<tr><td>B</td><td>b</td></tr>",
                     heads="<th>Reading</th><th>Instrument</th>")
    out = webmeta.label_table_cells(first + second)
    assert 'data-label="Stage">A' in out
    assert 'data-label="Reading">B' in out
