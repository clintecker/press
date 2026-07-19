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

# (source, output name, navigation label)
PAGES = [
    ("README.md", "index.html", "press"),
    ("docs/INSTALL.md", "install.html", "install"),
    ("docs/ARCHITECTURE.md", "architecture.html", "architecture"),
    ("docs/REFERENCE.md", "reference.html", "reference"),
    ("ROADMAP.md", "roadmap.html", "roadmap"),
    ("docs/TUI-PLAN.md", "desk-plan.html", "desk plan"),
    ("CHANGELOG.md", "changelog.html", "changelog"),
]

FOOTER_PAGES = [
    ("CONTRIBUTING.md", "contributing.html", "contributing"),
    ("SUPPORT.md", "support.html", "support"),
    ("SECURITY.md", "security.html", "security"),
]

# Repo Markdown that deliberately stays off the site, with the reason.
NOT_PUBLISHED = {
    "CLAUDE.md": "agent working instructions for this repo, not documentation",
    "AGENTS.md": "the same working instructions in the agents.md convention",
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
    links = []
    for _, name, label in PAGES:
        aria = ' aria-current="page"' if name == current else ""
        links.append(f'    <a href="{name}"{aria}>{label}</a>')
    joined = "\n".join(links)
    return (
        '<header class="toolbar">\n'
        '  <a class="wordmark" href="index.html">press<span class="mark">.</span></a>\n'
        '  <nav aria-label="Site">\n'
        f"{joined}\n"
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
