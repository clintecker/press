"""Verify the assembled Pages site as the public artifact it is.

The landing page and reader are the book's public face and were the
last artifacts nobody verified: a green build once shipped a landing
page with another book's name, a dead frontispiece, and links to a
different slug. This verifier crawls every HTML file under dist/pages,
proves every local reference resolves inside the site, proves every
declared download exists and is linked from the landing page, and
proves the book's own words appear on its public reading surface.
"""

from __future__ import annotations

import html.parser
import urllib.parse
from pathlib import Path

from . import booklib
from .verify_formats import VisibleText


class RefCollector(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in ("href", "src") and value:
                self.refs.append(value)


def crawl(pages: Path, sentinels: list[str], downloads: list[str],
          title: str) -> list[str]:
    """Every defect found, as human-readable failure lines."""

    failures: list[str] = []
    pages = pages.resolve()
    html_files = sorted(pages.rglob("*.html"))
    if not (pages / "index.html").is_file():
        return ["pages site has no index.html"]

    index_refs: list[str] = []
    for page in html_files:
        collector = RefCollector()
        collector.feed(page.read_text(encoding="utf-8", errors="replace"))
        if page == pages / "index.html":
            index_refs = list(collector.refs)
        for ref in collector.refs:
            parsed = urllib.parse.urlparse(ref)
            if parsed.scheme or ref.startswith("//"):
                continue
            if ref.startswith("#"):
                continue
            local = urllib.parse.unquote(parsed.path)
            if not local:
                continue
            if local.startswith("/"):
                failures.append(f"{page.relative_to(pages)}: absolute reference {ref}")
                continue
            target = (page.parent / local).resolve()
            if not target.exists():
                failures.append(f"{page.relative_to(pages)}: broken reference {ref}")
            elif not target.is_relative_to(pages):
                failures.append(f"{page.relative_to(pages)}: reference escapes the site: {ref}")

    for name in downloads:
        if not (pages / "downloads" / name).is_file():
            failures.append(f"declared download missing from downloads/: {name}")
        links = [r for r in index_refs if r == f"downloads/{name}"]
        if len(links) != 1:
            failures.append(
                f"landing page links {name} {len(links)} times (expected exactly once)"
            )

    reader_pages = sorted((pages / "read").glob("*.html"))
    text_parser = VisibleText()
    for page in reader_pages:
        text_parser.feed(page.read_text(encoding="utf-8", errors="replace"))
    reading_text = " ".join(" ".join(text_parser.parts).split())
    for sentinel in sentinels:
        if " ".join(sentinel.split()) not in reading_text:
            failures.append(f"public reading surface missing sentinel: {sentinel}")
    index_text = (pages / "index.html").read_text(encoding="utf-8", errors="replace")
    if title not in index_text:
        failures.append(f"landing page does not name the book: {title}")
    return failures


def main() -> int:
    import html as html_mod

    from .build import download_names

    root = booklib.root()
    pages = root / "dist" / "pages"
    if not pages.is_dir():
        raise SystemExit("no dist/pages to verify; build pages first")
    failures = crawl(
        pages,
        booklib.sentinels(),
        download_names(),
        html_mod.escape(str(booklib.metadata()["title"])),
    )
    if failures:
        print("Pages verification failed:")
        for line in failures:
            print(f"  - {line}")
        return 1
    print(
        f"Verified dist/pages: every local reference resolves, "
        f"{len(download_names())} downloads present and linked, sentinels on "
        "the public reading surface"
    )
    return 0
