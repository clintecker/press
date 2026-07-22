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
from pathlib import Path

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
        ("docs/PRINT-ORDERING.md", "print-ordering.html", "print ordering"),
        ("docs/PRINT-FORMATS.md", "print-formats.html", "trim & binding"),
        ("docs/LULU.md", "lulu.html", "printing at lulu"),
        ("docs/DESK.md", "desk.html", "desk"),
    ]),
    ("Reference", [
        ("docs/REFERENCE.md", "reference.html", "reference"),
        ("docs/ARCHITECTURE.md", "architecture.html", "architecture"),
        ("docs/EXTENSION-CONTRACT.md", "extension-contract.html", "extension contract"),
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
