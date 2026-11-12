"""Cross-page anchors in the reader site resolve, or the site is refused.

pandoc's chunked writer leaves a manuscript's own ``#id`` link as written
on every page, so a ``@fig:`` reference to a figure in another chapter was
a dead link in the reader (#270). ``reader_links.resolve_anchors`` points
each such link at the page that defines the id after the chunked write;
``verify_formats.require_anchors_resolve`` refuses any anchor left
dangling. The unit tests drive both over a synthetic site; the integration
test builds the two-chapter book of the issue with real pandoc.
"""

from __future__ import annotations

import base64

import pytest

from press import reader_links, verify_formats
from tests import factories
from tests.integration._harness import missing_tools, skip_reason

PANDOC = ("pandoc",)
requires_pandoc = pytest.mark.skipif(bool(missing_tools(PANDOC)), reason=skip_reason(PANDOC))

ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def _page(body: str) -> str:
    return f'<html><body><a class="skip" href="#content">skip</a><main id="content">{body}</main></body></html>'


def _site(tmp_path, two_body: str, one_body: str = '<figure id="fig:press"><p>plate</p></figure>'):
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text(_page('<a href="1-one.html#one">One</a>'), encoding="utf-8")
    (site / "1-one.html").write_text(_page(f'<h1 id="one">One</h1>{one_body}'), encoding="utf-8")
    (site / "2-two.html").write_text(_page(f'<h1 id="two">Two</h1>{two_body}'), encoding="utf-8")
    return site


@pytest.mark.invariant("INV-format-anchors-resolve")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_resolve_anchors_points_a_cross_page_fragment_at_its_home_page(tmp_path):
    site = _site(tmp_path, 'As <a href="#fig:press">Figure 1.1</a> shows. <a href="#two">top</a>')
    assert reader_links.resolve_anchors(site) == 1
    two = (site / "2-two.html").read_text(encoding="utf-8")
    assert 'href="1-one.html#fig:press"' in two
    assert 'href="#fig:press"' not in two
    # Same-page anchors (the skip link, the chapter heading) are left as they were.
    assert 'href="#two"' in two
    assert 'href="#content"' in two
    assert reader_links.local_anchors(site / "2-two.html") == ["content", "two"]
    assert ("1-one.html", "fig:press") in reader_links.sibling_anchors(site / "2-two.html")
    assert verify_formats.require_anchors_resolve(sorted(site.glob("*.html")), "site") is None


@pytest.mark.invariant("INV-format-anchors-resolve")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_resolve_anchors_is_idempotent_and_reports_zero_when_nothing_dangles(tmp_path):
    site = _site(tmp_path, 'See <a href="#fig:press">it</a>.')
    assert reader_links.resolve_anchors(site) == 1
    before = {p.name: p.read_bytes() for p in site.glob("*.html")}
    assert reader_links.resolve_anchors(site) == 0
    assert {p.name: p.read_bytes() for p in site.glob("*.html")} == before


@pytest.mark.invariant("INV-format-anchors-resolve")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_page_ids_maps_every_page_to_the_ids_it_defines(tmp_path):
    site = _site(tmp_path, "")
    ids = {page.name: found for page, found in reader_links.page_ids(site).items()}
    assert ids["1-one.html"] == {"content", "one", "fig:press"}
    assert ids["2-two.html"] == {"content", "two"}
    assert ids["index.html"] == {"content"}


@pytest.mark.invariant("INV-format-anchors-resolve")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_require_anchors_resolve_refuses_a_dangling_anchor(tmp_path):
    site = _site(tmp_path, 'See <a href="#fig:nowhere">it</a>.')
    # The id lives on no page, so the producer honestly leaves the link alone...
    assert reader_links.resolve_anchors(site) == 0
    # ...and the verifier names the page and the anchor instead of passing it.
    with pytest.raises(SystemExit, match=r"2-two\.html carries an unresolved anchor #fig:nowhere"):
        verify_formats.require_anchors_resolve(sorted(site.glob("*.html")), "reader site")


@pytest.mark.invariant("INV-format-anchors-resolve")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_an_id_defined_on_two_pages_is_not_guessed_and_is_refused(tmp_path):
    site = _site(
        tmp_path,
        'See <a href="#fig:press">it</a>.',
        one_body='<figure id="fig:press"></figure>',
    )
    (site / "index.html").write_text(_page('<p id="fig:press">twin</p>'), encoding="utf-8")
    assert reader_links.resolve_anchors(site) == 0
    with pytest.raises(SystemExit, match="unresolved anchor #fig:press"):
        verify_formats.require_anchors_resolve(sorted(site.glob("*.html")), "reader site")


@pytest.mark.invariant("INV-format-anchors-resolve")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_sibling_link_to_a_missing_id_is_refused(tmp_path):
    site = _site(tmp_path, '<a href="1-one.html#fig:gone">gone</a>')
    with pytest.raises(SystemExit, match=r"1-one\.html#fig:gone; no element on 1-one\.html"):
        verify_formats.require_anchors_resolve(sorted(site.glob("*.html")), "reader site")


@pytest.mark.invariant("INV-format-anchors-resolve")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_external_and_root_links_are_not_anchors(tmp_path):
    site = _site(
        tmp_path,
        '<a href="https://example.org/#frag">out</a><a href="/abs.html#frag">abs</a>'
        '<a href="#">top</a><a href="1-one.html">plain</a>',
    )
    assert reader_links.local_anchors(site / "2-two.html") == ["content"]
    assert reader_links.sibling_anchors(site / "2-two.html") == []
    assert reader_links.resolve_anchors(site) == 0


def _two_chapter_book(root):
    handle = (
        factories.BookFactory(slug="xref-site")
        .with_sentinels("the platen does the pressing")
        .with_chapter(
            "01-one.md",
            "# One\n\nThe first chapter stands here as a plain witness sentence of its own.\n\n"
            "![The hand press at work](assets/fig/press.png){#fig:press .figure "
            'fig-alt="A hand press"}\n',
        )
        .with_chapter(
            "02-two.md",
            "# Two\n\nThe second chapter stands here as a plain witness sentence of its own.\n\n"
            "As @fig:press shows, the platen does the pressing.\n",
        )
        .build(root)
    )
    (handle.root / "assets" / "fig").mkdir(parents=True, exist_ok=True)
    (handle.root / "assets" / "fig" / "press.png").write_bytes(ONE_PIXEL_PNG)
    return handle


@requires_pandoc
@pytest.mark.invariant("INV-format-anchors-resolve")
@pytest.mark.layer("integration")
@pytest.mark.proof("positive")
def test_a_cross_chapter_figure_reference_links_to_the_figure_page(tmp_path):
    from press import booklib, registry

    handle = _two_chapter_book(tmp_path)
    with handle.use():
        registry.build("site")
        site = booklib.root() / "dist" / "site"
        two = site / "2-two.html"
        text = two.read_text(encoding="utf-8")
        assert 'href="1-one.html#fig:press"' in text, text
        assert 'href="#fig:press"' not in text
        assert "fig:press" in reader_links.anchor_ids(site / "1-one.html")
        verify_formats.verify_site(site)
