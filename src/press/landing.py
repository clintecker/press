"""The GitHub Pages site: the landing page, its downloads table, the
generated policy pages, and the assembled ``dist/pages`` tree.

Split out of build.py so the build module stays about running pandoc over
the manuscript and this one about the public site assembled from what that
build produced. Every fact on the landing page derives from metadata and the
artifacts actually produced; optional blocks render only when their asset or
config exists, and all metadata is HTML-escaped.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from . import booklib
from . import reader_meta
from .reader_meta import landing_head_metadata


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
