"""Create a new book part -- a chapter, an appendix, or a front-matter
page -- placing the file where the manuscript merge order needs it.

The press stitches ``book/chapters/*.md`` and then ``book/appendices/*.md``
in filename order, so the leading number on a chapter and the leading
letter on an appendix are not decoration: those characters *are* the
placement mechanism. This command owns them, so an author never types
``00-`` or ``z-`` by hand and a change to the convention is a change to
one tool rather than to every book built from a doc snippet. It refuses
to overwrite an existing file and seeds a valid heading stub.

It is the sanctioned alternative to shell-escaping Markdown into a file
with ``printf ... > file``, which silently clobbers a draft and breaks
the moment real prose carries an apostrophe.
"""

from __future__ import annotations

import re
import string
from pathlib import Path

from . import booklib

KINDS = ("chapter", "appendix")

USAGE = (
    "usage: press add chapter|appendix <name> [--front]\n"
    "  chapter <name>           next numbered slot "
    "(book/chapters/NN-<slug>.md)\n"
    "  chapter <name> --front   before the numbered chapters "
    "(00-<slug>.md)\n"
    "  appendix <name>          back matter "
    "(book/appendices/<letter>-<slug>.md)\n"
    "  appendix <name> --front  front of the appendices "
    "(a-<slug>.md)\n"
)


def slugify(name: str) -> str:
    """A filename-safe slug from a human title or an existing slug.

    Folds to the artifact-basename alphabet the press writes everywhere
    (lowercase kebab), so the filename cannot carry a space, an
    apostrophe, or a shell-active character. Idempotent: an input that is
    already a slug is returned unchanged.
    """

    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    if not slug or not booklib.SLUG_PATTERN.fullmatch(slug):
        raise SystemExit(
            f"cannot make a filename from {name!r}: a part name needs at "
            "least one letter or digit"
        )
    return slug


def heading(name: str) -> str:
    """The stub heading: a human title verbatim, a bare slug sentence-cased."""

    if name != name.lower() or " " in name:
        return name.strip()
    words = name.strip().strip("-").replace("-", " ")
    return words[:1].upper() + words[1:]


def _next_chapter_prefix(root: Path) -> str:
    """The numeric prefix one past the highest numbered chapter."""

    numbers = []
    for path in (root / "book" / "chapters").glob("[0-9]*.md"):
        match = re.match(r"(\d+)", path.name)
        if match:
            numbers.append(int(match.group(1)))
    nxt = (max(numbers) + 1) if numbers else 1
    width = max(2, len(str(nxt)))
    return f"{nxt:0{width}d}"


def _next_appendix_letter(root: Path, front: bool) -> str:
    """The next unused single-letter appendix prefix: counting up from
    ``a`` for front matter, down from ``z`` for back matter, so successive
    back-matter parts land at z, y, x and successive front ones at a, b, c.
    """

    used = {
        path.name[0]
        for path in (root / "book" / "appendices").glob("[a-z]-*.md")
    }
    order = string.ascii_lowercase if front else string.ascii_lowercase[::-1]
    for letter in order:
        if letter not in used:
            return letter
    raise SystemExit(
        "the appendices are full: every single-letter prefix a-z is taken"
    )


def _stub(name: str, unnumbered: bool) -> str:
    tag = " {.unnumbered}" if unnumbered else ""
    return (
        f"# {heading(name)}{tag}\n\n"
        "Write this part here. This placeholder paragraph only exists so "
        "the file is valid Markdown that builds; delete it and begin.\n"
    )


def _target(root: Path, kind: str, slug: str, front: bool) -> Path:
    if kind == "chapter":
        prefix = "00" if front else _next_chapter_prefix(root)
        return root / "book" / "chapters" / f"{prefix}-{slug}.md"
    letter = _next_appendix_letter(root, front)
    return root / "book" / "appendices" / f"{letter}-{slug}.md"


def _parse(argv: list[str]) -> tuple[str, str, bool] | None:
    """(kind, name, front) from the argument vector, or None on a usage
    error the caller reports."""

    front = False
    positional: list[str] = []
    for arg in argv:
        if arg == "--front":
            front = True
        elif arg.startswith("-"):
            print(f"unknown option: {arg}")
            return None
        else:
            positional.append(arg)
    if len(positional) != 2 or positional[0] not in KINDS:
        return None
    return positional[0], positional[1], front


def main(argv: list[str]) -> int:
    parsed = _parse(argv)
    if parsed is None:
        print(USAGE, end="")
        return 2
    kind, name, front = parsed

    root = booklib.root()
    slug = slugify(name)
    target = _target(root, kind, slug, front)
    relative = target.relative_to(root)

    if target.exists():
        print(
            f"{relative} already exists; refusing to overwrite it. Rename "
            "or remove it first, or choose another name."
        )
        return 1

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_stub(name, unnumbered=(kind == "chapter" and front)),
                      encoding="utf-8")
    print(f"created {relative}")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
