"""Toolchain-stable structural features of the non-PDF editions.

The visual harness snapshots the house PDF's geometry; this snapshots the
*structure* of the editions pandoc writes -- the EPUB's spine and navigation,
the reader site's pages and links, the DOCX's declared paragraph styles. Raw
bytes shift with every pandoc patch, but the structural shape of a fixed book
does not: two chapters yield two chapter documents, a title page and a nav
sit in the spine, the reader site is an index plus one page per chapter, and
the DOCX declares the house paragraph styles the book leans on.

The comparison is scoped so a benign pandoc upgrade does not trip it while a
real regression does. Book-determined counts (chapter documents, reader
pages) are matched exactly. The version-sensitive shapes are matched in the
regression direction only: the spine and nav must carry *at least* the
baseline's entries, and the DOCX must still declare *every* baseline style --
so a lost chapter, a dropped nav entry, or a removed style is drift, while a
pandoc that adds an item or a new token style is not.

Baselines are reviewed data committed under tests/visual/, updated only with
a recorded reason, exactly like the PDF geometry baseline.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path


def extract_epub(path: Path) -> dict:
    """Spine length, chapter-document count, and navigation entry count of a
    built EPUB, read from the OPF and the nav document."""

    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        opf = "\n".join(
            archive.read(name).decode("utf-8", errors="ignore")
            for name in names
            if name.endswith(".opf")
        )
        spine_itemrefs = len(re.findall(r"<itemref\b", opf))
        content_docs = [n for n in names if n.endswith((".xhtml", ".html"))]
        chapter_docs = [
            n
            for n in content_docs
            if re.search(r"/ch\d+\.xhtml$", n) or re.search(r"/ch\d+\.html$", n)
        ]
        nav_docs = [n for n in content_docs if "nav" in n.rsplit("/", 1)[-1].lower()]
        nav_entries = 0
        if nav_docs:
            nav = archive.read(nav_docs[0]).decode("utf-8", errors="ignore")
            nav_entries = len(re.findall(r"<a\b", nav))
    return {
        "spine_itemrefs": spine_itemrefs,
        "chapter_docs": len(chapter_docs),
        "nav_entries": nav_entries,
    }


def extract_site(path: Path) -> dict:
    """Page count and index navigation link count of a built reader site."""

    pages = sorted(p.name for p in path.glob("*.html"))
    index = path / "index.html"
    nav_links = 0
    if index.is_file():
        nav_links = len(
            re.findall(
                r'<a\b[^>]*href="[^"]*\.html"', index.read_text(encoding="utf-8", errors="ignore")
            )
        )
    return {
        "page_count": len(pages),
        "index_nav_links": nav_links,
    }


def extract_docx(path: Path) -> dict:
    """The declared structural style ids of a built DOCX.

    Two families of reference styles churn across pandoc versions and are
    dropped: the syntax-highlighting token styles for code blocks (every id
    ending in ``Tok``) and the linked *character* styles pandoc's reference.docx
    carries for its paragraph styles (every id ending in ``Char`` -- HeadingNChar,
    TitleChar, SubtitleChar). A prose book leans on neither, and which of them a
    given pandoc declares varies host to container. What remains -- Title,
    Author, Heading1..9, BodyText, FirstParagraph, Caption, and the rest -- is
    the house document structure, stable across pandoc builds.
    """

    with zipfile.ZipFile(path) as archive:
        styles_xml = archive.read("word/styles.xml").decode("utf-8", errors="ignore")
    styles = sorted(
        style
        for style in set(re.findall(r'<w:style\b[^>]*w:styleId="([^"]+)"', styles_xml))
        if not style.endswith(("Tok", "Char"))
    )
    return {"styles": styles}


def extract_editions(dist: Path, slug: str) -> dict:
    """Every non-PDF edition's structural features, keyed by edition."""

    return {
        "epub": extract_epub(dist / f"{slug}.epub"),
        "site": extract_site(dist / "site"),
        "docx": extract_docx(dist / f"{slug}.docx"),
    }


# ---- baseline comparison ----


def compare_structure(baseline: dict, actual: dict) -> list[str]:
    """Structural drift beyond the scoping rules above, as a list of human
    diffs. Empty means the built editions match the reviewed baseline."""

    drifts: list[str] = []
    epub_b, epub_a = baseline["epub"], actual["epub"]
    # Chapter documents are book-determined: exact.
    if epub_b["chapter_docs"] != epub_a["chapter_docs"]:
        drifts.append(f"epub.chapter_docs {epub_b['chapter_docs']} -> {epub_a['chapter_docs']}")
    # Spine and nav must not shrink below the reviewed shape.
    if epub_a["spine_itemrefs"] < epub_b["spine_itemrefs"]:
        drifts.append(
            f"epub.spine_itemrefs dropped {epub_b['spine_itemrefs']} -> {epub_a['spine_itemrefs']}"
        )
    if epub_a["nav_entries"] < epub_b["nav_entries"]:
        drifts.append(
            f"epub.nav_entries dropped {epub_b['nav_entries']} -> {epub_a['nav_entries']}"
        )

    site_b, site_a = baseline["site"], actual["site"]
    if site_b["page_count"] != site_a["page_count"]:
        drifts.append(f"site.page_count {site_b['page_count']} -> {site_a['page_count']}")
    if site_a["index_nav_links"] < site_b["index_nav_links"]:
        drifts.append(
            f"site.index_nav_links dropped {site_b['index_nav_links']} -> {site_a['index_nav_links']}"
        )

    missing_styles = sorted(set(baseline["docx"]["styles"]) - set(actual["docx"]["styles"]))
    if missing_styles:
        drifts.append(f"docx styles removed: {', '.join(missing_styles)}")
    return drifts
