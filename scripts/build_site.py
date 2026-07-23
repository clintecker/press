#!/usr/bin/env python3
"""Build the press's own web site from its documentation.

The press publishes books; this script makes it publish itself. Every
page is a file the repo already maintains (README, the docs/ suite,
CHANGELOG, CONTRIBUTING, SUPPORT, SECURITY, ROADMAP), rendered through
pandoc with the site's own stylesheet. The site carries no
hand-written content, so a page cannot drift from the repo; the two
ways the site itself could fall out of phase are guarded here:

- A documentation file the page lists forgot: every Markdown file at
  the root and under docs/ must be published or appear in
  NOT_PUBLISHED with a stated reason, or the build fails.
- A stale deploy serving yesterday's site: every page footer carries
  the commit it was built from, so phase is visible, and CI builds
  the site on every push so a breakage goes red before deploy.

Run from the repo root: python3 scripts/build_site.py
Output: build/site/
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
# `escape` by name, not the module: build_page binds a local named `html`.
from html import escape
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "site"

# The site's public home. Canonical URLs, social cards, and the sitemap are
# absolute against it; a page never claims a canonical URL it is not served
# from. (This is the press's own docs site, not a book's site-url.)
SITE_URL = "https://clintecker.github.io/press/"

# The site navigation, grouped so it stays scannable as the docs grow.
# Each group is (label, [(source, output name, nav label), ...]).
NAV_GROUPS = [
    ("Guide", [
        ("site/landing.md", "index.html", "press"),
        ("docs/QUICKSTART.md", "quickstart.html", "quickstart"),
        ("docs/INSTALL.md", "install.html", "install"),
        ("docs/CONFIGURATION.md", "configuration.html", "configuration"),
        ("docs/BOOK-PARTS.md", "book-parts.html", "book parts"),
        ("docs/GALLERY.md", "gallery.html", "gallery"),
        ("docs/COVER-STYLES.md", "cover-styles.html", "cover styles"),
        ("docs/PRINT-ORDERING.md", "print-ordering.html", "print ordering"),
        ("docs/PRINT-FORMATS.md", "print-formats.html", "trim & binding"),
        ("docs/LULU.md", "lulu.html", "printing at lulu"),
        ("docs/DESK.md", "desk.html", "desk"),
    ]),
    ("Reference", [
        ("docs/REFERENCE.md", "reference.html", "reference"),
        ("docs/ARCHITECTURE.md", "architecture.html", "architecture"),
        ("docs/INVARIANTS.md", "invariants.html", "invariants"),
        ("docs/PROVIDER-QUALIFICATION.md", "provider-qualification.html", "providers"),
        ("docs/COMPATIBILITY.md", "compatibility.html", "compatibility"),
        ("docs/MIGRATION.md", "migration.html", "migration"),
    ]),
    ("Project", [
        ("ROADMAP.md", "roadmap.html", "roadmap"),
        ("CHANGELOG.md", "changelog.html", "changelog"),
    ]),
]

# (source, output name, navigation label) — flat, for the build loop and
# the completeness check.
PAGES = [page for _, group in NAV_GROUPS for page in group]

FOOTER_PAGES = [
    ("CONTRIBUTING.md", "contributing.html", "contributing"),
    ("SUPPORT.md", "support.html", "support"),
    ("SECURITY.md", "security.html", "security"),
]

# Repo Markdown that deliberately stays off the site, with the reason.
NOT_PUBLISHED = {
    "README.md": "the repository's front page; the site's home is site/landing.md, "
                 "written for a first-time author rather than a browsing developer",
    "CODE_OF_CONDUCT.md": "GitHub community-profile file, surfaced by GitHub itself",
    "GOVERNANCE.md": "GitHub community-profile file, surfaced by GitHub itself",
    "CLAUDE.md": "agent working instructions for this repo, not documentation",
    "AGENTS.md": "the same working instructions in the agents.md convention",
    "docs/TUI-PLAN.md": "internal design plan; lives in the repo and issues, not the docs site",
    "docs/DIRECT-ORDERING-PLAN.md": "internal PRD/TRD; lives in the repo and issues, not the docs site",
    "docs/PRINT-PROFILES-PLAN.md": "internal v2 design record; lives in the repo and issues, not the docs site",
    "docs/EXTENSION-CONTRACT.md": "implementer-facing spec for extending the press "
                                  "itself; lives in the repo for the few who write an "
                                  "extension, not on a site written for authors",
}


def check_completeness() -> None:
    """Every Markdown file a reader could find in the repo is either on
    the site or consciously excluded; a new doc cannot be silently
    absent."""

    published = {source for source, _, _ in PAGES + FOOTER_PAGES}
    candidates = [p.name for p in ROOT.glob("*.md")]
    candidates += [f"docs/{p.name}" for p in (ROOT / "docs").glob("*.md")]
    unaccounted = [
        c for c in candidates if c not in published and c not in NOT_PUBLISHED
    ]
    if unaccounted:
        raise SystemExit(
            "docs absent from the site and not consciously excluded:\n"
            + "\n".join(f"  - {c}" for c in unaccounted)
            + "\nadd each to PAGES/FOOTER_PAGES or to NOT_PUBLISHED with a reason"
        )


def built_from() -> tuple[str, str]:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()

    return git("rev-parse", "--short", "HEAD"), git("show", "-s", "--format=%cs", "HEAD")


def nav_html(current: str) -> str:
    groups = []
    for group_label, pages in NAV_GROUPS:
        links = []
        for _, name, label in pages:
            aria = ' aria-current="page"' if name == current else ""
            links.append(f'      <a href="{name}"{aria}>{label}</a>')
        joined = "\n".join(links)
        groups.append(
            f'    <span class="nav-group" role="group" aria-label="{group_label}">\n'
            f'      <span class="nav-group-label">{group_label}</span>\n'
            f"{joined}\n"
            "    </span>"
        )
    joined_groups = "\n".join(groups)
    return (
        '<header class="toolbar">\n'
        '  <a class="wordmark" href="index.html" aria-label="press">'
        '<img class="wm-lockup wm-light" src="brand/press-lockup.svg" alt="">'
        '<img class="wm-lockup wm-dark" src="brand/press-lockup-dark.svg" alt="">'
        '</a>\n'
        '  <input type="checkbox" id="nav-toggle" class="nav-toggle" aria-label="Toggle menu">\n'
        '  <label for="nav-toggle" class="nav-burger" title="Menu" aria-hidden="true">'
        "<span></span><span></span><span></span></label>\n"
        '  <nav aria-label="Site">\n'
        f"{joined_groups}\n"
        '    <a class="repo" href="https://github.com/clintecker/press">source ↗</a>\n'
        "  </nav>\n"
        "</header>\n"
    )


def footer_html(current: str) -> str:
    sha, date = built_from()
    links = []
    for _, name, label in FOOTER_PAGES:
        aria = ' aria-current="page"' if name == current else ""
        links.append(f'    <a href="{name}"{aria}>{label}</a>')
    joined = "\n".join(links)
    return (
        '<footer class="colophon">\n'
        '  <nav aria-label="Policies">\n'
        f"{joined}\n"
        "  </nav>\n"
        f'  <p class="stamp">built from '
        f'<a class="sha" href="https://github.com/clintecker/press/commit/{sha}">{sha}</a>'
        f" ({date}); the site tracks main and is regenerated on every push</p>\n"
        "</footer>\n"
    )


# A page's <body> class, so the stylesheet can specialize a surface without
# any per-page markup: the landing gets its front-door treatment, and the
# generated-record pages (an id/name heading, a subtitle, prose, and
# labelled fields) render as cards.
BODY_CLASSES = {
    "index.html": "home",
    "invariants.html": "doc-entries",
    "provider-qualification.html": "doc-entries",
}

# The Markdown links to GitHub-blob URLs so it also reads correctly on
# GitHub. On the site, a link to a doc that IS a site page is rewritten to
# that local page, so a reader stays on the site; a doc with no site page
# (an internal plan, a data file) keeps its GitHub link.
GITHUB_BLOB = "https://github.com/clintecker/press/blob/main/"


def published_links() -> dict[str, str]:
    """GitHub-blob URL -> local page, for every doc this site publishes."""

    return {f"{GITHUB_BLOB}{source}": name for source, name, _ in PAGES + FOOTER_PAGES}


def rewrite_internal_links(html: str) -> str:
    """Point every link-to-a-published-doc at its local page, preserving any
    #fragment (only the URL prefix inside href="…" is replaced)."""

    for url, name in published_links().items():
        html = html.replace(f'href="{url}', f'href="{name}')
    return html


def page_description(source: str) -> str:
    """A one-line description from the source's first real paragraph, so
    search results and link previews read a meaningful summary rather than
    inferring one from the body. Deterministic: derived from the doc, not
    hand-maintained per page."""

    import html as html_mod

    text = (ROOT / source).read_text(encoding="utf-8")
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        # Skip headings, code fences, tables, lists, and front-matter fences.
        if not block or block.startswith(("#", "```", "|", "-", "*", ">", "<!--")):
            continue
        one = " ".join(block.split())
        one = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", one)   # link text only
        one = re.sub(r"[`*_]", "", one)                        # drop md marks
        if len(one) > 157:
            one = one[:157].rsplit(" ", 1)[0] + "..."
        return html_mod.escape(one)
    return "The press: build, check, and verify books from Markdown."


def head_metadata(name: str, title: str, description: str) -> str:
    """Canonical, Open Graph, and Twitter-card tags for one page, injected
    into <head> so identity is declared, not inferred."""

    import html as html_mod

    canonical = SITE_URL if name == "index.html" else SITE_URL + name
    social = SITE_URL + "brand/press-lockup-reversed.png"
    t = html_mod.escape(title)
    return "\n".join([
        f'  <meta name="description" content="{description}" />',
        f'  <link rel="canonical" href="{canonical}" />',
        '  <link rel="icon" type="image/svg+xml" href="brand/press-favicon.svg" />',
        '  <link rel="icon" type="image/png" href="brand/press-icon-ink.png" />',
        '  <meta property="og:type" content="website" />',
        '  <meta property="og:site_name" content="press" />',
        f'  <meta property="og:title" content="{t}" />',
        f'  <meta property="og:description" content="{description}" />',
        f'  <meta property="og:url" content="{canonical}" />',
        f'  <meta property="og:image" content="{social}" />',
        '  <meta name="twitter:card" content="summary_large_image" />',
        f'  <meta name="twitter:title" content="{t}" />',
        f'  <meta name="twitter:description" content="{description}" />',
        f'  <meta name="twitter:image" content="{social}" />',
    ]) + "\n"


# ---- The gallery, generated from the example books themselves -------------
#
# The gallery must not describe the examples by hand: a written-out card goes
# stale the moment an example changes its palette, gains a feature, or a sixth
# book lands. These readers take the facts from each example's own config and
# files, so the page states what the examples actually are and a new example
# appears in the gallery by existing.
#
# Stdlib only, deliberately: the docs-site workflow installs pandoc and
# nothing else, so PyYAML is not available here. The readers below understand
# the small, known shape the example configs use, and every one of them fails
# the build rather than rendering a blank card.

EXAMPLES = ROOT / "examples"

# Built example artifacts (PDF + page previews), produced by
# scripts/build_examples.py inside the toolchain container before this script
# runs. Absent on a plain local `build_site.py` (which has only pandoc), and
# the gallery degrades to text-only cards when they are missing -- so the
# local build and its link checks still pass.
EXAMPLE_ARTIFACTS = ROOT / "build" / "examples"

# Where the artifacts are served from on the site.
GALLERY_DIR = "gallery"

# Where docs/GALLERY.md asks for the generated cards.
GALLERY_MARKER = "<!--GALLERY-CARDS-->"

# The cover-style library and where docs/COVER-STYLES.md asks for its catalogue.
COVER_STYLES_DATA = ROOT / "src" / "press" / "data" / "cover-styles.yaml"
COVER_STYLES_IMAGES = ROOT / "site" / "cover-styles"
COVER_STYLES_MARKER = "<!--COVER-STYLES-->"

# The card shows the physical trim size, not the internal profile name.
PROFILE_LABELS = {"novella-5x8": "5×8", "house-6x9": "6×9"}


def _yaml_scalar(text: str, key: str, indent: str = "") -> str | None:
    """A single-line `key: value`, with optional quotes, at a given indent."""
    match = re.search(rf'^{indent}{key}:[ \t]*(.+?)[ \t]*$', text, re.M)
    if not match:
        return None
    value = match.group(1).strip()
    if value in (">-", "|", ">", "|-"):     # a block scalar, not a value
        return None
    return value.strip('"').strip("'")


def _yaml_block(text: str, key: str) -> str | None:
    """A folded block scalar (`key: >-`) joined back into one line."""
    match = re.search(rf'^{key}:[ \t]*[>|]-?[ \t]*\n((?:[ \t]+.*\n?)+)', text, re.M)
    if not match:
        return None
    return " ".join(line.strip() for line in match.group(1).splitlines() if line.strip())


def _yaml_first_item(text: str, key: str) -> str | None:
    """The first entry of a simple `key:` / `  - value` list."""
    match = re.search(rf'^{key}:[ \t]*\n[ \t]+-[ \t]*(.+?)[ \t]*$', text, re.M)
    return match.group(1).strip('"').strip("'") if match else None


class Example(NamedTuple):
    """What the gallery says about one example book, read from the book."""

    dir: str
    title: str
    subtitle: str
    author: str
    publisher: str
    genre: str
    summary: str
    register: str
    trim: str
    paper: str
    ink: str
    accent: str
    chapters: int
    exercises: list[str]
    pages: int          # PDF page count, 0 when no PDF was built
    pdf: str            # served PDF filename, "" when absent
    previews: list[str]  # served preview-image filenames, in order


def _example_artifacts(slug: str) -> tuple[int, str, list[str]]:
    """The built PDF and page previews for one example, if this build has
    them staged (they are absent on a pandoc-only local run). Returns the
    PDF's page count, the PDF filename, and the preview filenames."""
    staged = EXAMPLE_ARTIFACTS / slug
    if not staged.is_dir():
        return 0, "", []
    pdf = staged / f"{slug}.pdf"
    previews = sorted(p.name for p in staged.glob("preview-*.jpg"))
    pages = 0
    count_file = staged / "pages.txt"
    if count_file.is_file():
        pages = int(count_file.read_text(encoding="utf-8").strip() or 0)
    return pages, (pdf.name if pdf.is_file() else ""), previews


def _is_unnumbered(md: Path) -> bool:
    """A chapter file whose heading is marked {.unnumbered} or {-} is front
    matter (a preface, a note), not a numbered chapter."""
    head = md.read_text(encoding="utf-8").lstrip().split("\n", 1)[0].rstrip()
    return "{.unnumbered}" in head or head.endswith("{-}")


def _example_facts(book: Path) -> Example:
    """Everything the gallery says about one example, read from the book."""
    meta = (book / "config" / "metadata.yaml").read_text(encoding="utf-8")
    aesthetic_file = book / "config" / "aesthetic.yaml"
    aesthetic = aesthetic_file.read_text(encoding="utf-8") if aesthetic_file.exists() else ""

    title = _yaml_scalar(meta, "title")
    if not title:
        raise SystemExit(f"gallery: {book.name} has no title in config/metadata.yaml")
    summary = _yaml_block(meta, "description") or _yaml_scalar(meta, "description")
    if not summary:
        raise SystemExit(f"gallery: {book.name} has no description to show")

    # The book's own colours, so the card is printed in the book's palette.
    palette = [
        _yaml_scalar(aesthetic, name, indent="  ")
        for name in ("paper", "ink", "accent")
    ]
    if not all(palette):
        raise SystemExit(f"gallery: {book.name} has no web-palette paper/ink/accent")

    profile = _yaml_scalar(meta, "profile", indent="  ")
    chapters = sorted((book / "book" / "chapters").glob("*.md"))
    # The chapter count is numbered chapters only; a preface or note marked
    # {.unnumbered} (or {-}) is front matter, not a chapter.
    numbered = [c for c in chapters if not _is_unnumbered(c)]
    appendices = sorted((book / "book" / "appendices").glob("*.md"))

    # What the example demonstrates, detected from what it actually contains.
    exercises: list[str] = []
    if (book / "config" / "front-matter.yaml").exists():
        exercises.append("front matter")
    if (book / "config" / "index-terms.yaml").exists():
        exercises.append("subject index")
    if (book / "assets" / "web" / "extra.css").exists():
        exercises.append("custom web CSS")
    if appendices:
        exercises.append(f"{len(appendices)} appendix" if len(appendices) == 1
                         else f"{len(appendices)} appendices")
    if any("[^" in c.read_text(encoding="utf-8") for c in chapters):
        exercises.append("footnotes")
    if profile:
        exercises.append("non-default trim")
    opening = re.search(
        r'^chapter-opening:[ \t]*\n(?:[ \t]+.*\n)*?[ \t]+style:[ \t]*["\']?([a-z-]+)',
        meta, re.M)
    if opening and opening.group(1) in ("drop-cap", "raised-cap"):
        exercises.append(f"{opening.group(1)} openings")
    binding = _yaml_scalar(meta, "binding", indent="  ")
    if binding and binding != "perfect-bound":
        exercises.append(f"{binding} binding")

    pages, pdf, previews = _example_artifacts(book.name)

    return Example(
        dir=book.name,
        title=title,
        subtitle=_yaml_scalar(meta, "subtitle") or "",
        author=_yaml_first_item(meta, "author") or "",
        publisher=_yaml_scalar(meta, "publisher") or "",
        genre=_yaml_first_item(meta, "keywords") or "",
        summary=summary,
        register=(_yaml_block(aesthetic, "register")
                  or _yaml_scalar(aesthetic, "register") or ""),
        trim=PROFILE_LABELS.get(profile or "house-6x9", profile or "6×9"),
        paper=palette[0] or "", ink=palette[1] or "", accent=palette[2] or "",
        chapters=len(numbered),
        exercises=exercises,
        pages=pages, pdf=pdf, previews=previews,
    )


def gallery_cards_html() -> str:
    """The gallery's cards, in the examples' own colours."""
    books = sorted(d for d in EXAMPLES.iterdir() if (d / "config" / "metadata.yaml").exists())
    if not books:
        raise SystemExit("gallery: no example books found under examples/")
    cards = []
    for book in books:
        ex = _example_facts(book)
        chips = "".join(f"<li>{escape(e)}</li>" for e in ex.exercises)
        register = (f'<p class="ex-register">{escape(ex.register)}</p>'
                    if ex.register else "")
        # The built pages, when this build has them: real page images from the
        # book's own PDF, on the book's own paper colour, and a link to the
        # whole file. The interior prints in a single ink, so the pages show
        # that ink on that paper -- the honest palette -- while the accent (a
        # cover and screen colour, not an interior ink) stays the card's chrome.
        # Emitted only when the files exist, so a pandoc-only local build still
        # passes the link check.
        preview = ""
        if ex.previews:
            # preview-1 is the cover; the rest are interior pages, each named
            # distinctly so a screen reader does not hear the same alt twice.
            interior = ["An early interior page of", "A later interior page of"]
            alts = [f"Cover of {ex.title}"] + [
                f"{interior[i] if i < len(interior) else 'An interior page of'} {ex.title}"
                for i in range(len(ex.previews) - 1)]
            imgs = "".join(
                f'<img src="{GALLERY_DIR}/{ex.dir}/{escape(name)}" loading="lazy"'
                f' alt="{escape(alt)}">'
                for name, alt in zip(ex.previews, alts)
            )
            preview = (f'<a class="ex-pages" href="{GALLERY_DIR}/{ex.dir}/{escape(ex.pdf)}"'
                       f' aria-label="Open {escape(ex.title)} (PDF)">{imgs}</a>')
        swatches = "".join(
            f'<li style="--sw:{colour}">{label}</li>'
            for colour, label in ((ex.paper, "paper"), (ex.ink, "ink"), (ex.accent, "accent"))
        )
        pdf_link = ""
        if ex.pdf:
            span = f" · {ex.pages} pp" if ex.pages else ""
            pdf_link = (f'<a class="ex-pdf" href="{GALLERY_DIR}/{ex.dir}/{escape(ex.pdf)}"'
                        f' aria-label="Read {escape(ex.title)} as a PDF">'
                        f'Read the PDF{span} ↓</a>')
        chapter_word = "chapter" if ex.chapters == 1 else "chapters"
        cards.append(f"""
<article class="ex" style="--ex-accent:{ex.accent};--ex-paper:{ex.paper};--ex-ink:{ex.ink}">
  {preview}
  <ul class="ex-swatches" aria-label="palette: paper, ink, accent">{swatches}</ul>
  <p class="ex-kind"><span>{escape(ex.genre)}</span>
    <span class="ex-trim">{escape(ex.trim)}</span></p>
  <h3 class="ex-name">{escape(ex.title)}</h3>
  <p class="ex-sub">{escape(ex.subtitle)}</p>
  <p class="ex-summary">{escape(ex.summary)}</p>
  {register}
  <ul class="ex-chips">{chips}</ul>
  <p class="ex-foot">
    <span>{escape(ex.publisher)} · {ex.chapters} {chapter_word}</span>
    <span class="ex-links">{pdf_link}
    <a href="https://github.com/clintecker/press/tree/main/examples/{ex.dir}"
       aria-label="{escape(ex.title)} source on GitHub">source →</a></span>
  </p>
</article>""")
    return f'<section class="gallery">{"".join(cards)}\n</section>'


def cover_styles_html() -> str:
    """The cover-style catalogue: one card per style in the library, its name,
    era, and note read from data/cover-styles.yaml and paired with the
    committed sample cover. Generated, so the page cannot drift from the
    library; a style with no sample image is simply skipped."""
    text = COVER_STYLES_DATA.read_text(encoding="utf-8")
    # Split on the 2-space-indented style ids, keeping the id and its block.
    parts = re.split(r'\n  ([a-z0-9-]+):\n', text)
    cards = []
    for i in range(1, len(parts), 2):
        sid, body = parts[i], parts[i + 1]
        image = COVER_STYLES_IMAGES / f"{sid}.jpg"
        if not image.is_file():
            continue

        def field(key: str, block: str = body) -> str:
            m = re.search(rf'^    {key}:[ \t]*"?(.+?)"?[ \t]*$', block, re.M)
            return m.group(1).strip().strip('"') if m else ""

        cards.append(f"""
<figure class="cs">
  <img src="cover-styles/{sid}.jpg" loading="lazy"
       alt="{escape(field('name'))} cover of Between the Tides">
  <figcaption>
    <span class="cs-name">{escape(field('name'))}</span>
    <span class="cs-era">{escape(field('era'))}</span>
    <span class="cs-note">{escape(field('note'))}</span>
    <code class="cs-id">{sid}</code>
  </figcaption>
</figure>""")
    if not cards:
        raise SystemExit("cover-styles: no sample images under site/cover-styles/")
    return f'<section class="cover-styles">{"".join(cards)}\n</section>'


def build_page(source: str, name: str, label: str) -> None:
    title = "press" if name == "index.html" else f"press: {label}"
    nav_file = OUT / f".nav-{name}"
    nav_file.write_text(nav_html(name), encoding="utf-8")
    footer_file = OUT / f".footer-{name}"
    footer_file.write_text(footer_html(name), encoding="utf-8")
    subprocess.run(
        [
            "pandoc",
            str(ROOT / source),
            "--standalone",
            "--from=markdown",
            "--to=html5",
            f"--metadata=pagetitle:{title}",
            # Emit <html lang="en"> for assistive tech and correct
            # hyphenation/voice (#157).
            "--metadata=lang=en",
            "--css=press.css",
            f"--include-before-body={nav_file}",
            f"--include-after-body={footer_file}",
            # Highlighting is ON: pandoc emits skylighting token classes on
            # code spans. Its injected <style> hard-codes light-scheme
            # colors, so it is stripped below and the stylesheet colors the
            # tokens for both themes instead (see press.css).
            "--output",
            str(OUT / name),
        ],
        check=True,
    )
    nav_file.unlink()
    footer_file.unlink()
    page = OUT / name
    html = page.read_text(encoding="utf-8")
    # Drop pandoc's injected highlight <style> (light-only); the token
    # colors live in press.css, theme-aware. This is the only inline style
    # on the page — the stylesheet arrives through --css as a <link>.
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.S)
    # Canonical URL and social-card metadata, so identity/description is
    # declared rather than inferred (#158).
    description = page_description(source)
    html = html.replace("</head>", head_metadata(name, title, description) + "</head>", 1)
    # The gallery's cards are generated from the example books; the page marks
    # where they belong. A missing marker is a build failure, not a quietly
    # card-less gallery.
    if name == "gallery.html":
        if GALLERY_MARKER not in html:
            raise SystemExit(f"gallery: {source} lost its {GALLERY_MARKER} marker")
        html = html.replace(GALLERY_MARKER, gallery_cards_html(), 1)
    if name == "cover-styles.html":
        if COVER_STYLES_MARKER not in html:
            raise SystemExit(f"cover-styles: {source} lost its {COVER_STYLES_MARKER} marker")
        html = html.replace(COVER_STYLES_MARKER, cover_styles_html(), 1)
    # Wrap the pandoc content in one <main class="prose"> between the
    # toolbar and the colophon, so the whole column is a single centered
    # container and no element can detach from it. The toolbar and footer
    # stay full-width outside it.
    html = html.replace("</header>",
                        '</header>\n<main class="prose" id="main-content">', 1)
    html = html.replace('<footer class="colophon">',
                        '</main>\n<footer class="colophon">', 1)
    # A skip link is the first focusable element, so a keyboard or screen
    # reader user can jump past the nav straight to the content (#157).
    html = re.sub(
        r"(<body[^>]*>)",
        r'\1\n<a class="skip-link" href="#main-content">Skip to content</a>',
        html, count=1)
    html = rewrite_internal_links(html)
    # The one script: a progressive-enhancement copy button on code blocks.
    # Deferred and optional; the page is complete without it.
    html = html.replace(
        "</body>", '<script src="copy.js" defer></script>\n</body>', 1)
    body_class = BODY_CLASSES.get(name)
    if body_class:
        html = html.replace("<body>", f'<body class="{body_class}">', 1)
    page.write_text(html, encoding="utf-8")


def check_links() -> None:
    """Every local reference on every page must resolve; a page that
    links a file this build did not produce is a broken site, not a
    warning. Stylesheet url() references count too."""

    problems = []
    referenced: dict[Path, list[str]] = {}
    for page in OUT.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        referenced[page] = re.findall(r'(?:href|src)="([^"]+)"', text)
    for sheet in OUT.glob("*.css"):
        text = sheet.read_text(encoding="utf-8")
        referenced[sheet] = re.findall(r'url\(["\']?([^)"\']+)["\']?\)', text)
    for origin, targets in referenced.items():
        for target in targets:
            if target.startswith(("http://", "https://", "#", "mailto:", "data:")):
                continue
            candidate = origin.parent / target.split("#", 1)[0]
            if not candidate.is_file():
                problems.append(f"{origin.name}: {target}")
    if problems:
        raise SystemExit(
            "site links do not resolve:\n"
            + "\n".join(f"  - {p}" for p in problems)
        )


def check_internal_links() -> None:
    """No page links to GitHub for a doc the site publishes: that link must
    point at the local page instead, so a reader stays on the site. Only a
    doc with no site page may keep its GitHub link."""

    problems = []
    for _, name, _ in PAGES + FOOTER_PAGES:
        html = (OUT / name).read_text(encoding="utf-8")
        for url, target in published_links().items():
            if f'href="{url}' in html:
                problems.append(f"{name} links to {url} instead of {target}")
    if problems:
        raise SystemExit(
            "site links to GitHub for a doc it publishes:\n"
            + "\n".join(f"  - {p}" for p in problems)
        )


def check_accessibility() -> None:
    """Every page carries the landmark semantics assistive tech relies on: a
    declared language, one `main` landmark, and a skip-to-content link as the
    first focusable element (#157). A page missing any is a build failure,
    not a silent regression."""

    required = {
        'lang="en"': "a declared document language",
        '<main ': "a main landmark",
        'class="skip-link"': "a skip-to-content link",
        'id="main-content"': "a skip-link target",
        'rel="canonical"': "a canonical URL",
        'name="description"': "a meta description",
        'property="og:title"': "an Open Graph title",
    }
    problems = []
    for page in OUT.glob("*.html"):
        html = page.read_text(encoding="utf-8")
        for needle, what in required.items():
            if needle not in html:
                problems.append(f"{page.name}: missing {what}")
    if problems:
        raise SystemExit(
            "site pages lack accessibility landmarks:\n"
            + "\n".join(f"  - {p}" for p in problems)
        )


def write_sitemap_and_robots() -> None:
    """A deterministic sitemap of every published page and a robots.txt that
    points at it; both absolute against SITE_URL (#158)."""

    urls = [SITE_URL] + [
        SITE_URL + name for _, name, _ in PAGES + FOOTER_PAGES if name != "index.html"
    ]
    entries = "\n".join(f"  <url><loc>{u}</loc></url>" for u in urls)
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n</urlset>\n",
        encoding="utf-8")
    (OUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n",
        encoding="utf-8")


def main() -> int:
    check_completeness()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    shutil.copy(ROOT / "site" / "press.css", OUT / "press.css")
    shutil.copy(ROOT / "site" / "copy.js", OUT / "copy.js")
    shutil.copytree(ROOT / "site" / "fonts", OUT / "fonts")
    # Brand assets: the favicon (SVG, PNG fallback) and the social card. The
    # .md README beside them is documentation and is not copied.
    (OUT / "brand").mkdir()
    for asset in sorted((ROOT / "site" / "brand").glob("*.*")):
        if asset.suffix.lower() in (".svg", ".png"):
            shutil.copy(asset, OUT / "brand" / asset.name)
    # Staged example artifacts (PDF + page previews), when a toolchain build
    # produced them. Copied in before the pages are built and the link check
    # runs, so the gallery's PDF and image references resolve. Absent on a
    # pandoc-only build, and the gallery simply omits them.
    if EXAMPLE_ARTIFACTS.is_dir():
        shutil.copytree(EXAMPLE_ARTIFACTS, OUT / GALLERY_DIR)
    # The cover-style catalogue's sample images (committed, one per style).
    if COVER_STYLES_IMAGES.is_dir():
        shutil.copytree(COVER_STYLES_IMAGES, OUT / "cover-styles")
    for source, name, label in PAGES + FOOTER_PAGES:
        build_page(source, name, label)
    write_sitemap_and_robots()
    check_links()
    check_internal_links()
    check_accessibility()
    pages = len(PAGES) + len(FOOTER_PAGES)
    print(f"+ built press site -> {OUT.relative_to(ROOT)} ({pages} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
