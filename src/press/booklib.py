"""Shared facts derived from the book being built.

The press is a pipeline with no book inside it. Every fact about the book
under construction comes from the book repository: identity and verification
knobs from config/metadata.yaml, house style from config/house-rules.yaml,
reading order from filename prefixes under book/. Nothing is stated a second
time anywhere else.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import yaml

DATA = Path(__file__).resolve().parent / "data"


@lru_cache(maxsize=1)
def root() -> Path:
    """The book repository being built: $BOOK_ROOT or the working directory."""

    candidate = Path(os.environ.get("BOOK_ROOT") or Path.cwd()).resolve()
    if not (candidate / "config" / "metadata.yaml").is_file():
        raise SystemExit(
            f"{candidate} is not a book: config/metadata.yaml not found "
            "(run from the book repository, or set BOOK_ROOT)"
        )
    return candidate


@lru_cache(maxsize=1)
def metadata() -> dict:
    """Parsed config/metadata.yaml."""

    with (root() / "config" / "metadata.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@lru_cache(maxsize=1)
def house_rules() -> dict:
    """Parsed config/house-rules.yaml, or an empty ruleset if absent."""

    path = root() / "config" / "house-rules.yaml"
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def slug() -> str:
    """Artifact basename, e.g. dist/<slug>.pdf."""

    value = metadata().get("slug")
    if not value:
        raise SystemExit("config/metadata.yaml must set slug: (artifact basename)")
    return value


def sentinels() -> list[str]:
    """Prose fragments every rendered artifact must contain.

    The title is checked only where a title page exists; different pandoc
    writers place metadata titles differently across versions.
    """

    return list(metadata().get("verify-sentinels") or [])


def year() -> str | None:
    """The publication year inside the human-readable date, if any.

    The date field is prose ("First edition, 2026"); the machines that
    need a real date (EPUB dc:date, the title page's roman numerals)
    extract the year from this one stated copy.
    """

    match = re.search(r"\b(1\d{3}|2\d{3})\b", str(metadata().get("date") or ""))
    return match.group(1) if match else None


def chapter_files() -> list[Path]:
    """Return the ordered manuscript files: chapters, then appendices."""

    chapters = sorted((root() / "book" / "chapters").glob("[0-9]*.md"))
    appendices = sorted((root() / "book" / "appendices").glob("[a-z]-*.md"))
    files = chapters + appendices
    if not files:
        raise FileNotFoundError("no manuscript files found under book/")
    return files


def chapter_args() -> list[str]:
    """The same files as strings relative to the book root."""

    return [str(path.relative_to(root())) for path in chapter_files()]
