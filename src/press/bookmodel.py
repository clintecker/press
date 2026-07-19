"""The book, parsed once: one typed model behind every consumer.

Every module used to read raw YAML and privately assume keys and
types; press check validated four fields while later targets demanded
others, and two modules disagreed about whether author is a string or
a list. The model parses config/metadata.yaml once, normalizes what
has more than one honest spelling (a lone author becomes a list of
one, a missing trim becomes the house 6 x 9), validates what the
pipeline trusts (slug shape, trim law, sentinel types), and reports
every defect at once with the file and key that caused it.

The v1 trim law lives here: book-header.tex is a 6 x 9 design, so v1
accepts only 6 x 9 (or an omitted trim meaning the same); configurable
geometry is a v2, breaking-change concern, and pretending otherwise
built one size while verifying another.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Book:
    root: Path
    title: str
    subtitle: str
    authors: tuple[str, ...]
    date: str
    year: str | None
    copyright: str
    publisher: str
    publisher_place: str
    description: str
    keywords: tuple[str, ...]
    slug: str
    repository: str
    site_url: str
    trim_width: float
    trim_height: float
    sentinels: tuple[str, ...]
    min_pages: int
    print_config: dict = field(default_factory=dict)
    registrations: dict = field(default_factory=dict)


def _fail(problems: list[str], source: Path) -> None:
    lines = "\n".join(f"  - {p}" for p in problems)
    raise SystemExit(f"configuration problems in {source}:\n{lines}")


def load(root: Path, raw: dict) -> Book:  # noqa: C901
    """Normalize and validate the parsed metadata into the one model."""

    from . import booklib

    source = root / "config" / "metadata.yaml"
    problems: list[str] = []

    def text(key: str, required: bool = False, default: str = "") -> str:
        value = raw.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            if required:
                problems.append(f"{key}: required and missing or empty")
            return default
        if not isinstance(value, (str, int, float)):
            problems.append(f"{key}: expected text, found {type(value).__name__}")
            return default
        return str(value).strip()

    title = text("title", required=True)
    subtitle = text("subtitle")
    date = text("date")
    copyright_ = text("copyright")
    publisher = text("publisher")
    publisher_place = text("publisher-place")
    description = text("description")
    repository = text("repository")
    site_url = text("site-url")

    authors_raw = raw.get("author")
    if authors_raw is None:
        problems.append("author: required and missing")
        authors: tuple[str, ...] = ()
    elif isinstance(authors_raw, str):
        authors = (authors_raw.strip(),) if authors_raw.strip() else ()
        if not authors:
            problems.append("author: empty")
    elif isinstance(authors_raw, list) and all(isinstance(a, str) for a in authors_raw):
        authors = tuple(a.strip() for a in authors_raw if a.strip())
        if not authors:
            problems.append("author: empty list")
    else:
        problems.append("author: expected a name or a list of names")
        authors = ()

    slug_raw = text("slug", required=True)
    slug = slug_raw
    if slug_raw:
        try:
            slug = booklib.validate_slug(slug_raw)
        except SystemExit as exc:
            problems.append(str(exc))

    trim = raw.get("trim") or {}
    if not isinstance(trim, dict):
        problems.append("trim: expected a mapping {width, height}")
        trim = {}
    try:
        trim_width = float(trim.get("width", 6))
        trim_height = float(trim.get("height", 9))
    except (TypeError, ValueError):
        problems.append("trim: width and height must be numbers")
        trim_width, trim_height = 6.0, 9.0
    if (trim_width, trim_height) != (6.0, 9.0):
        problems.append(
            f"trim: {trim_width:g} x {trim_height:g} is not supported in v1; "
            "the design is 6 x 9 (omit trim, or state 6 x 9). Configurable "
            "geometry is a v2, breaking-change concern."
        )

    sentinels_raw = raw.get("verify-sentinels") or []
    if not isinstance(sentinels_raw, list) or not all(
        isinstance(s, str) for s in sentinels_raw
    ):
        problems.append("verify-sentinels: expected a list of text fragments")
        sentinels_raw = []
    sentinels = tuple(s for s in sentinels_raw if s.strip())

    try:
        min_pages = int(raw.get("verify-min-pages", 40))
    except (TypeError, ValueError):
        problems.append("verify-min-pages: expected a number")
        min_pages = 40

    keywords_raw = raw.get("keywords") or []
    keywords = tuple(str(k) for k in keywords_raw) if isinstance(keywords_raw, list) else ()

    year_match = re.search(r"\b(1\d{3}|2\d{3})\b", date)

    print_config = raw.get("print") or {}
    if not isinstance(print_config, dict):
        problems.append("print: expected a mapping")
        print_config = {}
    registrations = raw.get("registrations") or {}
    if not isinstance(registrations, dict):
        problems.append("registrations: expected a mapping")
        registrations = {}

    if problems:
        _fail(problems, source)

    return Book(
        root=root,
        title=title,
        subtitle=subtitle,
        authors=authors,
        date=date,
        year=year_match.group(1) if year_match else None,
        copyright=copyright_,
        publisher=publisher,
        publisher_place=publisher_place,
        description=description,
        keywords=keywords,
        slug=slug,
        repository=repository,
        site_url=site_url,
        trim_width=trim_width,
        trim_height=trim_height,
        sentinels=sentinels,
        min_pages=min_pages,
        print_config=print_config,
        registrations=registrations,
    )
