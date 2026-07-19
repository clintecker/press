#!/usr/bin/env python3
"""Build the press's own web site from its documentation.

The press publishes books; this script makes it publish itself. Every
page is a file the repo already maintains (README, the docs/ suite,
CHANGELOG, CONTRIBUTING), rendered through pandoc with the site's own
stylesheet. The site carries no hand-written content, so it cannot
drift from the repo: REFERENCE.md is registry-generated and
drift-checked by the selftest, and everything else is the file a
reader would find at the source.

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
    ("README.md", "index.html", "Press"),
    ("docs/INSTALL.md", "install.html", "Install"),
    ("docs/ARCHITECTURE.md", "architecture.html", "Architecture"),
    ("docs/REFERENCE.md", "reference.html", "Reference"),
    ("CHANGELOG.md", "changelog.html", "Changelog"),
    ("CONTRIBUTING.md", "contributing.html", "Contributing"),
]


def nav_html(current: str) -> str:
    links = []
    for _, name, label in PAGES:
        aria = ' aria-current="page"' if name == current else ""
        links.append(f'    <a href="{name}"{aria}>{label}</a>')
    joined = "\n".join(links)
    return (
        '<header class="toolbar">\n'
        '  <nav aria-label="Site">\n'
        f"{joined}\n"
        "  </nav>\n"
        '  <a class="repo" href="https://github.com/clintecker/press">source</a>\n'
        "</header>\n"
    )


def build_page(source: str, name: str, label: str, nav_file: Path) -> None:
    title = "press" if name == "index.html" else f"press: {label.lower()}"
    subprocess.run(
        [
            "pandoc",
            str(ROOT / source),
            "--standalone",
            "--from=markdown",
            "--to=html5",
            # The site's own stylesheet colors code for both themes;
            # pandoc's highlighter hard-codes light-scheme span colors.
            # The old spelling: ubuntu's apt pandoc predates
            # --syntax-highlighting=none.
            "--no-highlight",
            f"--metadata=pagetitle:{title}",
            "--css=press.css",
            f"--include-before-body={nav_file}",
            "--output",
            str(OUT / name),
        ],
        check=True,
    )


def check_links() -> None:
    """Every local reference on every page must resolve; a page that
    links a file this build did not produce is a broken site, not a
    warning."""

    problems = []
    for page in OUT.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        for target in re.findall(r'(?:href|src)="([^"]+)"', text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            candidate = OUT / target.split("#", 1)[0]
            if not candidate.is_file():
                problems.append(f"{page.name}: {target}")
    if problems:
        raise SystemExit(
            "site links do not resolve:\n"
            + "\n".join(f"  - {p}" for p in problems)
        )


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    shutil.copy(ROOT / "site" / "press.css", OUT / "press.css")
    for source, name, label in PAGES:
        nav_file = OUT / f".nav-{name}"
        nav_file.write_text(nav_html(name), encoding="utf-8")
        build_page(source, name, label, nav_file)
        nav_file.unlink()
    check_links()
    print(f"+ built press site -> {OUT.relative_to(ROOT)} ({len(PAGES)} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
