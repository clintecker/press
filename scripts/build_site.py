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

# The site navigation, grouped so it stays scannable as the docs grow.
# Each group is (label, [(source, output name, nav label), ...]).
NAV_GROUPS = [
    ("Guide", [
        ("README.md", "index.html", "press"),
        ("docs/QUICKSTART.md", "quickstart.html", "quickstart"),
        ("docs/INSTALL.md", "install.html", "install"),
        ("docs/CONFIGURATION.md", "configuration.html", "configuration"),
        ("docs/PRINT-ORDERING.md", "print-ordering.html", "print ordering"),
        ("docs/DESK.md", "desk.html", "desk"),
    ]),
    ("Reference", [
        ("docs/REFERENCE.md", "reference.html", "reference"),
        ("docs/ARCHITECTURE.md", "architecture.html", "architecture"),
        ("docs/INVARIANTS.md", "invariants.html", "invariants"),
        ("docs/PROVIDER-QUALIFICATION.md", "provider-qualification.html", "providers"),
        ("docs/COMPATIBILITY.md", "compatibility.html", "compatibility"),
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
    "CLAUDE.md": "agent working instructions for this repo, not documentation",
    "AGENTS.md": "the same working instructions in the agents.md convention",
    "docs/TUI-PLAN.md": "internal design plan; lives in the repo and issues, not the docs site",
    "docs/DIRECT-ORDERING-PLAN.md": "internal PRD/TRD; lives in the repo and issues, not the docs site",
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
        '  <a class="wordmark" href="index.html">press<span class="mark">.</span></a>\n'
        '  <input type="checkbox" id="nav-toggle" class="nav-toggle" aria-label="Toggle menu">\n'
        '  <label for="nav-toggle" class="nav-burger" title="Menu"><span></span></label>\n'
        '  <nav aria-label="Site">\n'
        f"{joined_groups}\n"
        '    <a class="repo" href="https://github.com/clintecker/press">source</a>\n'
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
        f'<a href="https://github.com/clintecker/press/commit/{sha}">{sha}</a>'
        f" ({date}); the site tracks main and is regenerated on every push</p>\n"
        "</footer>\n"
    )


# Pages whose content is a list of generated entries (an id/name heading,
# a subtitle line, prose, and labelled fields) rather than free prose; they
# get a body class so the stylesheet can render the entries as cards.
ENTRY_PAGES = {"invariants.html", "provider-qualification.html"}


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
            "--css=press.css",
            f"--include-before-body={nav_file}",
            f"--include-after-body={footer_file}",
            # The site's own stylesheet colors code for both themes;
            # pandoc's highlighter hard-codes light-scheme span colors.
            # The old spelling: ubuntu's apt pandoc predates
            # --syntax-highlighting=none.
            "--no-highlight",
            "--output",
            str(OUT / name),
        ],
        check=True,
    )
    nav_file.unlink()
    footer_file.unlink()
    if name in ENTRY_PAGES:
        page = OUT / name
        page.write_text(
            page.read_text(encoding="utf-8").replace(
                "<body>", '<body class="doc-entries">', 1),
            encoding="utf-8")


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


def main() -> int:
    check_completeness()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    shutil.copy(ROOT / "site" / "press.css", OUT / "press.css")
    shutil.copytree(ROOT / "site" / "fonts", OUT / "fonts")
    for source, name, label in PAGES + FOOTER_PAGES:
        build_page(source, name, label)
    check_links()
    pages = len(PAGES) + len(FOOTER_PAGES)
    print(f"+ built press site -> {OUT.relative_to(ROOT)} ({pages} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
