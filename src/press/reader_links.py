"""Resolve the reader site's cross-page anchors.

pandoc's chunked writer rewrites the links it generates itself (the table
of contents, the pager) to ``<page>.html#id``, but a link the manuscript
carried -- a ``@fig:`` cross-reference, a ``[text](#id)`` -- stays ``#id``
on every page, so a reference to a figure in another chapter is a dead
link on the page that makes it (#270). This pass runs after the chunked
write: it maps every id to the page that carries it and rewrites each bare
fragment naming an id on a different page to that page's address. An
anchor it cannot place (an id on no page, or on several) is left as it was,
so ``verify_formats.require_anchors_resolve`` names it and the build fails
instead of shipping a dead link.
"""

from __future__ import annotations

import html
import html.parser
import os
import re
import urllib.parse
from pathlib import Path

# A bare-fragment href as pandoc writes it: double-quoted, never empty.
BARE_FRAGMENT = re.compile(r'href="#([^"]+)"')


class AnchorScan(html.parser.HTMLParser):
    """One pass over a page: the ids it defines and the hrefs it makes."""

    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name == "id" and value:
                self.ids.add(value)
            elif tag == "a" and name == "name" and value:
                self.ids.add(value)
            elif tag == "a" and name == "href" and value:
                self.hrefs.append(value)


def _scan(page: Path) -> AnchorScan:
    scan = AnchorScan()
    scan.feed(page.read_text(encoding="utf-8", errors="replace"))
    return scan


def anchor_ids(page: Path) -> set[str]:
    """The ids one page defines (``id=`` on any element, ``name=`` on ``<a>``)."""

    return _scan(page).ids


def local_anchors(page: Path) -> list[str]:
    """The fragments of every bare ``#id`` link on the page, in document
    order, duplicates folded; ``href="#"`` names nothing and is not one."""

    seen: dict[str, None] = {}
    for href in _scan(page).hrefs:
        if href.startswith("#") and len(href) > 1:
            seen.setdefault(urllib.parse.unquote(href[1:]), None)
    return list(seen)


def sibling_anchors(page: Path) -> list[tuple[str, str]]:
    """Every ``<path>#<fragment>`` link to a relative local target, as
    (path, fragment) pairs: the shape ``resolve_anchors`` writes, so a
    verifier can prove the rewritten address lands on a real id."""

    pairs: list[tuple[str, str]] = []
    for href in _scan(page).hrefs:
        parsed = urllib.parse.urlparse(href)
        if parsed.scheme or parsed.netloc or not parsed.path or not parsed.fragment:
            continue
        if parsed.path.startswith("/"):
            continue
        pairs.append((urllib.parse.unquote(parsed.path), urllib.parse.unquote(parsed.fragment)))
    return pairs


def page_ids(site: Path) -> dict[Path, set[str]]:
    """Every HTML page under the site mapped to the ids it defines."""

    return {page: anchor_ids(page) for page in sorted(site.rglob("*.html"))}


def _owners(ids: dict[Path, set[str]]) -> dict[str, list[Path]]:
    owners: dict[str, list[Path]] = {}
    for page, page_set in ids.items():
        for anchor in page_set:
            owners.setdefault(anchor, []).append(page)
    return owners


def _resolve_page(page: Path, own: set[str], owners: dict[str, list[Path]]) -> int:
    """Rewrite one page's bare fragments that live on exactly one other
    page; returns how many links were rewritten."""

    text = page.read_text(encoding="utf-8")
    rewritten = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal rewritten
        raw = match.group(1)
        fragment = urllib.parse.unquote(html.unescape(raw))
        homes = owners.get(fragment, [])
        if fragment in own or len(homes) != 1:
            return match.group(0)
        target = Path(os.path.relpath(homes[0], page.parent)).as_posix()
        rewritten += 1
        return f'href="{target}#{raw}"'

    resolved = BARE_FRAGMENT.sub(replace, text)
    if rewritten:
        page.write_text(resolved, encoding="utf-8")
    return rewritten


def resolve_anchors(site: Path) -> int:
    """Point every bare ``#id`` link at the page that defines the id, when
    that page is not the one making the link. Returns the number of links
    rewritten; a fragment with no home or several is left for the verifier."""

    ids = page_ids(site)
    owners = _owners(ids)
    return sum(_resolve_page(page, own, owners) for page, own in ids.items())
