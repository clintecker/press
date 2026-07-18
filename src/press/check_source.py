"""Fast source checks before invoking Pandoc or TeX."""

from __future__ import annotations

import re
from pathlib import Path

from . import booklib

FORBIDDEN = ["TODO: write", "TBD: write", "lorem ipsum"]


def main() -> int:
    root = booklib.root()
    failures: list[str] = []
    seen: set[Path] = set()
    for path in booklib.chapter_files():
        if path in seen:
            failures.append(f"duplicate source file: {path.relative_to(root)}")
        seen.add(path)
        if not path.is_file():
            failures.append(f"missing source file: {path.relative_to(root)}")
            continue
        text = path.read_text(encoding="utf-8")
        if len(text.strip()) < 80:
            failures.append(f"suspiciously short source: {path.relative_to(root)}")
        if not re.search(r"^#\s+\S", text, flags=re.MULTILINE):
            failures.append(f"no level-1 heading: {path.relative_to(root)}")
        lowered = text.lower()
        for phrase in FORBIDDEN:
            if phrase in lowered:
                failures.append(f"unfinished marker '{phrase}': {path.relative_to(root)}")

    metadata = booklib.metadata()
    for required in ["title", "author", "description", "slug"]:
        if not metadata.get(required):
            failures.append(f"metadata missing {required}:")

    # A plate on disk that no manuscript file references ships in every
    # archive and the site while appearing in no book; orphans are
    # mistakes. The match is path-anchored so raven.jpg cannot hide
    # behind a reference to black-raven.jpg.
    manuscript = "\n".join(
        path.read_text(encoding="utf-8") for path in seen if path.is_file()
    )
    for plate in sorted((root / "assets" / "woodcuts").glob("*.jpg")):
        if f"woodcuts/{plate.name}" not in manuscript:
            failures.append(
                f"plate never referenced by the manuscript: assets/woodcuts/{plate.name}"
            )

    if failures:
        print("Source checks failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"Source checks passed: {len(seen)} ordered Markdown files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
