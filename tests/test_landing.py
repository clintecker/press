"""The Pages landing assembly (press.landing): the downloads table lists every
published edition by its exact registry name, the subtitle's OR clauses stack,
optional blocks (cover, imprint device, source paragraph, commerce) render only
when their asset or config exists, generated policy pages appear only for an
enabled valid commerce block, and a missing download fails the assembly loudly.

Every scenario is a factory book with fabricated dist/ artifacts: pages_build
only copies what a build produced, so no pandoc or TeX run is needed here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.factories import BookFactory, full, minimal
from press import landing, registry

pytestmark = pytest.mark.layer("integration")

COMMERCE = {
    "print-ordering": {
        "enabled": True,
        "edition": "paperback",
        "storefront-url": "https://store.example.test/book",
        "seller-of-record": "Lulu",
        "support-url": "https://ex.test/support",
        "privacy-url": "",
        "refund-url": "",
    }
}


def _fake_dist(root: Path, names: list[str]) -> None:
    """Stand in for a finished build: a reader site and one file per download."""

    site = root / "dist" / "site"
    site.mkdir(parents=True)
    (site / "index.html").write_text("<html>reader</html>", encoding="utf-8")
    (site / "01-chapter.html").write_text("<html>chapter</html>", encoding="utf-8")
    for name in names:
        (root / "dist" / name).write_bytes(f"artifact {name}".encode())


def _cover(path: Path, size=(40, 60)) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, "white").save(path, "JPEG")


def _assemble(handle) -> Path:
    _fake_dist(handle.root, landing.download_names())
    landing.pages_build("dist/pages")
    return handle.root / "dist" / "pages"


def _rows(index: str) -> list[tuple[str, str]]:
    """(href, label) for every row of the downloads table."""

    return re.findall(r'<td[^>]*><a href="([^"]+)">([^<]+)</a></td>', index)


# ---- the editions table ----


@pytest.mark.invariant("INV-landing-editions-exact")
@pytest.mark.proof("positive")
def test_every_registry_download_is_listed_by_its_exact_name(tmp_path):
    handle = full().build(tmp_path)  # authorities: the sources companion publishes
    with handle.use():
        names = landing.download_names()
        assert names == registry.download_names()
        assert f"{handle.slug}-sources.md" in names
        pages = _assemble(handle)
        index = (pages / "index.html").read_text(encoding="utf-8")

    rows = _rows(index)
    assert rows[0] == ("read/index.html", "Chapter edition")
    listed = {href.removeprefix("downloads/"): label for href, label in rows[1:]}
    assert sorted(listed) == sorted(names)
    labels = dict(
        (f"{handle.slug}{suffix}", label) for suffix, label, _ in landing.EDITION_DESCRIPTIONS
    )
    assert listed == {name: labels[name] for name in names}
    # Each label appears once: the sources companion is not a second manuscript.
    assert list(listed.values()).count("Manuscript edition") == 1
    assert listed[f"{handle.slug}-sources.md"] == "Table of authorities"
    # Every listed download was copied into the site byte for byte.
    for name in names:
        assert (pages / "downloads" / name).read_bytes() == f"artifact {name}".encode()
    assert (pages / "read" / "index.html").is_file()


@pytest.mark.invariant("INV-landing-editions-exact")
@pytest.mark.proof("negative")
def test_no_authorities_means_no_sources_row(tmp_path):
    handle = minimal().build(tmp_path)
    with handle.use():
        names = landing.download_names()
        assert not any(n.endswith("-sources.md") for n in names)
        index = (_assemble(handle) / "index.html").read_text(encoding="utf-8")
    assert "Table of authorities" not in index
    assert len(_rows(index)) == len(names) + 1  # plus the chapter edition


def test_unlisted_names_get_no_row_and_rows_escape(monkeypatch):
    monkeypatch.setattr(
        landing, "download_names", lambda: ["bk.pdf", "bk-interior.pdf", "other.epub"]
    )
    rows = landing._pages_download_rows("bk", "5 by 8 inches")
    assert len(rows) == 2
    assert 'href="downloads/bk.pdf">Print edition' in rows[1]
    assert "5 by 8 inches, typeset by LuaLaTeX" in rows[1]


def test_rows_describe_each_edition_with_the_default_trim(tmp_path):
    handle = minimal().build(tmp_path)
    with handle.use():
        names = landing.download_names()
        index = (_assemble(handle) / "index.html").read_text(encoding="utf-8")
    assert "6 by 9 inches, typeset by LuaLaTeX" in index
    for suffix, _, desc in landing.EDITION_DESCRIPTIONS[1:]:
        assert (desc in index) == (f"{handle.slug}{suffix}" in names)


@pytest.mark.proof("negative")
def test_a_missing_download_fails_the_assembly_loudly(tmp_path):
    handle = minimal().build(tmp_path)
    with handle.use():
        names = landing.download_names()
        _fake_dist(handle.root, names)
        (handle.root / "dist" / names[1]).unlink()
        with pytest.raises(SystemExit, match=re.escape(f"pages: {names[1]} missing from dist")):
            landing.pages_build("dist/pages")


def test_a_rebuild_replaces_the_previous_pages_tree(tmp_path):
    handle = minimal().build(tmp_path)
    with handle.use():
        pages = _assemble(handle)
        (pages / "stale.html").write_text("old", encoding="utf-8")
        landing.pages_build("dist/pages")
    assert not (pages / "stale.html").exists()
    assert (pages / "index.html").is_file()


# ---- the subtitle stack ----


def test_subtitle_or_clauses_stack_with_the_first_strong():
    html = landing.subtitle_stack_html("Being a Plain Account; or, The Press Revealed")
    lines = html.splitlines()
    assert lines == [
        '      <strong class="sc">Being a Plain Account</strong><br>',
        '      <span class="or sc">or,</span><br>',
        '      <span class="sc">The Press Revealed</span>',
    ]


def test_subtitle_leading_or_and_escaping():
    html = landing.subtitle_stack_html("or, Types & <Rules>")
    assert html.splitlines() == [
        '      <span class="or sc">or,</span><br>',
        '      <strong class="sc">Types &amp; &lt;Rules&gt;</strong>',
    ]


def test_an_empty_subtitle_renders_nothing():
    assert landing.subtitle_stack_html("") == ""
    assert landing.subtitle_stack_html(" ; . ") == ""


def test_the_landing_carries_the_subtitle_stack(tmp_path):
    book = BookFactory(slug="sub-book").with_metadata(
        subtitle="One Thing; or, Another; or, A Third"
    )
    handle = book.build(tmp_path)
    with handle.use():
        index = (_assemble(handle) / "index.html").read_text(encoding="utf-8")
    assert index.count('<span class="or sc">or,</span>') == 2
    assert '<strong class="sc">One Thing</strong>' in index
    assert '<span class="sc">A Third</span>' in index


# ---- optional blocks degrade honestly ----


@pytest.mark.proof("negative")
def test_a_bare_book_renders_no_cover_logo_repo_commerce_or_sitemap(tmp_path):
    handle = minimal().build(tmp_path)
    with handle.use():
        pages = _assemble(handle)
    index = (pages / "index.html").read_text(encoding="utf-8")
    for absent in (
        '<div class="cover-plate"',
        '<img class="press-logo"',
        "public build system",
        '<aside class="print-order"',
    ):
        assert absent not in index
    assert 'rel="canonical"' not in index
    for absent in ("cover.jpg", "press-logo.png", "woodcuts", "sitemap.xml", "robots.txt"):
        assert not (pages / absent).exists()
    for policy in ("support.html", "privacy.html", "refunds.html"):
        assert not (pages / policy).exists()
    assert "{{" not in index  # every placeholder resolved


def test_cover_logo_repo_and_site_url_render_when_supplied(tmp_path):
    book = BookFactory(slug="dressed-book", title="Types & Rules").with_metadata(
        **{
            "repository": "https://github.com/example/dressed-book",
            "site-url": "https://example.test/dressed",
            "publisher": "Example & Sons",
        }
    )
    handle = book.build(tmp_path)
    _cover(handle.root / "assets" / "cover.jpg", (40, 60))
    _cover(handle.root / "assets" / "press-logo.png")
    (handle.root / "assets" / "woodcuts").mkdir()
    (handle.root / "assets" / "woodcuts" / "plate.png").write_bytes(b"png")
    with handle.use():
        pages = _assemble(handle)
    index = (pages / "index.html").read_text(encoding="utf-8")
    assert '<img src="cover.jpg" alt="Cover of Types &amp; Rules">' in index
    assert 'alt="Imprint device of Example &amp; Sons"' in index
    repo = "https://github.com/example/dressed-book"
    assert f'<a href="{repo}">a public build system</a>' in index
    assert f"{repo}/blob/main/CHANGELOG.md" in index and f"{repo}/releases" in index
    assert 'rel="canonical" href="https://example.test/dressed/"' in index
    assert "https://example.test/dressed/cover.jpg" in index
    assert 'content="40"' in index and 'content="60"' in index  # verified cover dims
    assert (pages / "cover.jpg").is_file() and (pages / "press-logo.png").is_file()
    assert (pages / "woodcuts" / "plate.png").read_bytes() == b"png"
    sitemap = (pages / "sitemap.xml").read_text(encoding="utf-8")
    assert "<loc>https://example.test/dressed/</loc>" in sitemap
    assert "https://example.test/dressed/read/01-chapter.html" in sitemap


def test_extra_css_is_appended_into_the_landing_head(tmp_path):
    handle = minimal().with_extra_css("body { background: rebeccapurple; }").build(tmp_path)
    with handle.use():
        index = (_assemble(handle) / "index.html").read_text(encoding="utf-8")
    head, _, _ = index.partition("</head>")
    assert "/* assets/web/extra.css */\nbody { background: rebeccapurple; }" in head
    assert index.count("</head>") == 1


# ---- commerce: the CTA and the generated policy pages ----


def test_enabled_commerce_renders_the_cta_and_generates_missing_policies(tmp_path):
    handle = (
        BookFactory(slug="shop-book")
        .with_metadata(commerce=COMMERCE, publisher="Shop Press")
        .build(tmp_path)
    )
    with handle.use():
        pages = _assemble(handle)
    index = (pages / "index.html").read_text(encoding="utf-8")
    assert '<aside class="print-order"' in index
    assert 'href="https://store.example.test/book"' in index
    assert "sold and fulfilled by Lulu" in index
    # The publisher hosts support; press generates privacy and refunds.
    assert not (pages / "support.html").exists()
    for filename, heading in (
        ("privacy.html", "Privacy for print orders"),
        ("refunds.html", "Returns and refunds for print orders"),
    ):
        page = (pages / filename).read_text(encoding="utf-8")
        assert heading in page
        assert "A Fixture Book" in page
        assert "{{" not in page


@pytest.mark.proof("negative")
@pytest.mark.parametrize(
    "override",
    [{"enabled": False}, {"storefront-url": "http://insecure.test/book"}],
    ids=["disabled", "invalid"],
)
def test_disabled_or_invalid_commerce_renders_no_cta_and_no_policies(tmp_path, override):
    block = {"print-ordering": {**COMMERCE["print-ordering"], **override}}
    handle = BookFactory(slug="quiet-shop").with_metadata(commerce=block).build(tmp_path)
    with handle.use():
        pages = _assemble(handle)
    assert '<aside class="print-order"' not in (pages / "index.html").read_text(encoding="utf-8")
    for policy in ("support.html", "privacy.html", "refunds.html"):
        assert not (pages / policy).exists()
