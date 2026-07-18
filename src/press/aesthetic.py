"""The book's visual identity, merged from config: press aesthetic.

The house aesthetic (data/aesthetic-house.yaml) is the default; a
book's config/aesthetic.yaml replaces any top-level section it names.
`press aesthetic` prints the effective merge, which is what the
art-direction workflow reads, so the one command answers "what will
the art look like" for authors and agents alike.
"""

from __future__ import annotations

import yaml

from . import booklib

HOUSE = booklib.DATA / "aesthetic-house.yaml"


def effective() -> dict:
    with HOUSE.open(encoding="utf-8") as handle:
        merged = yaml.safe_load(handle)
    book_file = booklib.root() / "config" / "aesthetic.yaml"
    if book_file.is_file():
        with book_file.open(encoding="utf-8") as handle:
            overrides = yaml.safe_load(handle) or {}
        merged.update(overrides)
    return merged


def show() -> int:
    book_file = booklib.root() / "config" / "aesthetic.yaml"
    source = book_file if book_file.is_file() else HOUSE
    print(f"# effective aesthetic ({source})")
    print(yaml.safe_dump(effective(), sort_keys=False, allow_unicode=True))
    return 0
