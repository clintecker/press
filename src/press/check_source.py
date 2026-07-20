"""Fast source checks before invoking Pandoc or TeX."""

from __future__ import annotations

import re
from pathlib import Path

from . import booklib

FORBIDDEN = ["TODO: write", "TBD: write", "lorem ipsum"]


def _content_failures(root: Path, path: Path) -> list[str]:
    """Everything wrong inside one source file that exists."""

    failures: list[str] = []
    text = path.read_text(encoding="utf-8")
    if len(text.strip()) < 80:
        failures.append(f"suspiciously short source: {path.relative_to(root)}")
    if not re.search(r"^#\s+\S", text, flags=re.MULTILINE):
        failures.append(f"no level-1 heading: {path.relative_to(root)}")
    lowered = text.lower()
    for phrase in FORBIDDEN:
        if phrase in lowered:
            failures.append(f"unfinished marker '{phrase}': {path.relative_to(root)}")
    return failures


def _source_failures(root: Path) -> tuple[list[str], set[Path]]:
    """Walk the ordered chapter list once; return failures and the set seen."""

    failures: list[str] = []
    seen: set[Path] = set()
    for path in booklib.chapter_files():
        if path in seen:
            failures.append(f"duplicate source file: {path.relative_to(root)}")
        seen.add(path)
        if not path.is_file():
            failures.append(f"missing source file: {path.relative_to(root)}")
            continue
        failures.extend(_content_failures(root, path))
    return failures, seen


def _metadata_failures() -> list[str]:
    metadata = booklib.metadata()
    return [
        f"metadata missing {required}:"
        for required in ["title", "author", "description", "slug"]
        if not metadata.get(required)
    ]


def _sentinel_failures(seen: set[Path]) -> list[str]:
    # A sentinel that never appears in the source proves nothing in the
    # artifacts; catch the typo here, not after six builds.
    manuscript_text = " ".join(
        " ".join(path.read_text(encoding="utf-8").split())
        for path in seen if path.is_file()
    )
    return [
        f"sentinel not found in the manuscript: {sentinel}"
        for sentinel in booklib.sentinels()
        if " ".join(sentinel.split()) not in manuscript_text
    ]


def _plate_failures(root: Path, seen: set[Path]) -> list[str]:
    # A plate on disk that no manuscript file references ships in every
    # archive and the site while appearing in no book; orphans are
    # mistakes. The match is path-anchored so raven.jpg cannot hide
    # behind a reference to black-raven.jpg.
    manuscript = "\n".join(
        path.read_text(encoding="utf-8") for path in seen if path.is_file()
    )
    return [
        f"plate never referenced by the manuscript: assets/woodcuts/{plate.name}"
        for plate in sorted((root / "assets" / "woodcuts").glob("*.jpg"))
        if f"woodcuts/{plate.name}" not in manuscript
    ]


def main() -> int:
    root = booklib.root()
    failures, seen = _source_failures(root)
    failures.extend(_metadata_failures())

    from . import commerce, registrations

    failures.extend(registrations.failures())
    failures.extend(commerce.failures())
    failures.extend(_sentinel_failures(seen))
    failures.extend(_plate_failures(root, seen))

    if failures:
        print("Source checks failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"Source checks passed: {len(seen)} ordered Markdown files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
