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

from . import yamlio

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


def load_config_mapping(path, required: bool = False) -> dict:
    """A YAML mapping from a config file, or a locatable refusal.

    Config errors are the author's to fix and deserve a diagnostic
    naming the file and line, not a parser traceback; an empty or
    non-mapping file is refused before any consumer can dereference
    None.
    """

    if not path.is_file():
        if required:
            raise SystemExit(f"{path}: missing (a book requires this file)")
        return {}
    try:
        loaded = yamlio.loads(path.read_text(encoding="utf-8"))
    except yamlio.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f":{mark.line + 1}" if mark is not None else ""
        problem = getattr(exc, "problem", None) or "invalid YAML"
        raise SystemExit(f"{path}{where}: {problem}") from exc
    if loaded is None:
        if required:
            raise SystemExit(f"{path}: empty")
        return {}
    if not isinstance(loaded, dict):
        raise SystemExit(
            f"{path}: must be a YAML mapping, not {type(loaded).__name__}"
        )
    return loaded


@lru_cache(maxsize=1)
def metadata() -> dict:
    """Parsed config/metadata.yaml."""

    return load_config_mapping(root() / "config" / "metadata.yaml", required=True)


@lru_cache(maxsize=1)
def book():
    """The one typed, normalized model of the book being built."""

    from . import bookmodel

    return bookmodel.load(root(), metadata())


@lru_cache(maxsize=1)
def house_rules() -> dict:
    """Parsed config/house-rules.yaml, or an empty ruleset if absent."""

    return load_config_mapping(root() / "config" / "house-rules.yaml")


SLUG_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]*")


def validate_slug(value: str) -> str:
    """The artifact-basename invariant: lowercase kebab, nothing else.

    The slug names every file the press writes and every download link
    it publishes; separators, dot segments, spaces, or shell- and
    HTML-active characters would let configuration redirect outputs
    outside dist or inject into CI outputs and markup.
    """

    if not SLUG_PATTERN.fullmatch(value):
        raise SystemExit(
            f"slug {value!r} is not a valid artifact basename: lowercase "
            "kebab-case ([a-z0-9-], starting with a letter or digit)"
        )
    return value


def slug() -> str:
    """Artifact basename, e.g. dist/<slug>.pdf."""

    return book().slug


def sentinels() -> list[str]:
    """Prose fragments every rendered artifact must contain.

    The title is checked only where a title page exists; different pandoc
    writers place metadata titles differently across versions.
    """

    return list(book().sentinels)


def year() -> str | None:
    """The publication year inside the human-readable date, if any.

    The date field is prose ("First edition, 2026"); the machines that
    need a real date (EPUB dc:date, the title page's roman numerals)
    extract the year from this one stated copy.
    """

    return book().year


def require_release_witnesses() -> None:
    """Release builds refuse vacuous verification.

    A scaffold's empty sentinel list and one-page floor are draft
    conveniences: they let a book build before its first real word.
    A release (PRESS_RELEASE=1, set by CI on tag builds) demands at
    least two sentinels and a real page floor, because a green
    verification that proves nothing is worse than a red one.
    """

    if not os.environ.get("PRESS_RELEASE"):
        return
    b = book()
    problems = []
    if len(b.sentinels) < 2:
        problems.append(
            f"verify-sentinels has {len(b.sentinels)} entries; a release "
            "needs at least 2 distinctive prose fragments"
        )
    if b.min_pages < 24:
        problems.append(
            f"verify-min-pages is {b.min_pages}; a release needs at least 24"
        )
    if problems:
        raise SystemExit(
            "this is a release build (PRESS_RELEASE=1) and its witnesses "
            "are vacuous:\n" + "\n".join(f"  - {p}" for p in problems)
            + "\n(drafts may build with defaults; releases must prove the "
            "manuscript survived)"
        )


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
