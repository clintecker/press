"""Build every format of the book from the Markdown sources in filename order.

Pandoc defaults live in the press as templates whose path entries use two
prefixes: "@press/..." resolves into the installed package's data directory,
"@book/..." resolves into the book repository. A "?optional" suffix drops the
entry when the book does not carry that file, which is how a book without a
cover, without woodcuts, or without custom front matter builds cleanly from
the same defaults.
"""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

from . import adapters
from . import booklib
from . import gen_authorities
from . import gen_front_matter
from . import gen_index
from . import yamlio


def run(command: list[str]) -> None:
    printable = " ".join(command)
    print(f"+ {printable}")
    env = adapters.environment.copy()
    env.setdefault("SOURCE_DATE_EPOCH", "1784160000")
    env["BOOK_ROOT"] = str(booklib.root())
    env["BOOK_PUBLISHER"] = str(booklib.metadata().get("publisher") or "")
    started = time.monotonic()
    adapters.process_runner.run(command, cwd=booklib.root(), env=env, check=True)
    elapsed = time.monotonic() - started
    if elapsed >= 1.0:
        print(f"  {command[0]} took {elapsed:.1f}s")


def book_inputs() -> list[str]:
    """Chapters, then appendices merged with generated appendices in letter order."""

    root = booklib.root()
    generated_dir = root / "build" / "generated"
    if generated_dir.exists():
        shutil.rmtree(generated_dir)
    chapters = [a for a in booklib.chapter_args() if "/chapters/" in a.replace("\\", "/")]
    appendices = [a for a in booklib.chapter_args() if "/appendices/" in a.replace("\\", "/")]
    for generated in (gen_index.generate(), gen_authorities.generate()):
        if generated is not None:
            appendices.append(str(generated.relative_to(root)))
    appendices.sort(key=lambda a: Path(a).name)
    return chapters + appendices


def woodcut_count() -> int:
    return len(booklib.plate_files(booklib.root() / "assets" / "woodcuts"))


def _resolve_entry(value: str) -> str | None:
    """Resolve one @-prefixed path; None means an optional file is absent."""

    optional = value.endswith("?optional")
    if optional:
        value = value[: -len("?optional")]
    if value.startswith("@press/"):
        path = booklib.DATA / value[len("@press/") :]
    elif value.startswith("@book/"):
        path = booklib.root() / value[len("@book/") :]
    else:
        return value
    if not path.exists():
        if optional:
            return None
        raise SystemExit(f"defaults reference a missing file: {path}")
    return str(path)


def _resolve_paths(node):
    if isinstance(node, dict):
        resolved = {}
        for key, value in node.items():
            value = _resolve_paths(value)
            if value is not None:
                resolved[key] = value
        return resolved
    if isinstance(node, list):
        values = [_resolve_paths(item) for item in node]
        return [item for item in values if item is not None]
    if isinstance(node, str):
        return _resolve_entry(node)
    return node


def cover_fragment_html(title: str) -> str:
    """The single-file edition's cover block; the title is data and is
    escaped like every other metadata interpolation into HTML."""

    import html as html_mod

    safe = html_mod.escape(title, quote=True)
    return (
        '<p style="text-align:center;margin:0 0 2em 0;">'
        f'<img src="assets/cover.jpg" alt="{safe} cover" '
        'style="max-width:100%;height:auto;'
        'box-shadow:0 2px 12px rgba(0,0,0,0.35);"/></p>\n'
    )


def _chapter_opening_settings():
    """The effective chapter-opening treatment: the active profile's default,
    overridden by the book's own ``chapter-opening`` if it sets one."""

    from . import dropcaps, profiles

    override = booklib.metadata().get("chapter-opening")
    return dropcaps.settings(profiles.active().chapter_opening, override)


def _scene_break_ornament() -> str:
    """The scene-break ornament the book's aesthetic asks for: ``asterism`` to
    set a Markdown thematic break as a centered asterism, or ``rule`` (the
    default) to leave it a plain horizontal rule. Anything unrecognized falls
    back to ``rule``, so a typo degrades to the unchanged behavior rather than
    breaking a build."""

    from . import aesthetic

    value = str((aesthetic.effective() or {}).get("scene-break", "rule"))
    return value if value in ("rule", "asterism", "fairy-dust") else "rule"


def render_defaults(name: str) -> Path:
    """Materialize a press defaults template for this book into build/."""

    defaults = yamlio.load(booklib.DATA / "defaults" / f"{name}.yaml")

    root = booklib.root()

    # Chapter-opening drop caps: the effective settings (profile default, book
    # override) reach the Lua filter as pandoc metadata, and for the PDF the
    # centralized \PressDropCap style is projected into a fragment. Off by
    # default, so a book that does not opt in is untouched.
    opening = _chapter_opening_settings()
    meta = defaults.setdefault("metadata", {})
    meta["chapter-opening-style"] = opening.style
    meta["chapter-opening-lines"] = opening.lines
    meta["chapter-opening-smallcaps"] = "true" if opening.small_caps_remainder else "false"

    # Scene-break ornament: the aesthetic may turn a Markdown thematic break
    # (`* * *`) into a centered asterism. Default `rule` leaves the horizontal
    # rule untouched, so a book that does not opt in renders byte-for-byte as
    # before; the scene-break.lua filter reads this in every edition.
    meta["scene-break-ornament"] = _scene_break_ornament()
    if name in ("pdf", "print"):
        from . import dropcaps as _dropcaps

        fragment = root / "build" / "profile-dropcap.tex"
        if opening.enabled:
            fragment.parent.mkdir(parents=True, exist_ok=True)
            fragment.write_text(_dropcaps.tex_setup(opening), encoding="utf-8")
        elif fragment.exists():
            fragment.unlink()  # a disabled build never carries a stale fragment
    if name == "html":
        cover = root / "assets" / "cover.jpg"
        if cover.is_file():
            fragment = root / "build" / "cover-fragment.html"
            fragment.parent.mkdir(parents=True, exist_ok=True)
            title = booklib.metadata()["title"]
            fragment.write_text(
                cover_fragment_html(str(title)),
                encoding="utf-8",
            )
    if name == "chunked":
        # The reader shows a cover only when the book has one; the
        # template must not reference an image that does not exist.
        defaults.setdefault("variables", {})["cover"] = (root / "assets" / "cover.jpg").is_file()
    if name in ("pdf", "print"):
        # An empty List of Plates is worse than none; only figure-bearing
        # books get the list.
        defaults.setdefault("variables", {})["lof"] = woodcut_count() > 0
        gen_front_matter.generate(include_cover=(name == "pdf"))
        from . import aesthetic, profiles

        aesthetic.write_tex_overrides()
        # The active print profile projects trim and interior geometry into a
        # fragment included right after the house header, overriding its
        # defaults. The house profile carries the v1 numbers, so a v1 book is
        # unchanged; another profile changes the page (#172).
        profiles.write_geometry_tex(profiles.active(), root / "build" / "profile-geometry.tex")
        if name == "print":
            # Flatten transparency and cap image resolution for the print
            # interior only; print-header.tex prepends build/print-assets to
            # graphicspath so lualatex embeds these copies, and the reading
            # PDF (which never prepends it) is unaffected.
            from . import print_safe

            print_safe.prepare(root)
    if name == "print" and (root / "tex" / "title-page-print.tex").is_file():
        # The print variant replaces the reading title page; never stack.
        defaults["include-in-header"] = [
            entry
            for entry in defaults["include-in-header"]
            if entry != "@book/tex/title-page.tex?optional"
        ]

    resolved = _resolve_paths(defaults)
    out = root / "build" / "defaults" / f"{name}.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yamlio.dump(resolved), encoding="utf-8")
    return out


def pandoc_build(defaults_name: str, output: str, extra: list[str] | None = None) -> None:
    root = booklib.root()
    (root / "dist").mkdir(parents=True, exist_ok=True)
    (root / "build").mkdir(parents=True, exist_ok=True)
    defaults = render_defaults(defaults_name)
    command = ["pandoc", f"--defaults={defaults}"]
    if extra:
        command.extend(extra)
    command.extend(book_inputs())
    command.extend(["--output", output])
    run(command)


def strip_heading_attrs(text: str) -> str:
    """Drop pandoc heading attributes ({-}, {.unnumbered}) from stitched output.

    The stitched Markdown is raw source, not a pandoc render, so attribute
    blocks would ship as literal text. Fence tracking keeps shell comments
    inside code blocks untouched.
    """

    lines = []
    fence = ""
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            fence = "" if fence == stripped[:3] else (fence or stripped[:3])
        elif not fence:
            line = re.sub(r"^(#{1,6}\s.*?)\s*\{[^}]*\}\s*$", r"\1", line)
        lines.append(line)
    return "\n".join(lines)


def markdown_build(output: str) -> None:
    """Stitch the canonical Markdown chapters into one distributable file."""

    root = booklib.root()
    (root / "dist").mkdir(parents=True, exist_ok=True)
    book = booklib.book()
    authors = ", ".join(book.authors)
    subtitle_line = f"*{book.subtitle}*\n\n" if book.subtitle else ""
    imprint = f" Published by {book.publisher}, {book.publisher_place}." if book.publisher else ""
    header = (
        f"# {book.title}\n\n{subtitle_line}By {authors}. {book.date}. {book.copyright}{imprint}\n"
    )
    parts = [header]
    inputs = book_inputs()
    for rel in inputs:
        text = strip_heading_attrs((root / rel).read_text(encoding="utf-8"))
        parts.append(text.strip() + "\n")
    (root / output).write_text("\n".join(parts), encoding="utf-8")
    print(f"+ stitched {len(inputs)} files -> {output}")


def recompress_images(target: Path) -> None:
    """Shrink reader images for the web; engravings tolerate quality 70 well."""

    from PIL import Image

    for path in sorted(target.rglob("*.jpg")):
        image = Image.open(path)
        image.save(path, quality=70, optimize=True)


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


def site_stylesheet() -> str:
    """The reader stylesheet, with the book in charge of every layer.

    A book that supplies assets/web/reader.css replaces the house sheet
    outright and owns the whole design; one that supplies
    assets/web/extra.css keeps the house sheet and appends its own
    declarations last, so they win the cascade. Either way the
    aesthetic palette substitution applies (a no-op unless the sheet
    declares the house tokens), and a book that supplies neither
    renders exactly as before.
    """

    from . import aesthetic

    root = booklib.root()
    own = root / "assets" / "web" / "reader.css"
    base = own if own.is_file() else booklib.DATA / "web" / "reader.css"
    css = aesthetic.substitute_web(base.read_text(encoding="utf-8"))
    # The design profile's web reading measure overrides the house sheet's
    # body; a book that supplies its own reader.css owns the whole design, so
    # the profile does not reach into it. The house profile appends nothing,
    # so a house book's stylesheet is byte-for-byte unchanged.
    if not own.is_file():
        from . import profiles

        css += profiles.web_css(profiles.active())
    extra = root / "assets" / "web" / "extra.css"
    if extra.is_file():
        css += "\n/* assets/web/extra.css */\n" + extra.read_text(encoding="utf-8")
    return css


def site_build(output_dir: str) -> None:
    """Per-chapter HTML site via pandoc's chunkedhtml writer."""

    root = booklib.root()
    out = root / output_dir
    if out.exists():
        shutil.rmtree(out)
    pandoc_build("chunked", output_dir, extra=["--to=chunkedhtml"])
    (out / "reader.css").write_text(site_stylesheet(), encoding="utf-8")
    cover = root / "assets" / "cover.jpg"
    if cover.is_file():
        shutil.copy(cover, out / "cover.jpg")
    woodcuts = root / "assets" / "woodcuts"
    if woodcuts.is_dir():
        shutil.copytree(woodcuts, out / "assets" / "woodcuts", dirs_exist_ok=True)
    recompress_images(out)
    # Stamp canonical/OG/JSON-LD onto every reader page (#158); a no-op for
    # the URL-shaped tags on an offline build with no site-url.
    inject_reader_metadata(out, booklib.book())
    archive = root / "dist" / f"{booklib.slug()}-site"
    if archive.with_suffix(".zip").exists():
        archive.with_suffix(".zip").unlink()
    shutil.make_archive(str(archive), "zip", root_dir=root / "dist", base_dir="site")


def download_names() -> list[str]:
    from . import registry

    return registry.download_names()


EDITION_DESCRIPTIONS = [
    (".pdf", "Print edition", "{trim}, typeset by LuaLaTeX, suitable for paper"),
    (".epub", "Circulating edition", "EPUB, for readers of every size"),
    (".html", "Single-leaf edition", "the whole book in one self-contained HTML file"),
    (".md", "Manuscript edition", "plain Markdown, agreeable to machines and their agents"),
    (".txt", "Telegraphic edition", "plain text at eighty columns, for terminals"),
    (".docx", "Office edition", "DOCX, for reviewers armed with tracked changes"),
    ("-site.zip", "Chapter edition, boxed", "the reading site, zipped for carrying"),
    ("-source.zip", "Source edition", "the manuscript and its configuration, archived"),
    ("-sources.md", "Table of authorities", "every factual claim mapped to its source"),
]


def _edition_row(name: str, slug: str, trim_text: str) -> tuple[str, str] | None:
    """The (label, description) for a download by its exact ``{slug}{suffix}``
    name, or None when it is not a listed edition. Matched exactly, never by
    ``endswith``: the sources companion ``{slug}-sources.md`` also ends in
    ``.md`` and would otherwise be labelled a second "Manuscript edition"
    beside the real ``{slug}.md``."""

    for suffix, label, desc in EDITION_DESCRIPTIONS:
        if name == f"{slug}{suffix}":
            return label, desc.format(trim=trim_text)
    return None


def subtitle_stack_html(subtitle: str) -> str:
    """The landing page's OR stack, mirroring the title page's seams."""

    import html as html_mod

    leading_or = bool(re.match(r"\s*or,", subtitle, re.IGNORECASE))
    clauses = [
        c.strip(" ;.")
        for c in re.split(r";?\s*\bor,\s*", subtitle, flags=re.IGNORECASE)
        if c.strip(" ;.")
    ]
    if not clauses:
        return ""
    lines = []
    for index, clause in enumerate(clauses):
        if index > 0 or leading_or:
            lines.append('      <span class="or sc">or,</span><br>')
        tag = "strong" if index == 0 else "span"
        close = "<br>" if index < len(clauses) - 1 else ""
        lines.append(f'      <{tag} class="sc">{html_mod.escape(clause)}</{tag}>{close}')
    return "\n".join(lines)


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


def pages_build(output_dir: str) -> None:
    """Assemble the GitHub Pages site: landing page, chapters, downloads.

    Every fact on the landing page derives from metadata and the
    artifacts actually produced; optional blocks render only when their
    asset or config exists, and all metadata is HTML-escaped.
    """

    import html as html_mod

    from . import webmeta

    root = booklib.root()
    out = root / output_dir
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    meta = booklib.metadata()
    title = html_mod.escape(str(meta["title"]))
    trim = meta.get("trim") or {}
    trim_text = f"{trim.get('width', 6):g} by {trim.get('height', 9):g} inches"

    rows = [
        '    <tr><td><a href="read/index.html">Chapter edition</a></td>\n'
        '        <td class="desc">the book as a small website, one chapter per page</td></tr>'
    ]
    slug = booklib.slug()
    for name in download_names():
        match = _edition_row(name, slug, trim_text)
        if match is None:
            continue
        label, description = match
        rows.append(
            f'    <tr><td><a href="downloads/{html_mod.escape(name)}">'
            f"{label}</a></td>\n"
            f'        <td class="desc">{html_mod.escape(description)}</td></tr>'
        )

    cover_block = ""
    if (root / "assets" / "cover.jpg").is_file():
        cover_block = (
            '    <div class="cover-plate">\n'
            f'      <a href="read/index.html"><img src="cover.jpg" '
            f'alt="Cover of {title}"></a>\n'
            "    </div>"
        )
    logo_block = ""
    if (root / "assets" / "press-logo.png").is_file():
        publisher = html_mod.escape(booklib.book().publisher)
        logo_block = (
            f'    <img class="press-logo" src="press-logo.png" alt="Imprint device of {publisher}">'
        )
    repo_paragraph = ""
    repository = str(meta.get("repository") or "")
    if repository:
        repo = html_mod.escape(repository)
        repo_paragraph = (
            "    <p>The source lives in "
            f'<a href="{repo}">a public build system</a>; versions and their\n'
            f'    contents are recorded in the <a href="{repo}/blob/main/CHANGELOG.md">changelog</a>,\n'
            f'    and finished releases live on the <a href="{repo}/releases">releases page</a>.</p>'
        )

    from . import commerce as commerce_mod

    commerce_block = commerce_mod.render(commerce_mod.load(meta))

    template = (booklib.DATA / "web" / "index-template.html").read_text(encoding="utf-8")
    has_cover = (root / "assets" / "cover.jpg").is_file()
    head_meta = landing_head_metadata(
        booklib.book(),
        has_cover=has_cover,
        format_names=list(download_names()),
        cover_dims=_image_dims(root / "assets" / "cover.jpg") if has_cover else None,
    )
    replacements = {
        "{{TITLE}}": title,
        "{{DESCRIPTION}}": html_mod.escape(str(meta.get("description", "")).strip()),
        "{{HEAD_META}}": head_meta,
        "{{SUBTITLE_STACK}}": subtitle_stack_html(str(meta.get("subtitle") or "")),
        "{{COVER_BLOCK}}": cover_block,
        "{{COMMERCE_BLOCK}}": commerce_block,
        "{{EDITION_ROWS}}": "\n".join(rows),
        "{{REPO_PARAGRAPH}}": repo_paragraph,
        "{{LOGO_BLOCK}}": logo_block,
        "{{DATE}}": html_mod.escape(booklib.book().date),
        "{{COPYRIGHT}}": html_mod.escape(booklib.book().copyright),
        "{{PUBLISHER}}": html_mod.escape(booklib.book().publisher),
        "{{PLACE}}": html_mod.escape(booklib.book().publisher_place),
    }
    page = template
    for key, value in replacements.items():
        page = page.replace(key, value)
    from . import aesthetic

    page = aesthetic.substitute_web(page)
    extra = root / "assets" / "web" / "extra.css"
    if extra.is_file():
        overrides = (
            "<style>\n/* assets/web/extra.css */\n"
            + extra.read_text(encoding="utf-8")
            + "\n</style>\n</head>"
        )
        page = page.replace("</head>", overrides, 1)
    (out / "index.html").write_text(webmeta.label_table_cells(page), encoding="utf-8")

    # Generate the support/privacy/returns pages the CTA links to but the
    # publisher did not host themselves (#151), so every policy link
    # resolves to an honest page the book owns.
    _write_policy_pages(out, meta, booklib.book())

    for optional in ("cover.jpg", "press-logo.png"):
        source = root / "assets" / optional
        if source.is_file():
            shutil.copy(source, out / optional)
    woodcuts = root / "assets" / "woodcuts"
    if woodcuts.is_dir():
        shutil.copytree(woodcuts, out / "woodcuts")
    shutil.copytree(root / "dist" / "site", out / "read")
    downloads = out / "downloads"
    downloads.mkdir()
    for name in download_names():
        source = root / "dist" / name
        if not source.exists():
            raise SystemExit(
                f"pages: {name} missing from dist; build it before pages "
                "(silent gaps in the public downloads are not allowed)"
            )
        shutil.copy(source, downloads / name)
    _write_book_sitemap(out, booklib.book())
    print(f"+ assembled pages site -> {output_dir}")


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


def _write_policy_pages(out, meta, book) -> None:
    """Write a generated support/privacy/returns page for each policy the
    publisher did not host themselves, styled in the book's palette. A no-op
    unless a valid, enabled commerce block asks for it."""

    import html as html_mod

    from . import aesthetic, booklib
    from . import commerce as commerce_mod

    config = commerce_mod.load(meta)
    if config is None or not config.enabled or commerce_mod.validate(config):
        return

    template = (booklib.DATA / "web" / "policy-template.html").read_text(encoding="utf-8")
    for kind in config.generated_kinds():
        heading, filename = commerce_mod.POLICY_KINDS[kind][2], commerce_mod.POLICY_KINDS[kind][3]
        page = template
        page = page.replace("{{TITLE}}", html_mod.escape(f"{book.title} — {heading}"))
        page = page.replace("{{BOOK_TITLE}}", html_mod.escape(book.title))
        page = page.replace(
            "{{BODY}}", commerce_mod.render_policy_body(config, book.publisher, kind)
        )
        (out / filename).write_text(aesthetic.substitute_web(page), encoding="utf-8")


def build_target(target: str) -> None:
    if adapters.environment.which("pandoc") is None:
        raise SystemExit("pandoc is required")
    slug = booklib.slug()
    if target == "pdf":
        pandoc_build("pdf", f"dist/{slug}.pdf")
    elif target == "print":
        pandoc_build("print", f"dist/{slug}-interior.pdf")
    elif target == "epub":
        from . import registrations

        book = booklib.book()
        rights = " ".join(
            part
            for part in (
                book.copyright,
                f"Published by {book.publisher}, {book.publisher_place}." if book.publisher else "",
            )
            if part
        )
        extra = ["--metadata", f"rights={rights}"]
        epub_isbn = registrations.isbn("epub")
        if epub_isbn:
            extra += ["--metadata", f"identifier=urn:isbn:{epub_isbn}"]
        year = booklib.year()
        if year:
            # The prose date ("First edition, 2026") is not a date to
            # pandoc, which then emits an empty dc:date that epubcheck
            # rejects (RSC-005). The extracted year is a valid dc:date
            # and leaves the displayed date untouched.
            epub_meta = booklib.root() / "build" / "epub-metadata.xml"
            epub_meta.parent.mkdir(parents=True, exist_ok=True)
            epub_meta.write_text(f"<dc:date>{year}</dc:date>\n", encoding="utf-8")
            extra += [f"--epub-metadata={epub_meta}"]
        pandoc_build("epub", f"dist/{slug}.epub", extra=extra)
    elif target == "html":
        pandoc_build("html", f"dist/{slug}.html")
        # The single-file edition is read in a browser too, so its tables owe
        # their cells the same column headers the reader pages carry.
        from . import webmeta

        edition = booklib.root() / "dist" / f"{slug}.html"
        edition.write_text(
            webmeta.label_table_cells(edition.read_text(encoding="utf-8")), encoding="utf-8"
        )
    elif target == "markdown":
        markdown_build(f"dist/{slug}.md")
    elif target == "site":
        site_build("dist/site")
    elif target == "pages":
        pages_build("dist/pages")
    elif target == "txt":
        pandoc_build("portable", f"dist/{slug}.txt", extra=["--to=plain", "--columns=80"])
    elif target == "docx":
        pandoc_build("portable", f"dist/{slug}.docx", extra=["--to=docx"])
    else:
        raise SystemExit(f"unknown build target: {target}")
