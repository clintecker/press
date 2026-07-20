"""Verify the assembled Pages site as the public artifact it is.

The landing page and reader are the book's public face and were the
last artifacts nobody verified: a green build once shipped a landing
page with another book's name, a dead frontispiece, and links to a
different slug. This verifier crawls every HTML file under dist/pages,
proves every local reference resolves inside the site (stylesheet
url() assets and fragment anchors included), proves every declared
download exists and is linked from the landing page, and proves the
book's own words appear on its public reading surface.
"""

from __future__ import annotations

import html.parser
import re
import urllib.parse
from pathlib import Path

from . import booklib
from .verify_formats import VisibleText

CSS_URL = re.compile(r"""url\(["']?([^)"']+)["']?\)""")


class PageScan(html.parser.HTMLParser):
    """One pass over a page: references, anchor ids, style-block urls."""

    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []
        self.ids: set[str] = set()
        self._in_style = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in ("href", "src") and value:
                self.refs.append(value)
            if name == "id" and value:
                self.ids.add(value)
            if tag == "a" and name == "name" and value:
                self.ids.add(value)
        if tag == "style":
            self._in_style = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "style":
            self._in_style = False

    def handle_data(self, data: str) -> None:
        if self._in_style:
            self.refs.extend(CSS_URL.findall(data))


def scan_page(page: Path) -> PageScan:
    scan = PageScan()
    scan.feed(page.read_text(encoding="utf-8", errors="replace"))
    return scan


def check_refs(origin: Path, refs: list[str], pages: Path,
               ids_by_page: dict[Path, set[str]]) -> list[str]:
    """Every local reference from one file resolves inside the site;
    fragments resolve to a real anchor in their target page."""

    failures: list[str] = []
    where = origin.relative_to(pages)
    for ref in refs:
        parsed = urllib.parse.urlparse(ref)
        if parsed.scheme or ref.startswith("//"):
            continue
        local = urllib.parse.unquote(parsed.path)
        fragment = urllib.parse.unquote(parsed.fragment)
        if not local:
            if fragment and origin in ids_by_page and fragment not in ids_by_page[origin]:
                failures.append(f"{where}: dead fragment {ref}")
            continue
        if local.startswith("/"):
            failures.append(f"{where}: absolute reference {ref}")
            continue
        target = (origin.parent / local).resolve()
        if not target.exists():
            failures.append(f"{where}: broken reference {ref}")
            continue
        if not target.is_relative_to(pages):
            failures.append(f"{where}: reference escapes the site: {ref}")
            continue
        if fragment and target in ids_by_page and fragment not in ids_by_page[target]:
            failures.append(f"{where}: dead fragment {ref}")
    return failures


def check_downloads(index_refs: list[str], pages: Path,
                    downloads: list[str]) -> list[str]:
    failures: list[str] = []
    for name in downloads:
        if not (pages / "downloads" / name).is_file():
            failures.append(f"declared download missing from downloads/: {name}")
        links = [r for r in index_refs if r == f"downloads/{name}"]
        if len(links) != 1:
            failures.append(
                f"landing page links {name} {len(links)} times (expected exactly once)"
            )
    return failures


def check_reading_surface(pages: Path, sentinels: list[str],
                          title: str) -> list[str]:
    from .verify_formats import sentinel_present

    failures: list[str] = []
    text_parser = VisibleText()
    for page in sorted((pages / "read").glob("*.html")):
        text_parser.feed(page.read_text(encoding="utf-8", errors="replace"))
    reading_text = " ".join(" ".join(text_parser.parts).split())
    for sentinel in sentinels:
        if not sentinel_present(sentinel, reading_text):
            failures.append(f"public reading surface missing sentinel: {sentinel}")
    index_text = (pages / "index.html").read_text(encoding="utf-8", errors="replace")
    if title not in index_text:
        failures.append(f"landing page does not name the book: {title}")
    return failures


def check_commerce(pages: Path, config) -> list[str]:
    """The rendered print-order control matches the declared config: when
    ordering is enabled the landing page carries the CTA with the
    storefront, seller, and every policy link, and no page leaks a secret;
    when it is off, no stray CTA appears."""

    from . import commerce

    failures: list[str] = []
    index = (pages / "index.html").read_text(encoding="utf-8", errors="replace")
    has_cta = 'class="print-order"' in index
    if config is None or not config.enabled:
        if has_cta:
            failures.append("landing page shows a print-order CTA but ordering is not enabled")
        return failures
    if commerce.validate(config):
        failures.append("ordering is enabled but the CTA was not rendered "
                        "(config invalid; see press check)")
        return failures
    if not has_cta:
        failures.append("ordering is enabled but the landing page has no print-order CTA")
        return failures
    for label, value in [("storefront", config.storefront_url),
                         ("seller-of-record", config.seller_of_record),
                         *[(name, url) for name, url in config.policy_links()]]:
        if value not in index:
            failures.append(f"print-order CTA is missing the {label}")
    # A policy the publisher did not host is generated on the site; it must
    # exist and honestly disclose the seller of record.
    for kind in config.generated_kinds():
        filename = commerce.POLICY_KINDS[kind][3]
        page_path = pages / filename
        if not page_path.is_file():
            failures.append(f"generated {kind} policy page {filename} is missing")
        elif config.seller_of_record not in page_path.read_text(encoding="utf-8", errors="replace"):
            failures.append(f"generated {kind} policy page does not disclose the seller of record")
    for page in sorted(pages.rglob("*.html")):
        if commerce._SECRET_MARKERS.search(page.read_text(encoding="utf-8", errors="replace")):
            failures.append(f"a rendered page appears to leak a secret: {page.name}")
    return failures


def check_landing_metadata(pages: Path, title: str, site_url: str) -> list[str]:
    """The landing page's structured metadata matches the book's config and
    invents nothing (#158): the JSON-LD names the book, a canonical URL is
    present exactly when a site-url is configured, and never otherwise (a
    false canonical on an offline build would misdirect search engines)."""

    import html as html_mod
    import json
    import re

    failures: list[str] = []
    text = (pages / "index.html").read_text(encoding="utf-8", errors="replace")
    m = re.search(r'<script type="application/ld\+json">\n(.*?)\n</script>', text, re.S)
    if not m:
        return ["landing page carries no JSON-LD structured metadata"]
    try:
        node = json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        return [f"landing page JSON-LD is not valid JSON: {exc}"]
    if node.get("name") != html_mod.unescape(title):
        failures.append(
            f"landing JSON-LD names {node.get('name')!r}, not the book "
            f"{html_mod.unescape(title)!r}")
    base = (site_url or "").strip().rstrip("/")
    has_canonical = 'rel="canonical"' in text
    if base and not has_canonical:
        failures.append("site-url is set but the landing page has no canonical URL")
    if not base and has_canonical:
        failures.append("landing page claims a canonical URL but no site-url is configured")
    if base and node.get("url") not in (base, base + "/"):
        failures.append(
            f"landing JSON-LD url {node.get('url')!r} does not match the site-url")
    return failures


def crawl(pages: Path, sentinels: list[str], downloads: list[str],
          title: str, commerce_config=None, site_url: str = "") -> list[str]:
    """Every defect found, as human-readable failure lines."""

    pages = pages.resolve()
    if not (pages / "index.html").is_file():
        return ["pages site has no index.html"]

    scans = {page: scan_page(page) for page in sorted(pages.rglob("*.html"))}
    ids_by_page = {page: scan.ids for page, scan in scans.items()}

    failures: list[str] = []
    for page, scan in scans.items():
        failures += check_refs(page, scan.refs, pages, ids_by_page)
    for sheet in sorted(pages.rglob("*.css")):
        refs = CSS_URL.findall(sheet.read_text(encoding="utf-8", errors="replace"))
        failures += check_refs(sheet, refs, pages, ids_by_page)
    failures += check_downloads(scans[pages / "index.html"].refs, pages, downloads)
    failures += check_reading_surface(pages, sentinels, title)
    failures += check_commerce(pages, commerce_config)
    failures += check_landing_metadata(pages, title, site_url)
    return failures


def main() -> int:
    import html as html_mod

    from . import commerce
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
        commerce.load(booklib.metadata()),
        booklib.book().site_url,
    )
    if failures:
        print("Pages verification failed:")
        for line in failures:
            print(f"  - {line}")
        return 1
    print(
        f"Verified dist/pages: every local reference resolves (fragments "
        f"and stylesheet assets included), {len(download_names())} downloads "
        "present and linked, sentinels on the public reading surface"
    )
    return 0
