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


# The metadata surfaces whose head contract this verifier enforces (#158):
# the landing page and every reader page. Commerce policy pages and download
# blobs are not part of the metadata contract.
def _metadata_surfaces(pages: Path) -> list[Path]:
    surfaces = [pages / "index.html"]
    surfaces += sorted((pages / "read").glob("*.html"))
    return [p for p in surfaces if p.is_file()]


# Local build paths and other data that must never reach a public preview or
# search index (#158). The commerce secret scan is reused for credential-shaped
# strings; these catch filesystem paths and file:// URLs.
_PRIVATE_DATA = re.compile(r"/Users/|/home/|/dist/|/build/|file://", re.IGNORECASE)

_JSONLD = re.compile(r'<script type="application/ld\+json">\n(.*?)\n\s*</script>', re.S)
_HEAD = re.compile(r"<head\b[^>]*>(.*?)</head>", re.S | re.I)


def _jsonld_nodes(text: str) -> list:
    """Every JSON-LD node on a page, flattening a top-level list into its
    members so a page may carry an Article and a BreadcrumbList together."""

    import json

    nodes: list = []
    for match in _JSONLD.finditer(text):
        loaded = json.loads(match.group(1))
        nodes.extend(loaded if isinstance(loaded, list) else [loaded])
    return nodes


def _book_names(nodes: list) -> list[str]:
    """The `name` of every schema.org Book identity on the page, whether a
    top-level Book or the `isPartOf` Book of an Article."""

    names: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("@type") == "Book" and node.get("name"):
            names.append(node["name"])
        part = node.get("isPartOf")
        if isinstance(part, dict) and part.get("@type") == "Book" and part.get("name"):
            names.append(part["name"])
    return names


def _jsonld_urls(node) -> list[str]:
    """Every url/image/item string anywhere in a JSON-LD node."""

    urls: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("url", "image", "item") and isinstance(value, str):
                urls.append(value)
            else:
                urls.extend(_jsonld_urls(value))
    elif isinstance(node, list):
        for item in node:
            urls.extend(_jsonld_urls(item))
    return urls


def _resolve_absolute(url: str, base: str, pages: Path) -> Path | None:
    """The file a base-relative absolute URL is served from, or None if the
    URL is not under the site base. A trailing slash maps to index.html."""

    if not base or not url.startswith(base):
        return None
    rel = url[len(base):]
    if rel == "" or rel.endswith("/"):
        rel += "index.html"
    return (pages / rel).resolve()


def _check_canonical(where, head: str, base: str, base_root: str) -> list[str]:
    """A canonical URL exists exactly when a site-url is configured, and
    points under it -- never a false or foreign canonical."""

    m = re.search(r'<link rel="canonical" href="([^"]*)"', head)
    canonical = m.group(1) if m else None
    out: list[str] = []
    if base and not canonical:
        out.append(f"{where}: site-url is set but there is no canonical URL")
    if not base and canonical:
        out.append(f"{where}: canonical URL {canonical!r} but no site-url is configured")
    if base and canonical and not canonical.startswith(base_root + "/"):
        out.append(f"{where}: canonical {canonical!r} is not under the site-url {base_root!r}")
    return out


def _check_jsonld_identity(where, nodes: list, want: str) -> list[str]:
    """The structured data names this book, never a stale or missing one."""

    out: list[str] = []
    if not nodes:
        out.append(f"{where}: carries no JSON-LD structured metadata")
    names = _book_names(nodes)
    if names and want not in names:
        out.append(f"{where}: JSON-LD names {names!r}, not the book {want!r}")
    for name in names:
        if name != want:
            out.append(f"{where}: JSON-LD carries a stale book name {name!r} (expected {want!r})")
    return out


def _check_urls_resolve(where, nodes: list, head: str, base: str, pages: Path,
                        download_set: set) -> list[str]:
    """Every base-relative JSON-LD/image URL resolves, names no foreign
    edition, and the og:image points at a cover that exists."""

    out: list[str] = []
    for url in {u for node in nodes for u in _jsonld_urls(node)}:
        target = _resolve_absolute(url, base, pages)
        if "/downloads/" in url and url.rsplit("/", 1)[-1] not in download_set:
            out.append(f"{where}: JSON-LD names a foreign edition "
                       f"{url.rsplit('/', 1)[-1]!r} that is not among this book's downloads")
        if target is not None and not target.exists():
            out.append(f"{where}: JSON-LD URL does not resolve: {url}")
    img = re.search(r'property="og:image" content="([^"]*)"', head)
    if img:
        target = _resolve_absolute(img.group(1), base, pages)
        if target is not None and not target.exists():
            out.append(f"{where}: og:image points at a missing cover: {img.group(1)}")
    return out


def _check_one_surface(page: Path, pages: Path, want: str, base: str,
                       base_root: str, download_set: set) -> list[str]:
    import json

    where = page.relative_to(pages)
    text = page.read_text(encoding="utf-8", errors="replace")
    head_match = _HEAD.search(text)
    head = head_match.group(0) if head_match else text

    out = _check_canonical(where, head, base, base_root)
    if 'property="og:title"' not in head:
        out.append(f"{where}: no Open Graph title")
    if 'name="twitter:card"' not in head:
        out.append(f"{where}: no Twitter card")
    try:
        nodes = _jsonld_nodes(text)
    except json.JSONDecodeError as exc:
        out.append(f"{where}: JSON-LD is not valid JSON: {exc}")
        nodes = []
    out += _check_jsonld_identity(where, nodes, want)
    out += _check_urls_resolve(where, nodes, head, base, pages, download_set)
    if _PRIVATE_DATA.search(head) or commerce_secret(head):
        out.append(f"{where}: page metadata leaks private build data or a secret")
    return out


def check_metadata(pages: Path, title: str, site_url: str,
                   downloads: list[str]) -> list[str]:
    """Every metadata surface declares honest identity (#158): a canonical URL
    exactly when a site-url is configured (and pointing at it), Open Graph and
    Twitter cards, valid JSON-LD that names this book (never a stale or foreign
    one), a social image that resolves and is not claimed for a missing cover,
    and no private build data anywhere in the head."""

    import html as html_mod

    want = html_mod.unescape(title)
    base_root = (site_url or "").strip().rstrip("/")
    base = (base_root + "/") if base_root else ""
    download_set = set(downloads)

    failures: list[str] = []
    for page in _metadata_surfaces(pages):
        failures += _check_one_surface(page, pages, want, base, base_root, download_set)
    return failures


def commerce_secret(text: str) -> bool:
    from . import commerce

    return bool(commerce._SECRET_MARKERS.search(text))


def check_book_sitemap(pages: Path, site_url: str) -> list[str]:
    """The book-site sitemap is explicit and deterministic (#158): present only
    when a site-url is configured, every declared <loc> resolves to a real
    file, and every metadata surface's canonical is listed."""

    failures: list[str] = []
    base_root = (site_url or "").strip().rstrip("/")
    base = (base_root + "/") if base_root else ""
    sitemap = pages / "sitemap.xml"

    if not base:
        if sitemap.is_file():
            failures.append("a sitemap.xml was emitted but no site-url is configured")
        return failures

    if not sitemap.is_file():
        return ["site-url is set but no sitemap.xml was emitted"]
    locs = re.findall(r"<loc>([^<]+)</loc>", sitemap.read_text(encoding="utf-8", errors="replace"))
    loc_set = set(locs)
    for loc in locs:
        target = _resolve_absolute(loc, base, pages)
        if target is None:
            failures.append(f"sitemap <loc> is not under the site-url: {loc}")
        elif not target.exists():
            failures.append(f"sitemap <loc> does not resolve to a file: {loc}")

    for page in _metadata_surfaces(pages):
        text = page.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'<link rel="canonical" href="([^"]*)"', text)
        if m and m.group(1) not in loc_set:
            failures.append(
                f"{page.relative_to(pages)}: canonical {m.group(1)!r} is absent from the sitemap")
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
    failures += check_metadata(pages, title, site_url, downloads)
    failures += check_book_sitemap(pages, site_url)
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
