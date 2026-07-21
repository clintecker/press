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


def _text(
    raw: dict, problems: list[str], key: str, required: bool = False, default: str = ""
) -> str:
    value = raw.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            problems.append(f"{key}: required and missing or empty")
        return default
    if not isinstance(value, (str, int, float)):
        problems.append(f"{key}: expected text, found {type(value).__name__}")
        return default
    return str(value).strip()


def _authors(raw: dict, problems: list[str]) -> tuple[str, ...]:
    authors_raw = raw.get("author")
    if authors_raw is None:
        problems.append("author: required and missing")
        return ()
    if isinstance(authors_raw, str):
        authors = (authors_raw.strip(),) if authors_raw.strip() else ()
        if not authors:
            problems.append("author: empty")
        return authors
    if isinstance(authors_raw, list) and all(isinstance(a, str) for a in authors_raw):
        authors = tuple(a.strip() for a in authors_raw if a.strip())
        if not authors:
            problems.append("author: empty list")
        return authors
    problems.append("author: expected a name or a list of names")
    return ()


def _slug(raw: dict, problems: list[str]) -> str:
    from . import booklib

    slug_raw = _text(raw, problems, "slug", required=True)
    if slug_raw:
        try:
            return booklib.validate_slug(slug_raw)
        except SystemExit as exc:
            problems.append(str(exc))
    return slug_raw


def _trim(raw: dict, problems: list[str]) -> tuple[float, float]:
    """Trim comes from the selected design profile (``print.profile``), not a
    hand-entered number: a profile is a sealed, verified geometry, so the trim
    can never disagree with the interior it was laid out for. The house
    profile is 6 x 9, so a book that selects none keeps the v1 trim. A legacy
    ``metadata.trim`` is honored only as a cross-check against the profile."""

    from . import profiles

    profile_id = (raw.get("print") or {}).get("profile")
    try:
        profile = profiles.load(profile_id)
    except SystemExit as exc:
        problems.append(str(exc))
        return 6.0, 9.0

    trim_width, trim_height = profile.trim
    legacy = raw.get("trim")
    if isinstance(legacy, dict) and legacy:
        try:
            legacy_w = float(legacy.get("width", trim_width))
            legacy_h = float(legacy.get("height", trim_height))
        except (TypeError, ValueError):
            problems.append("trim: width and height must be numbers")
        else:
            if (legacy_w, legacy_h) != (trim_width, trim_height):
                problems.append(
                    f"trim: metadata declares {legacy_w:g} x {legacy_h:g}, but the "
                    f"design profile {profile.id!r} is {trim_width:g} x {trim_height:g}; "
                    "trim comes from print.profile, so drop the metadata trim"
                )
    return trim_width, trim_height


def _verification_knobs(raw: dict, problems: list[str]) -> tuple[tuple[str, ...], int]:
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
    return sentinels, min_pages


def _mapping(raw: dict, problems: list[str], key: str) -> dict:
    value = raw.get(key) or {}
    if not isinstance(value, dict):
        problems.append(f"{key}: expected a mapping")
        value = {}
    return value


def load(root: Path, raw: dict) -> Book:
    """Normalize and validate the parsed metadata into the one model."""

    source = root / "config" / "metadata.yaml"
    problems: list[str] = []

    title = _text(raw, problems, "title", required=True)
    subtitle = _text(raw, problems, "subtitle")
    date = _text(raw, problems, "date")
    copyright_ = _text(raw, problems, "copyright")
    publisher = _text(raw, problems, "publisher")
    publisher_place = _text(raw, problems, "publisher-place")
    description = _text(raw, problems, "description")
    repository = _text(raw, problems, "repository")
    site_url = _text(raw, problems, "site-url")

    authors = _authors(raw, problems)
    slug = _slug(raw, problems)
    trim_width, trim_height = _trim(raw, problems)
    sentinels, min_pages = _verification_knobs(raw, problems)

    keywords_raw = raw.get("keywords") or []
    keywords = tuple(str(k) for k in keywords_raw) if isinstance(keywords_raw, list) else ()

    year_match = re.search(r"\b(1\d{3}|2\d{3})\b", date)

    print_config = _mapping(raw, problems, "print")
    registrations = _mapping(raw, problems, "registrations")

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
