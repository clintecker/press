"""Structured metadata for the reader site and landing page.

Post-pandoc passes that stamp canonical/OG/JSON-LD onto every reader page,
assemble the landing page's head metadata, and emit the book sitemap. Split
out of build.py so the build module stays about assembling artifacts and this
one about the metadata layered onto them.
"""

from __future__ import annotations

import re
from pathlib import Path


def _image_dims(path: Path) -> tuple[int, int] | None:
    """Pixel dimensions of an image, or None if it cannot be read. Social
    cards must carry verified dimensions, so this reads the real file rather
    than trusting a declared size."""

    if not path.is_file():
        return None
    try:
        from PIL import Image

        with Image.open(path) as image:
            return int(image.width), int(image.height)
    except Exception:
        return None


def _first_paragraph_text(html_text: str) -> str:
    """The visible text of a reader page's first body paragraph, for a
    per-page meta description. Derived from the built page, not hand-kept, so
    it cannot drift from what the chapter actually says."""

    import html as html_mod

    body = re.search(r'<main id="content">(.*?)</main>', html_text, re.S)
    region = body.group(1) if body else html_text
    for match in re.finditer(r"<p[^>]*>(.*?)</p>", region, re.S):
        text = re.sub(r"<[^>]+>", " ", match.group(1))
        text = html_mod.unescape(" ".join(text.split()))
        if len(text) < 20:
            continue
        if len(text) > 157:
            text = text[:157].rsplit(" ", 1)[0] + "..."
        return text
    return ""


def _reader_page_title(html_text: str) -> str:
    """The chapter/page heading pandoc wrote into the reader page's <title>."""

    import html as html_mod

    match = re.search(r"<title>(.*?)</title>", html_text, re.S)
    return html_mod.unescape(match.group(1).strip()) if match else ""


def _reader_identity(book) -> dict:
    """The Book identity shared by the index node and every chapter's
    ``isPartOf``: title, language, and (when known) author and publisher."""

    identity: dict = {"@type": "Book", "name": book.title, "inLanguage": "en"}
    if book.authors:
        identity["author"] = [{"@type": "Person", "name": a} for a in book.authors]
    if book.publisher:
        identity["publisher"] = {"@type": "Organization", "name": book.publisher}
    return identity


def _reader_index_node(
    book, identity: dict, canonical: str, read_base: str, desc: str, has_cover: bool
) -> dict:
    """The index page's Book node, consistent with the landing's identity."""

    node = dict(identity)
    node["@context"] = "https://schema.org"
    if desc:
        node["description"] = desc
    if book.year:
        node["datePublished"] = book.year
    if canonical:
        node["url"] = canonical
    if canonical and has_cover:
        node["image"] = read_base + "cover.jpg"
    return node


def _reader_article_node(
    book, identity: dict, page_title: str, canonical: str, read_base: str, desc: str
):
    """A chapter's Article node (isPartOf the Book), plus a BreadcrumbList
    when there is a public base to point at."""

    article: dict = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": page_title or book.title,
        "inLanguage": "en",
        "isPartOf": identity,
    }
    if desc:
        article["description"] = desc
    if canonical:
        article["url"] = canonical
    if book.authors:
        article["author"] = [{"@type": "Person", "name": a} for a in book.authors]
    if not canonical:
        return article
    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": book.title,
                "item": read_base + "index.html",
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": page_title or book.title,
                "item": canonical,
            },
        ],
    }
    return [article, breadcrumb]


def _reader_jsonld(
    book,
    is_index: bool,
    page_title: str,
    canonical: str,
    read_base: str,
    desc: str,
    has_cover: bool,
):
    """The structured node for one reader page: a Book on the index (consistent
    with the landing's identity), an Article that isPartOf that Book on a
    chapter, plus a BreadcrumbList when there is a public base to point at."""

    identity = _reader_identity(book)
    if is_index:
        return _reader_index_node(book, identity, canonical, read_base, desc, has_cover)
    return _reader_article_node(book, identity, page_title, canonical, read_base, desc)


def inject_reader_metadata(site_dir: Path, book) -> None:
    """Post-pandoc pass: give every reader page its canonical/OG/JSON-LD.

    Pandoc's chunked writer owns each page's <head>, so identity is stamped
    here after the fact (mirroring how the docs-site builder post-processes a
    pandoc render). The reader is served under ``read/`` on the public site,
    so canonicals are absolute against ``site-url + read/`` -- and omitted
    entirely on an offline build, where the shared emitter claims no URL.
    """

    from . import webmeta

    base = (book.site_url or "").strip()
    read_base = (base.rstrip("/") + "/read/") if base else ""
    has_cover = (site_dir / "cover.jpg").is_file()

    for page in sorted(site_dir.glob("*.html")):
        text = page.read_text(encoding="utf-8")
        is_index = page.name == "index.html"
        canonical = (read_base + page.name) if read_base else ""
        if is_index:
            desc = str(book.description or "").strip()
            page_title = book.title
        else:
            desc = _first_paragraph_text(text)
            page_title = _reader_page_title(text) or book.title
        node = _reader_jsonld(book, is_index, page_title, canonical, read_base, desc, has_cover)
        fragment = webmeta.head_fragment(
            base=read_base,
            title=page_title,
            description=desc,
            og_type="book" if is_index else "article",
            site_name=book.publisher or "",
            canonical=canonical,
            image=(read_base + "cover.jpg") if (read_base and has_cover) else "",
            image_alt=f"Cover of {book.title}" if has_cover else "",
            jsonld=node,
        )
        original = text
        if fragment:
            text = text.replace("</head>", fragment + "\n</head>", 1)
        # Independent of the metadata: a table in a chapter needs its column
        # headers carried onto its cells so narrow screens can stack it into
        # readable cards. An offline book emits no metadata fragment at all,
        # and its tables must still be legible on a phone.
        text = webmeta.label_table_cells(text)
        if text != original:
            page.write_text(text, encoding="utf-8")


_SCHEMA_FORMATS = {
    ".epub": ("https://schema.org/EBook", "application/epub+zip"),
    ".pdf": ("https://schema.org/EBook", "application/pdf"),
}


def _landing_jsonld(book, base: str, desc: str, has_cover: bool, format_names: list[str]) -> dict:
    """A schema.org Book node carrying only the facts the book actually has."""

    node: dict = {
        "@context": "https://schema.org",
        "@type": "Book",
        "name": book.title,
        "inLanguage": "en",
    }
    if book.authors:
        node["author"] = [{"@type": "Person", "name": a} for a in book.authors]
    if book.publisher:
        node["publisher"] = {"@type": "Organization", "name": book.publisher}
    if desc:
        node["description"] = desc
    if book.year:
        node["datePublished"] = book.year
    if not base:
        return node
    node["url"] = base
    if has_cover:
        node["image"] = base + "cover.jpg"
    examples = [
        {
            "@type": "Book",
            "bookFormat": fmt,
            "encodingFormat": enc,
            "url": base + "downloads/" + name,
        }
        for name in format_names
        for suffix, (fmt, enc) in _SCHEMA_FORMATS.items()
        if name.endswith(suffix)
    ]
    if examples:
        node["workExample"] = examples
    return node


def landing_head_metadata(
    book, has_cover: bool, format_names: list[str], cover_dims: tuple[int, int] | None = None
) -> str:
    """Canonical, social-card, and schema.org JSON-LD for the book's landing
    page, generated from the book's own config (#158). No fact is invented: a
    canonical/og:url and og:image appear only when a `site-url` is set (and a
    cover exists); absent facts are simply omitted, so an offline build never
    claims a false canonical URL. The shared emitter (webmeta) enforces the
    no-public-base law; this only assembles the book's facts."""

    from . import webmeta

    base = (book.site_url or "").strip()
    base = (base.rstrip("/") + "/") if base else ""
    desc = str(book.description or "").strip()
    width, height = cover_dims if cover_dims else (None, None)

    node = _landing_jsonld(book, base, desc, has_cover, format_names)
    return webmeta.head_fragment(
        base=base,
        title=book.title,
        description=desc,
        og_type="book",
        site_name=book.publisher or "",
        canonical=base,
        image=(base + "cover.jpg") if (base and has_cover) else "",
        image_width=width if has_cover else None,
        image_height=height if has_cover else None,
        image_alt=f"Cover of {book.title}" if has_cover else "",
        extra_properties=[("book:author", author) for author in book.authors],
        jsonld=node,
    )


def book_sitemap_locs(out: Path, book) -> list[str]:
    """The absolute URLs of every indexable HTML surface on the book site:
    the landing page and every reader page. Empty when no `site-url` is set,
    so a preview/offline build declares no sitemap at all (#158)."""

    base = (book.site_url or "").strip()
    if not base:
        return []
    base = base.rstrip("/") + "/"
    locs = [base]
    read = out / "read"
    if read.is_dir():
        for page in sorted(read.glob("*.html")):
            locs.append(base + "read/" + page.name)
    return locs


def _write_book_sitemap(out: Path, book) -> None:
    """A sitemap.xml and robots.txt for the book site, absolute against
    `site-url` and emitted only on a release build that has one. A
    preview/offline build gets neither, so it never advertises URLs it is not
    served from."""

    locs = book_sitemap_locs(out, book)
    if not locs:
        return
    base = (book.site_url or "").strip().rstrip("/") + "/"
    entries = "\n".join(f"  <url><loc>{loc}</loc></url>" for loc in locs)
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n</urlset>\n",
        encoding="utf-8",
    )
    (out / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n", encoding="utf-8"
    )
