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
from . import reader_meta
from . import yamlio

# Re-exported so the public build API is unchanged after the reader-metadata
# split; landing_head_metadata and inject_reader_metadata are also used below.
from .reader_meta import (
    book_sitemap_locs,  # noqa: F401
    inject_reader_metadata,
    landing_head_metadata,
)


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


def _pages_download_rows(slug: str, trim_text: str) -> list[str]:
    """The download table's rows: the chapter edition first, then each produced
    download that maps to a listed edition label."""

    import html as html_mod

    rows = [
        '    <tr><td><a href="read/index.html">Chapter edition</a></td>\n'
        '        <td class="desc">the book as a small website, one chapter per page</td></tr>'
    ]
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
    return rows


def _landing_optional_blocks(root: Path, meta: dict) -> dict[str, str]:
    """The landing page's optional HTML blocks (cover, imprint device, source
    paragraph, commerce), each empty unless its asset or config exists."""

    import html as html_mod

    from . import commerce as commerce_mod

    title = html_mod.escape(str(meta["title"]))
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
    return {
        "{{COVER_BLOCK}}": cover_block,
        "{{LOGO_BLOCK}}": logo_block,
        "{{REPO_PARAGRAPH}}": repo_paragraph,
        "{{COMMERCE_BLOCK}}": commerce_mod.render(commerce_mod.load(meta)),
    }


def _landing_index_html(root: Path, meta: dict, trim_text: str) -> str:
    """The fully-assembled landing index.html: template, metadata head, optional
    blocks, and any book extra.css, with every fact HTML-escaped."""

    import html as html_mod

    from . import aesthetic, webmeta

    title = html_mod.escape(str(meta["title"]))
    has_cover = (root / "assets" / "cover.jpg").is_file()
    head_meta = landing_head_metadata(
        booklib.book(),
        has_cover=has_cover,
        format_names=list(download_names()),
        cover_dims=reader_meta._image_dims(root / "assets" / "cover.jpg") if has_cover else None,
    )
    blocks = _landing_optional_blocks(root, meta)
    # The replacement order matches the original single-function pass exactly,
    # so a value that happened to contain another placeholder token resolves
    # identically (the byte-for-byte landing contract).
    replacements = {
        "{{TITLE}}": title,
        "{{DESCRIPTION}}": html_mod.escape(str(meta.get("description", "")).strip()),
        "{{HEAD_META}}": head_meta,
        "{{SUBTITLE_STACK}}": subtitle_stack_html(str(meta.get("subtitle") or "")),
        "{{COVER_BLOCK}}": blocks["{{COVER_BLOCK}}"],
        "{{COMMERCE_BLOCK}}": blocks["{{COMMERCE_BLOCK}}"],
        "{{EDITION_ROWS}}": "\n".join(_pages_download_rows(booklib.slug(), trim_text)),
        "{{REPO_PARAGRAPH}}": blocks["{{REPO_PARAGRAPH}}"],
        "{{LOGO_BLOCK}}": blocks["{{LOGO_BLOCK}}"],
        "{{DATE}}": html_mod.escape(booklib.book().date),
        "{{COPYRIGHT}}": html_mod.escape(booklib.book().copyright),
        "{{PUBLISHER}}": html_mod.escape(booklib.book().publisher),
        "{{PLACE}}": html_mod.escape(booklib.book().publisher_place),
    }
    page = (booklib.DATA / "web" / "index-template.html").read_text(encoding="utf-8")
    for key, value in replacements.items():
        page = page.replace(key, value)
    page = aesthetic.substitute_web(page)
    extra = root / "assets" / "web" / "extra.css"
    if extra.is_file():
        overrides = (
            "<style>\n/* assets/web/extra.css */\n"
            + extra.read_text(encoding="utf-8")
            + "\n</style>\n</head>"
        )
        page = page.replace("</head>", overrides, 1)
    return webmeta.label_table_cells(page)


def _copy_pages_assets(root: Path, out: Path) -> None:
    """Copy the book's optional assets, the reader site, and every produced
    download into the assembled pages tree, failing loudly on a missing
    download so the public downloads never have a silent gap."""

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


def pages_build(output_dir: str) -> None:
    """Assemble the GitHub Pages site: landing page, chapters, downloads.

    Every fact on the landing page derives from metadata and the
    artifacts actually produced; optional blocks render only when their
    asset or config exists, and all metadata is HTML-escaped.
    """

    root = booklib.root()
    out = root / output_dir
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    meta = booklib.metadata()
    trim = meta.get("trim") or {}
    trim_text = f"{trim.get('width', 6):g} by {trim.get('height', 9):g} inches"

    (out / "index.html").write_text(_landing_index_html(root, meta, trim_text), encoding="utf-8")

    # Generate the support/privacy/returns pages the CTA links to but the
    # publisher did not host themselves (#151), so every policy link
    # resolves to an honest page the book owns.
    _write_policy_pages(out, meta, booklib.book())

    _copy_pages_assets(root, out)
    reader_meta._write_book_sitemap(out, booklib.book())
    print(f"+ assembled pages site -> {output_dir}")


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


def _build_epub(slug: str) -> None:
    """The EPUB edition, carrying rights, an ISBN identifier when registered,
    and a valid dc:date so epubcheck accepts it (RSC-005)."""

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


def _build_html(slug: str) -> None:
    """The single-file HTML edition, read in a browser too, so its tables owe
    their cells the same column headers the reader pages carry."""

    pandoc_build("html", f"dist/{slug}.html")
    from . import webmeta

    edition = booklib.root() / "dist" / f"{slug}.html"
    edition.write_text(
        webmeta.label_table_cells(edition.read_text(encoding="utf-8")), encoding="utf-8"
    )


def build_target(target: str) -> None:
    if adapters.environment.which("pandoc") is None:
        raise SystemExit("pandoc is required")
    slug = booklib.slug()
    handlers = {
        "pdf": lambda: pandoc_build("pdf", f"dist/{slug}.pdf"),
        "print": lambda: pandoc_build("print", f"dist/{slug}-interior.pdf"),
        "epub": lambda: _build_epub(slug),
        "html": lambda: _build_html(slug),
        "markdown": lambda: markdown_build(f"dist/{slug}.md"),
        "site": lambda: site_build("dist/site"),
        "pages": lambda: pages_build("dist/pages"),
        "txt": lambda: pandoc_build(
            "portable", f"dist/{slug}.txt", extra=["--to=plain", "--columns=80"]
        ),
        "docx": lambda: pandoc_build("portable", f"dist/{slug}.docx", extra=["--to=docx"]),
    }
    handler = handlers.get(target)
    if handler is None:
        raise SystemExit(f"unknown build target: {target}")
    handler()
