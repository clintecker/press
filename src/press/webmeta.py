"""One web-metadata emitter for every surface the press publishes (#158).

The docs site, the book landing page, the reader index, and the reader
chapter pages all owe the same head fragment: a canonical URL, Open Graph
and Twitter cards, and a schema.org JSON-LD node, generated from
authoritative config and never faked. This module is the single place that
knows the shape of that fragment and the one law that binds all of it:

    when there is no public base URL, nothing URL-shaped is emitted.

An offline build (a book with no ``site-url``, a preview deploy) carries the
facts it honestly has -- title, description, author, publisher -- but no
canonical link, no ``og:url``, no ``og:image``, and a JSON-LD node stripped
of every ``url``/``image``/``@id``/``item`` it cannot stand behind. That way
a build that is not served from a known address never claims one.

The module is stdlib-only so the docs-site builder (a pandoc-only runner
with no installed dependencies) can import it too.
"""

from __future__ import annotations

import html as _html
import json as _json
from typing import Any


def _esc(value: Any) -> str:
    return _html.escape(str(value if value is not None else ""), quote=True)


def _strip_url_shaped(node: Any) -> Any:
    """Recursively drop URL-shaped keys from a JSON-LD node.

    This is the JSON-LD half of the no-public-base law: an offline node keeps
    its facts (name, author, description) but loses every ``url``, ``image``,
    ``@id``, and breadcrumb ``item`` it has no honest address for.
    """

    if isinstance(node, dict):
        return {
            key: _strip_url_shaped(value)
            for key, value in node.items()
            if key not in ("url", "image", "@id", "item")
        }
    if isinstance(node, list):
        return [_strip_url_shaped(item) for item in node]
    return node


def jsonld_script(node: Any, *, indent_prefix: str = "") -> str:
    """One ``<script type="application/ld+json">`` block. The open tag is on
    its own line and the payload on the next, matching what the verifier's
    extractor expects on every surface."""

    body = _json.dumps(node, ensure_ascii=False, indent=2)
    return (
        f'{indent_prefix}<script type="application/ld+json">\n'
        f"{body}\n"
        f"{indent_prefix}</script>"
    )


def _og_image_lines(image: str, width: int | None, height: int | None,
                    alt: str) -> list[str]:
    """The og:image family, emitted only for a real, dimensioned social card."""

    lines = [f'<meta property="og:image" content="{_esc(image)}">']
    if width:
        lines.append(f'<meta property="og:image:width" content="{int(width)}">')
    if height:
        lines.append(f'<meta property="og:image:height" content="{int(height)}">')
    if alt:
        lines.append(f'<meta property="og:image:alt" content="{_esc(alt)}">')
    return lines


def head_fragment(
    *,
    base: str,
    title: str,
    description: str = "",
    og_type: str = "website",
    site_name: str = "",
    canonical: str = "",
    image: str = "",
    image_width: int | None = None,
    image_height: int | None = None,
    image_alt: str = "",
    twitter_card: str = "summary_large_image",
    description_meta: bool = False,
    extra_properties: list[tuple[str, str]] | None = None,
    jsonld: Any = None,
    indent: str = "",
) -> str:
    """The canonical/OG/Twitter/JSON-LD ``<head>`` fragment for one page.

    ``base`` is the site's public root (``""`` for an offline/preview build).
    It is the one switch for the no-public-base law: when it is empty every
    URL-shaped output is dropped here, in one place, regardless of what the
    caller passed -- ``canonical`` and ``image`` are ignored and the JSON-LD
    node is stripped of its URL-shaped keys. Callers therefore never have to
    remember the rule; they pass the absolute URLs and this enforces it.

    ``canonical`` and ``image`` are absolute URLs the caller has already
    composed against ``base``. ``extra_properties`` are additional
    ``<meta property=...>`` pairs that are never URL-shaped (``book:author``,
    ``article:published_time``). ``description_meta`` also emits a plain
    ``<meta name="description">`` (the docs site wants it here; the landing
    template owns its own, so it leaves this off).
    """

    if not base:
        canonical = ""
        image = ""
        jsonld = _strip_url_shaped(jsonld) if jsonld is not None else None

    lines: list[str] = []

    def add(markup: str) -> None:
        lines.append(indent + markup)

    if description_meta and description:
        add(f'<meta name="description" content="{_esc(description)}">')
    if canonical:
        add(f'<link rel="canonical" href="{_esc(canonical)}">')

    add(f'<meta property="og:type" content="{_esc(og_type)}">')
    add(f'<meta property="og:title" content="{_esc(title)}">')
    if site_name:
        add(f'<meta property="og:site_name" content="{_esc(site_name)}">')
    if description:
        add(f'<meta property="og:description" content="{_esc(description)}">')
    if canonical:
        add(f'<meta property="og:url" content="{_esc(canonical)}">')
    for prop, content in extra_properties or []:
        add(f'<meta property="{_esc(prop)}" content="{_esc(content)}">')
    if image:
        for line in _og_image_lines(image, image_width, image_height, image_alt):
            add(line)

    add(f'<meta name="twitter:card" content="{_esc(twitter_card)}">')
    add(f'<meta name="twitter:title" content="{_esc(title)}">')
    if description:
        add(f'<meta name="twitter:description" content="{_esc(description)}">')
    if image:
        add(f'<meta name="twitter:image" content="{_esc(image)}">')

    if jsonld is not None:
        lines.append(jsonld_script(jsonld, indent_prefix=indent))

    return "\n".join(lines)
